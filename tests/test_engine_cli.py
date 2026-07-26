"""Proveedor de nube via CLI de suscripcion (ADR 0018) y el gate de ADR 0013.

Sin red y sin subprocesos reales: se intercepta ``subprocess.run`` para mirar el
argv y el stdin que habrian salido. Varias de estas comprobaciones existen porque
el fallo real fue silencioso (codigo de salida 0 y texto plausible), no ruidoso.
"""

import subprocess

import pytest

from leyllana.config import CliConfig, Config, EngineConfig
from leyllana.engine import ConsentRequired, explain
from leyllana.engine.base import ProviderError
from leyllana.engine.cli_provider import CliProvider
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


class _Corrida:
    """Registra la llamada y devuelve una salida fija."""

    def __init__(self, stdout=CUATRO_SECCIONES, stderr="", returncode=0):
        self.resultado = subprocess.CompletedProcess([], returncode, stdout, stderr)
        self.argv = None
        self.entrada = None
        self.llamadas = 0

    def __call__(self, argv, **kwargs):
        self.argv = argv
        self.entrada = kwargs.get("input")
        self.llamadas += 1
        return self.resultado


@pytest.fixture
def corrida(monkeypatch):
    espia = _Corrida()
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: f"/bin/{nombre}"
    )
    monkeypatch.setattr("leyllana.engine.cli_provider.subprocess.run", espia)
    return espia


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


def test_fuerza_utf8_en_las_tuberias_del_hijo(monkeypatch):
    # Un CLI en Python usa la codepage ANSI de Windows y rompe con el primer
    # acento de una norma real.
    visto = {}
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: f"/bin/{nombre}"
    )
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.subprocess.run",
        lambda argv, **kw: visto.update(kw)
        or subprocess.CompletedProcess(argv, 0, "ok", ""),
    )
    CliProvider(_config(preset="kimi")).generate(PROMPT)
    assert visto["env"]["PYTHONIOENCODING"] == "utf-8"
    assert visto["encoding"] == "utf-8"


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
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: "/bin/claude"
    )
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.subprocess.run",
        _Corrida(stdout="", stderr="se cayo el CLI", returncode=1),
    )
    with pytest.raises(ProviderError, match="se cayo el CLI"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_salida_vacia_avisa(monkeypatch):
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: "/bin/claude"
    )
    monkeypatch.setattr(
        "leyllana.engine.cli_provider.subprocess.run", _Corrida(stdout="   \n")
    )
    with pytest.raises(ProviderError, match="no devolvio texto"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


def test_timeout_se_reporta_como_error_de_proveedor(monkeypatch):
    def revienta(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr(
        "leyllana.engine.cli_provider.shutil.which", lambda nombre: "/bin/claude"
    )
    monkeypatch.setattr("leyllana.engine.cli_provider.subprocess.run", revienta)
    with pytest.raises(ProviderError, match="Fallo la llamada"):
        CliProvider(_config(preset="claude")).generate(PROMPT)


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
