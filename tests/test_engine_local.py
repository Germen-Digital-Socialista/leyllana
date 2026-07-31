"""Tests del proveedor local (llama-server subprocess, ADR 0016).

Todo hermetico: se monkeypatchea la llamada HTTP y el arranque del servidor, asi
que estos tests corren sin binario ni modelo. El arranque real del servidor se
prueba aparte (test_engine_smoke.py), gated a la presencia de binario+modelo.
"""

import json
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


def test_resolve_gpu_auto_uses_device_list(monkeypatch):
    # ADR 0023: "auto" pregunta al binario que dispositivos ve, en vez de adivinar
    # por la presencia de nvidia-smi (que no dice nada del backend compilado).
    monkeypatch.setattr(
        server_mod, "probe_devices",
        lambda binary: [server_mod.Device("CUDA0", "X", 8192, 8000)],
    )
    assert server_mod.resolve_gpu_layers("auto", "srv") == 999
    monkeypatch.setattr(server_mod, "probe_devices", lambda binary: [])
    assert server_mod.resolve_gpu_layers("auto", "srv") == 0


# --- Parseo de la lista de dispositivos (ADR 0023) --------------------------

def test_parse_device_list_empty():
    # Un build CPU-only imprime la cabecera y nada mas (verificado en b9929).
    assert server_mod.parse_device_list("Available devices:\n") == []


def test_parse_device_list_cuda():
    out = "Available devices:\n  CUDA0: NVIDIA GeForce RTX 5060 (7708 MiB, 7573 MiB free)\n"
    assert server_mod.parse_device_list(out) == [
        server_mod.Device("CUDA0", "NVIDIA GeForce RTX 5060", 7708, 7573)
    ]


def test_parse_device_list_name_with_parentheses():
    # El nombre del dispositivo puede traer parentesis: hay que anclar en el grupo
    # final "(N MiB, N MiB free)", no en el primer parentesis.
    out = "Available devices:\n  Vulkan0: Intel(R) Graphics (ARL) (11577 MiB, 8251 MiB free)\n"
    assert server_mod.parse_device_list(out) == [
        server_mod.Device("Vulkan0", "Intel(R) Graphics (ARL)", 11577, 8251)
    ]


def test_parse_device_list_multiple():
    out = (
        "Available devices:\n"
        "  CUDA0: NVIDIA GeForce RTX 5060 (7708 MiB, 7573 MiB free)\n"
        "  Vulkan0: Intel(R) Graphics (ARL) (11577 MiB, 8251 MiB free)\n"
    )
    devs = server_mod.parse_device_list(out)
    assert [d.id for d in devs] == ["CUDA0", "Vulkan0"]


def test_parse_device_list_ignores_init_noise():
    # Las lineas de init de ggml ("Device 0: ..., compute capability ...") no traen
    # el sufijo de memoria y no deben contarse como dispositivos.
    out = (
        "ggml_cuda_init: found 1 CUDA devices:\n"
        "  Device 0: NVIDIA GeForce RTX 5060, compute capability 12.0, VMM: yes\n"
        "Available devices:\n"
        "  CUDA0: NVIDIA GeForce RTX 5060 (7708 MiB, 7573 MiB free)\n"
    )
    assert server_mod.parse_device_list(out) == [
        server_mod.Device("CUDA0", "NVIDIA GeForce RTX 5060", 7708, 7573)
    ]


# --- Decision de descarga a GPU (ADR 0023) ----------------------------------

def test_plan_offload_cpu_does_not_probe(monkeypatch):
    def boom(binary):
        raise AssertionError("cpu no debe consultar dispositivos")

    monkeypatch.setattr(server_mod, "probe_devices", boom)
    plan = server_mod.plan_offload("cpu", "srv")
    assert plan.ngl == 0
    assert plan.device is None


def test_plan_offload_gpu_forced_does_not_probe(monkeypatch):
    # Fill-only (ADR 0027): una eleccion explicita del usuario no se verifica ni se
    # segundo-adivina. "gpu" forzado pasa -ngl 999 sin consultar el dispositivo.
    llamadas = []
    monkeypatch.setattr(server_mod, "probe_devices", lambda binary: llamadas.append(binary) or [])
    plan = server_mod.plan_offload("gpu", "srv")
    assert plan.ngl == 999
    assert llamadas == []


