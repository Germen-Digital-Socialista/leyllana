"""Proveedor de nube via CLI de suscripcion (ADR 0018) y el gate de ADR 0013.

Sin red y sin subprocesos reales: se intercepta ``subprocess.Popen`` para mirar el
argv y el stdin que habrian salido. Varias de estas comprobaciones existen porque
el fallo real fue silencioso (codigo de salida 0 y texto plausible), no ruidoso.
"""

import subprocess

import pytest

from leyllana.config import CliConfig, Config, EngineConfig
from leyllana.engine import ConsentRequired, explain
from leyllana.engine.base import ProviderError
from leyllana.engine.cli_provider import CliProvider
from leyllana.engine.progress import Cancelled, CancelToken
from leyllana.prompt import Prompt
from leyllana.types import Nivel

PROMPT = Prompt(system="SYSTEM\ncon salto de linea", user="USER")

CUATRO_SECCIONES = (
    "Que hace: algo\n"
    "A quien afecta: alguien\n"
    "Articulos clave: uno\n"
    "En una frase: resumen\n"
)


def _config(**cli) -> Config:
    return Config(engine=EngineConfig(provider="cli", cli=CliConfig(**cli)))


class _FakeProc:
    """Subproceso falso con la superficie de ``Popen`` que usa el proveedor."""

    def __init__(self, espia, stdout, stderr, returncode, cuelga=False):
        self._espia = espia
        self._stdout = stdout
        self._stderr = stderr
        self._cuelga = cuelga
        self.returncode = returncode

    def communicate(self, entrada=None, timeout=None):
        if entrada is not None:
            self._espia.entrada = entrada
        if self._cuelga:
            raise subprocess.TimeoutExpired("cli", timeout or 0)
        return self._stdout, self._stderr

    def kill(self):
        self._espia.matado = True
        self._cuelga = False  # tras el kill, communicate() ya puede recoger


class _Corrida:
    """Fabrica de subprocesos falsos: registra la llamada y devuelve salida fija."""

    def __init__(self, stdout=CUATRO_SECCIONES, stderr="", returncode=0, cuelga=False):
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode
        self._cuelga = cuelga
        self.argv = None
        self.entrada = None
        self.kwargs = None
        self.llamadas = 0
        self.matado = False

    def __call__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.llamadas += 1
        return _FakeProc(
            self, self._stdout, self._stderr, self._returncode, self._cuelga
        )


def _patch(monkeypatch, espia):
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: f"/bin/{nombre}"
    )
    monkeypatch.setattr("leyllana.engine.cli_provider.subprocess.Popen", espia)
    return espia


@pytest.fixture
def corrida(monkeypatch):
    return _patch(monkeypatch, _Corrida())


def test_preset_claude_pasa_el_system_por_archivo(corrida):
    # El system prompt es multilinea: como argumento, el shim .cmd de Windows lo
    # corta en el primer salto de linea y el modelo se queda sin guardrail.
    CliProvider(_config(preset="claude")).generate(PROMPT)
    assert PROMPT.system not in " ".join(corrida.argv)
    ruta = corrida.argv[corrida.argv.index("--system-prompt-file") + 1]
    assert ruta.endswith("system.txt")
    assert corrida.entrada == PROMPT.user


def test_preset_kimi_antepone_el_system_al_stdin(corrida):
    # kimi no tiene flag de system prompt: va al principio de la entrada.
    CliProvider(_config(preset="kimi")).generate(PROMPT)
    assert corrida.argv[1:] == ["--quiet"]
    assert corrida.entrada == f"{PROMPT.system}\n\n{PROMPT.user}"


def test_command_explicito_gana_sobre_el_preset(corrida):
    CliProvider(_config(preset="claude", command=("otro", "exec"))).generate(PROMPT)
    assert corrida.argv[1:] == ["exec"]
    assert corrida.entrada.startswith(PROMPT.system)


