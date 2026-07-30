"""El registro de corridas: que anota, que nunca anota, y que no rompe nada."""

from __future__ import annotations

import json
import subprocess

import pytest

from leyllana import diagnostics
from leyllana.config import Config, EngineConfig, ModelConfig
from leyllana.engine.progress import Progress, Stage
from leyllana.engine.server import LlamaServer
from leyllana.gui.worker import ExplainWorker
from leyllana.types import Explanation, Nivel

_TEXTO = (
    "Articulo 1. Esta norma establece un deber de reportar en el plazo de "
    "tres horas contado desde el incidente."
)


@pytest.fixture(autouse=True)
def _apagar_al_terminar():
    """Ningun test deja el diagnostico encendido para el siguiente."""
    yield
    diagnostics.desactivar()


def _config(tmp_path):
    return Config(
        engine=EngineConfig(
            default_model=ModelConfig(path=str(tmp_path / "m.gguf"), ctx=8192),
            server_path=str(tmp_path / "llama-server.exe"),
        )
    )


def test_apagado_por_defecto():
    assert not diagnostics.activo()
    assert diagnostics.log_servidor() is None


def test_activar_crea_la_carpeta_y_nombra_el_log(tmp_path):
    destino = diagnostics.activar(tmp_path / "mediciones")
    assert destino.is_dir()
    assert diagnostics.activo()
    assert diagnostics.log_servidor() == destino / "llama-server.log"


def test_apagado_no_escribe_nada(tmp_path):
    registro = diagnostics.RunRecord("fuente", "publico", _config(tmp_path))
    registro.texto_resuelto(_TEXTO)
    assert registro.cerrar("ok") is None
    assert list(tmp_path.iterdir()) == []


def test_el_registro_guarda_los_hechos_y_la_configuracion(tmp_path):
    diagnostics.activar(tmp_path)
    registro = diagnostics.RunRecord(
        "https://ejemplo.cl/norma", "tecnico", _config(tmp_path)
    )
    registro.texto_resuelto(_TEXTO)
    registro.anotar(Progress(Stage.ANALIZANDO, fragmento=1, total=3))
    registro.anotar(Progress(Stage.ANALIZANDO, fragmento=2, total=3))
    destino = registro.cerrar("ok")

    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["resultado"] == "ok"
    assert datos["fuente"] == "https://ejemplo.cl/norma"
    assert datos["nivel"] == "tecnico"
    assert datos["caracteres"] == len(_TEXTO)
    # Un numero sin su configuracion al lado no sirve: por eso van juntos.
    assert datos["ctx"] == 8192
    assert datos["llamadas_map"] == 2
    assert datos["fragmentos_primer_nivel"] == 3
    assert datos["total_s"] >= 0


def test_el_registro_nunca_guarda_el_texto_del_documento(tmp_path):
    diagnostics.activar(tmp_path)
    registro = diagnostics.RunRecord("fuente", "publico", _config(tmp_path))
    registro.texto_resuelto(_TEXTO)
    crudo = registro.cerrar("ok").read_text(encoding="utf-8")
    assert "tres horas" not in crudo
    assert "deber de reportar" not in crudo
    assert "Articulo 1" not in crudo


def test_una_corrida_que_falla_tambien_queda_registrada(tmp_path):
    diagnostics.activar(tmp_path)
    registro = diagnostics.RunRecord("fuente", "publico", _config(tmp_path))
    datos = json.loads(
        registro.cerrar("fallo", error="ProviderError: sin modelo").read_text(
            encoding="utf-8"
        )
    )
    assert datos["resultado"] == "fallo"
    assert datos["error"] == "ProviderError: sin modelo"


def test_un_destino_no_escribible_no_tumba_la_corrida(tmp_path, monkeypatch):
    diagnostics.activar(tmp_path)
    registro = diagnostics.RunRecord("fuente", "publico", _config(tmp_path))

    def explotar(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr("pathlib.Path.write_text", explotar)
    assert registro.cerrar("ok") is None


# ------------------------------------------------- log del llama-server


def test_el_log_del_servidor_es_devnull_cuando_esta_apagado(tmp_path):
    srv = LlamaServer("bin.exe", "m.gguf", ctx=2048, gpu="cpu", threads=0)
    assert srv._abrir_log() is subprocess.DEVNULL


def test_el_log_del_servidor_se_abre_cuando_esta_encendido(tmp_path):
    diagnostics.activar(tmp_path)
    srv = LlamaServer("bin.exe", "m.gguf", ctx=2048, gpu="cpu", threads=0)
    salida = srv._abrir_log()
    assert salida is not subprocess.DEVNULL
    salida.write(b"linea del servidor\n")
    srv.stop()
    assert "linea del servidor" in (tmp_path / "llama-server.log").read_text(
        encoding="utf-8"
    )


# ------------------------------------------------- el worker de la GUI


class _ProveedorTonto:
    """Devuelve una respuesta con las cuatro secciones, sin modelo detras."""

    def generate(self, prompt, *, cancel=None):
        return (
            "Que hace: algo.\nA quien afecta: a alguien.\n"
            "Articulos clave: el 1.\nEn una frase: una frase.\n"
        )


def test_el_worker_registra_la_corrida(tmp_path, monkeypatch):
    diagnostics.activar(tmp_path)
    monkeypatch.setattr(
        "leyllana.gui.worker.resolve_with_source",
        lambda fuente: (_TEXTO, None),
    )
    worker = ExplainWorker(
        "paste:x", Nivel.PUBLICO, _config(tmp_path), provider=_ProveedorTonto()
    )
    resultados = []
    worker.terminado.connect(lambda exp, info: resultados.append(exp))
    worker.run()

    assert isinstance(resultados[0], Explanation)
    corridas = sorted(tmp_path.glob("corrida-*.json"))
    assert len(corridas) == 1
    datos = json.loads(corridas[0].read_text(encoding="utf-8"))
    assert datos["resultado"] == "ok"
    assert datos["caracteres"] == len(_TEXTO)
    # Las dos etapas que emite el propio worker antes de llamar al engine.
    etapas = [e["stage"] for e in datos["eventos"]]
    assert str(Stage.CARGANDO) in etapas
    assert str(Stage.EXTRAYENDO) in etapas