def test_plan_offload_auto_with_device(monkeypatch):
    dev = server_mod.Device("Vulkan0", "Intel(R) Graphics", 11577, 8251)
    monkeypatch.setattr(server_mod, "probe_devices", lambda binary: [dev])
    plan = server_mod.plan_offload("auto", "srv")
    assert plan.ngl == 999
    assert plan.device == dev
    assert "Vulkan0" in plan.report


def test_plan_offload_auto_no_device_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(server_mod, "probe_devices", lambda binary: [])
    plan = server_mod.plan_offload("auto", "srv")
    assert plan.ngl == 0
    assert plan.device is None


# --- probe_devices: subprocess + cache (ADR 0023) ---------------------------

class _FakeProc:
    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = 0


def test_probe_devices_parses_binary_output(monkeypatch):
    out = "Available devices:\n  CUDA0: NVIDIA GeForce RTX 5060 (7708 MiB, 7573 MiB free)\n"
    monkeypatch.setattr(server_mod.subprocess, "run", lambda *a, **k: _FakeProc(stdout=out))
    server_mod._device_cache.clear()
    devs = server_mod.probe_devices("srv-parse")
    assert devs == [server_mod.Device("CUDA0", "NVIDIA GeForce RTX 5060", 7708, 7573)]


def test_probe_devices_empty_on_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("no se pudo ejecutar")

    monkeypatch.setattr(server_mod.subprocess, "run", boom)
    server_mod._device_cache.clear()
    assert server_mod.probe_devices("srv-boom") == []


def test_probe_devices_caches_per_binary(monkeypatch):
    llamadas = []

    def run(*a, **k):
        llamadas.append(1)
        return _FakeProc(stdout="Available devices:\n")

    monkeypatch.setattr(server_mod.subprocess, "run", run)
    server_mod._device_cache.clear()
    server_mod.probe_devices("srv-cache")
    server_mod.probe_devices("srv-cache")
    assert len(llamadas) == 1


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


def test_ensure_server_runs_the_selected_model(monkeypatch):
    # ADR 0027: el modelo que arranca es el que elige select_model (aqui, el
    # fallback por memoria justa), no siempre el default.
    from leyllana.engine import model_fit
    from leyllana.engine.server import OffloadPlan

    cfg = Config(
        engine=EngineConfig(
            server_path="srv",
            default_model=ModelConfig(path="big.gguf", ctx=4096),
            fallback_model=ModelConfig(path="small.gguf", ctx=2048),
        )
    )
    prov = LocalProvider(cfg)

    monkeypatch.setattr(
        "leyllana.engine.local.plan_offload",
        lambda gpu, binary: OffloadPlan(0, None, "CPU"),
    )
    elegido = model_fit.ModelChoice(
        cfg.engine.fallback_model, "fallback", "memoria justa", True
    )
    monkeypatch.setattr(
        "leyllana.engine.local.select_model", lambda engine, live: elegido
    )

    captured = {}

    def fake_server(binary, model_path, *, ctx, gpu, threads, kv_cache_type):
        captured.update(model_path=model_path, ctx=ctx)

        class _S:
            def ensure(self):
                return "http://fake"

            def stop(self):
                pass

        return _S()

    monkeypatch.setattr("leyllana.engine.local.LlamaServer", fake_server)

    prov._ensure_server()
    assert captured["model_path"] == "small.gguf"
    assert captured["ctx"] == 2048
    assert prov.model_report == "memoria justa"


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