def test_fuerza_utf8_en_las_tuberias_del_hijo(corrida):
    # Un CLI en Python usa la codepage ANSI de Windows y rompe con el primer
    # acento de una norma real.
    CliProvider(_config(preset="kimi")).generate(PROMPT)
    assert corrida.kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    assert corrida.kwargs["encoding"] == "utf-8"


def test_model_se_agrega_solo_si_esta_configurado(corrida):
    CliProvider(_config(preset="claude")).generate(PROMPT)
    assert "--model" not in corrida.argv
    CliProvider(_config(preset="claude", model="sonnet")).generate(PROMPT)
    assert corrida.argv[-2:] == ["--model", "sonnet"]


def test_sin_preset_ni_command_avisa(corrida):
    with pytest.raises(ProviderError, match="preset"):
        CliProvider(_config()).generate(PROMPT)


def test_preset_desconocido_avisa(corrida):
    with pytest.raises(ProviderError, match="preset"):
        CliProvider(_config(preset="inventado")).generate(PROMPT)


def test_cli_ausente_del_path_avisa(monkeypatch):
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: None
    )
    with pytest.raises(ProviderError, match="PATH"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_salida_no_cero_muestra_el_stderr(monkeypatch):
    _patch(monkeypatch, _Corrida(stdout="", stderr="se cayo el CLI", returncode=1))
    with pytest.raises(ProviderError, match="se cayo el CLI"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_salida_vacia_avisa(monkeypatch):
    _patch(monkeypatch, _Corrida(stdout="   \n"))
    with pytest.raises(ProviderError, match="no devolvio texto"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_timeout_mata_al_cli_y_avisa(monkeypatch):
    espia = _patch(monkeypatch, _Corrida(cuelga=True))
    with pytest.raises(ProviderError, match="no respondio"):
        CliProvider(_config(preset="claude", timeout=0)).generate(PROMPT)
    assert espia.matado  # no se deja un CLI huerfano corriendo


def test_arranque_fallido_se_reporta_como_error_de_proveedor(monkeypatch):
    def revienta(argv, **kwargs):
        raise OSError("no se pudo ejecutar")

    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: "/bin/claude"
    )
    monkeypatch.setattr("leyllana.engine.cli_provider.subprocess.Popen", revienta)
    with pytest.raises(ProviderError, match="Fallo la llamada"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_cancelar_mata_al_cli_en_vez_de_esperar_el_timeout(monkeypatch):
    # Sin esto, cancelar una corrida de nube significaba esperar diez minutos.
    espia = _patch(monkeypatch, _Corrida(cuelga=True))
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        CliProvider(_config(preset="claude")).generate(PROMPT, cancel=token)
    assert espia.matado


def test_sin_consentimiento_no_se_ejecuta_nada(corrida):
    # ADR 0013: el corte va antes de la primera llamada, no despues.
    with pytest.raises(ConsentRequired, match="claude"):
        explain("Articulo 1. Texto.", Nivel.PUBLICO, _config(preset="claude"))
    assert corrida.llamadas == 0


def test_con_consentimiento_genera(corrida):
    resultado = explain(
        "Articulo 1. Texto.", Nivel.PUBLICO, _config(preset="claude"), consent=True
    )
    assert resultado.en_una_frase == "resumen"
    assert corrida.llamadas == 1


def test_el_proveedor_local_no_pide_consentimiento(monkeypatch):
    # No hay regresion en el camino por defecto (ADR 0005): falla por falta de
    # configuracion del modelo, no por consentimiento.
    with pytest.raises(ProviderError):
        explain("Articulo 1. Texto.", Nivel.PUBLICO, Config())


def test_el_contexto_del_cli_manda_sobre_el_del_modelo_local(corrida):
    # Un CLI de nube tiene mucho mas contexto que el modelo local: un texto que
    # entra entero no debe trocearse (ADR 0017).
    largo = "Articulo 1. " + ("palabra " * 4000)
    explain(largo, Nivel.PUBLICO, _config(preset="claude"), consent=True)
    assert corrida.llamadas == 1  # una sola pasada, sin map-reduce
