"""Tests del proveedor local (llama-server subprocess, ADR 0016).

Todo hermetico: se monkeypatchea la llamada HTTP y el arranque del servidor, asi
que estos tests corren sin binario ni modelo. El arranque real del servidor se
prueba aparte (test_engine_smoke.py), gated a la presencia de binario+modelo.
"""

import urllib.error

import pytest

from leyllana.config import Config, EngineConfig, ModelConfig
from leyllana.engine import explain
from leyllana.engine import server as server_mod
from leyllana.engine.base import ProviderError
from leyllana.engine.local import LocalProvider
from leyllana.prompt import Prompt
from leyllana.types import Explanation, Nivel


def _local_cfg(**engine_kwargs):
    engine_kwargs.setdefault("server_path", "srv")
    engine_kwargs.setdefault("default_model", ModelConfig(path="m.gguf"))
    return Config(engine=EngineConfig(**engine_kwargs))


def test_resolve_gpu_cpu_and_gpu():
    assert server_mod.resolve_gpu_layers("cpu") == 0
    assert server_mod.resolve_gpu_layers("gpu") == 999


def test_resolve_gpu_auto_detects_nvidia(monkeypatch):
    monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    assert server_mod.resolve_gpu_layers("auto") == 999
    monkeypatch.setattr(server_mod.shutil, "which", lambda name: None)
    assert server_mod.resolve_gpu_layers("auto") == 0


# La lectura de la respuesta paso a ser en streaming (ADR 0020) y se prueba
# entera en test_streaming.py: tramas SSE, trama rota, cancelacion y respuesta
# vacia. Aqui queda lo propio de este modulo: el arranque del servidor.


def test_health_check_usa_http_json(monkeypatch):
    # _http_json quedo solo para el /health del arranque; el chat ya no pasa por
    # ahi. Si alguien lo borra por "no usado", esto lo delata.
    llamadas = []
    monkeypatch.setattr(
        server_mod,
        "_http_json",
        lambda url, payload=None, *, timeout: llamadas.append(url)
        or {"status": "ok"},
    )
    srv = server_mod.LlamaServer("srv", "m.gguf", ctx=2048, gpu="cpu", threads=0)
    srv._base = "http://fake"
    srv._wait_healthy(timeout=1.0)
    assert llamadas == ["http://fake/health"]


def test_health_check_agotado_avisa(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.URLError("aun arrancando")

    monkeypatch.setattr(server_mod, "_http_json", boom)
    srv = server_mod.LlamaServer("srv", "m.gguf", ctx=2048, gpu="cpu", threads=0)
    srv._base = "http://fake"
    with pytest.raises(ProviderError, match="no quedo listo"):
        srv._wait_healthy(timeout=0.1)


def test_generate_builds_messages_and_returns_content(monkeypatch):
    prov = LocalProvider(_local_cfg(temperature=0.3, max_tokens=512))
    monkeypatch.setattr(prov, "_ensure_server", lambda: "http://fake")
    captured = {}

    def fake_chat(base, messages, *, temperature, max_tokens, **kwargs):
        captured.update(base=base, messages=messages, temperature=temperature,
                        max_tokens=max_tokens)
        return "respuesta del modelo"

    monkeypatch.setattr("leyllana.engine.local.chat_completion", fake_chat)
    out = prov.generate(Prompt(system="SYS", user="USR"))
    assert out == "respuesta del modelo"
    assert captured["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 512


def test_generate_without_server_path_raises():
    cfg = Config(engine=EngineConfig(default_model=ModelConfig(path="m.gguf")))
    with pytest.raises(ProviderError):
        LocalProvider(cfg).generate(Prompt(system="s", user="u"))


def test_generate_without_model_path_raises():
    cfg = Config(engine=EngineConfig(server_path="srv"))
    with pytest.raises(ProviderError):
        LocalProvider(cfg).generate(Prompt(system="s", user="u"))


def test_server_missing_binary_raises(tmp_path):
    srv = server_mod.LlamaServer(
        str(tmp_path / "no-existe.exe"), str(tmp_path / "m.gguf"),
        ctx=2048, gpu="cpu", threads=0,
    )
    with pytest.raises(ProviderError):
        srv.ensure()


def test_server_missing_model_raises(tmp_path):
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    srv = server_mod.LlamaServer(
        str(binary), str(tmp_path / "no-existe.gguf"),
        ctx=2048, gpu="cpu", threads=0,
    )
    with pytest.raises(ProviderError):
        srv.ensure()


def test_explain_local_end_to_end_parsed(monkeypatch):
    canned = (
        "Que hace: regula el uso de IA.\n"
        "A quien afecta: a los organismos publicos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    monkeypatch.setattr("leyllana.engine.local.chat_completion", lambda *a, **k: canned)
    monkeypatch.setattr(LocalProvider, "_ensure_server", lambda self: "http://fake")
    exp = explain("texto de una ley", Nivel.PUBLICO, _local_cfg())
    assert isinstance(exp, Explanation)
    assert exp.que_hace == "regula el uso de IA."
    assert exp.en_una_frase == "una ley sobre IA."