def test_ensure_appends_extra_args(monkeypatch, tmp_path):
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(server_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(
        str(binary), str(model), ctx=2048, gpu="cpu", threads=0,
        extra_args=("--reranking", "--pooling", "rank"),
    )
    srv.ensure()
    assert captured["args"][-3:] == ["--reranking", "--pooling", "rank"]


def test_ensure_without_extra_args_unchanged(monkeypatch, tmp_path):
    # Los llamadores existentes (LocalProvider) no pasan extra_args: el argv no
    # debe cambiar para ellos.
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(server_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(str(binary), str(model), ctx=2048, gpu="cpu", threads=0)
    srv.ensure()
    assert captured["args"][-1] == "--jinja"


def test_ensure_records_device_report(monkeypatch, tmp_path):
    # ADR 0023: el motor registra en que dispositivo quedo y por que, en vez de
    # absorber en silencio una caida de GPU a CPU.
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(server_mod.subprocess, "Popen", lambda args, **k: FakeProc())
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)
    monkeypatch.setattr(server_mod, "probe_devices", lambda binary: [])

    srv = server_mod.LlamaServer(str(binary), str(model), ctx=2048, gpu="auto", threads=0)
    srv.ensure()
    assert srv.device_report  # cadena no vacia
    assert srv.device is None


def test_ensure_appends_kv_cache_type_when_set(monkeypatch, tmp_path):
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(server_mod.subprocess, "Popen", lambda args, **k: captured.update(args=args) or FakeProc())
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(
        str(binary), str(model), ctx=2048, gpu="cpu", threads=0, kv_cache_type="q8_0"
    )
    srv.ensure()
    args = captured["args"]
    assert args[args.index("-ctk") + 1] == "q8_0"
    assert args[args.index("-ctv") + 1] == "q8_0"


def test_ensure_omits_kv_flags_for_default_f16(monkeypatch, tmp_path):
    # f16 es el default de llama.cpp: no hace falta pasar -ctk/-ctv, y no pasarlos
    # mantiene el argv de los llamadores existentes sin cambios.
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(server_mod.subprocess, "Popen", lambda args, **k: captured.update(args=args) or FakeProc())
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(str(binary), str(model), ctx=2048, gpu="cpu", threads=0)
    srv.ensure()
    assert "-ctk" not in captured["args"]
    assert "-ctv" not in captured["args"]


def test_rerank_returns_scores_in_input_order(monkeypatch):
    payload = {
        "results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.2},
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(
        server_mod.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse()
    )
    scores = server_mod.rerank("http://fake", "query", ["doc a", "doc b"])
    assert scores == [0.2, 0.9]


def test_rerank_wraps_network_errors(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("caido")

    monkeypatch.setattr(server_mod.urllib.request, "urlopen", boom)
    with pytest.raises(ProviderError, match="reranker"):
        server_mod.rerank("http://fake", "q", ["a"])


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


def test_explain_uses_isolation_for_publico_local_provider(monkeypatch):
    # Ley corta (bajo el tope): select_key_articles devuelve todo sin rankear.
    # PUBLICO+local arma "Articulos clave" articulo por articulo (aislamiento): una
    # llamada de resumen (tres secciones) y una de gloss por articulo, en vez del
    # build_with_selection conjunto que atribuia mal el numero (ROADMAP After-number).
    canned = (
        "Que hace: regula algo.\n"
        "A quien afecta: a los organismos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    calls = []

    def fake_chat(base, messages, *, temperature, max_tokens, **kwargs):
        calls.append(messages)
        return canned

    monkeypatch.setattr("leyllana.engine.local.chat_completion", fake_chat)
    monkeypatch.setattr(LocalProvider, "_ensure_server", lambda self: "http://fake")

    texto = "Articulo 1. Regula el uso de sistemas de IA por organismos publicos."
    exp = explain(texto, Nivel.PUBLICO, _local_cfg())

    assert isinstance(exp, Explanation)
    systems = [m[0]["content"] for m in calls]
    users = [m[1]["content"] for m in calls]
    assert any("tres secciones" in s for s in systems)  # hubo llamada de resumen
    assert any("Articulo a explicar" in u for u in users)  # hubo gloss por articulo
    assert all("Articulos preseleccionados" not in u for u in users)  # no el viejo
    assert "Articulo 1" in exp.articulos_clave  # numero estampado por el pipeline


def test_explain_tecnico_still_uses_plain_build(monkeypatch):
    # TECNICO no pasa por la seleccion (no tiene tope) -- sigue usando build().
    canned = (
        "Que hace: regula algo.\n"
        "A quien afecta: a los organismos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    captured = {}

    def fake_chat(base, messages, *, temperature, max_tokens, **kwargs):
        captured["messages"] = messages
        return canned

    monkeypatch.setattr("leyllana.engine.local.chat_completion", fake_chat)
    monkeypatch.setattr(LocalProvider, "_ensure_server", lambda self: "http://fake")

    explain("Articulo 1. Texto.", Nivel.TECNICO, _local_cfg())
    user_msg = captured["messages"][1]["content"]
    assert "Articulos preseleccionados" not in user_msg
