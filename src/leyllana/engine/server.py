"""Ejecucion del modelo local via el binario ``llama-server`` (ADR 0016).

En vez de un binding en proceso (``llama-cpp-python``, cuyas ruedas precompiladas
fallan en algunas CPU de gama baja), se arranca el ``llama-server`` oficial como
subproceso gestionado y se le habla por su API compatible con OpenAI
(``/v1/chat/completions``) con ``--jinja``, de modo que se aplica la plantilla de
chat propia del GGUF (correcta para Qwen3). Toda la comunicacion es a ``localhost``
con la biblioteca estandar (``urllib``): el backend de servidor no necesita
dependencias pip, solo el binario externo.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .base import ProviderError
from .progress import CancelToken

# El arranque en frio incluye cargar el GGUF; en CPU puede tardar (ADR 0015).
_HEALTH_TIMEOUT = 180.0
_REQUEST_TIMEOUT = 600.0
# Descarga "todo a GPU" cuando hay GPU; en un build CPU-only es inofensivo.
_GPU_ALL_LAYERS = 999


def _free_port() -> int:
    """Reserva un puerto libre de loopback para el ``llama-server``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def resolve_gpu_layers(gpu: str) -> int:
    """Traduce el modo de GPU (ADR 0012) a ``-ngl`` para ``llama-server``.

    ``cpu`` -> 0, ``gpu`` -> todas las capas, ``auto`` -> descarga a GPU si se
    detecta una NVIDIA (``nvidia-smi`` en el PATH) y si no, CPU. Nunca falla en una
    maquina sin GPU: cae a CPU.
    """
    mode = (gpu or "auto").lower()
    if mode == "cpu":
        return 0
    if mode == "gpu":
        return _GPU_ALL_LAYERS
    return _GPU_ALL_LAYERS if shutil.which("nvidia-smi") else 0


def _http_json(url: str, payload: dict | None = None, *, timeout: float) -> dict:
    """GET/POST JSON a ``localhost`` con ``urllib`` y devuelve el JSON parseado."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    method = "POST" if data is not None else "GET"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (loopback)
        return json.loads(resp.read().decode("utf-8"))


def chat_completion(
    base_url: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float = _REQUEST_TIMEOUT,
    cancel: CancelToken | None = None,
) -> str:
    """Llama ``/v1/chat/completions`` (no streaming) y devuelve el texto asistente.

    ``enable_thinking=False`` evita los bloques ``<think>`` que Qwen3 emite por
    defecto y que ensuciarian las cuatro secciones de salida.
    """
    payload = {
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        obj = _http_json(f"{base_url}/v1/chat/completions", payload, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"Fallo la llamada al modelo local: {exc}") from exc
    try:
        return obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Respuesta inesperada del llama-server.") from exc


class LlamaServer:
    """Un ``llama-server`` gestionado: arranca bajo demanda y se detiene al salir."""

    def __init__(
        self,
        binary_path: str,
        model_path: str,
        *,
        ctx: int,
        gpu: str,
        threads: int,
    ) -> None:
        self._binary = Path(binary_path)
        self._model = Path(model_path)
        self._ctx = ctx
        self._gpu = gpu
        self._threads = threads
        self._proc: subprocess.Popen | None = None
        self._base: str | None = None
        self._lock = threading.Lock()

    def ensure(self) -> str:
        """Arranca el servidor si hace falta, espera a que este sano y da su URL."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return self._base  # type: ignore[return-value]
            if not self._binary.exists():
                raise ProviderError(
                    f"No se encontro el binario llama-server: {self._binary}"
                )
            if not self._model.exists():
                raise ProviderError(f"No se encontro el modelo: {self._model}")

            port = _free_port()
            self._base = f"http://127.0.0.1:{port}"
            args = [
                str(self._binary),
                "-m", str(self._model),
                "--host", "127.0.0.1",
                "--port", str(port),
                "-c", str(self._ctx),
                "-ngl", str(resolve_gpu_layers(self._gpu)),
                "--jinja",
            ]
            if self._threads > 0:
                args += ["-t", str(self._threads)]
            # cwd = carpeta del binario: llama.cpp carga sus backends ggml-*.dll
            # (por CPU) relativos al ejecutable/cwd; asi se encuentran siempre.
            self._proc = subprocess.Popen(
                args,
                cwd=str(self._binary.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._wait_healthy()
            return self._base

    def _wait_healthy(self, timeout: float = _HEALTH_TIMEOUT) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise ProviderError("El llama-server termino durante el arranque.")
            try:
                obj = _http_json(f"{self._base}/health", timeout=2.0)
                if obj.get("status") == "ok":
                    return
            except Exception:  # noqa: BLE001 - aun arrancando; se reintenta
                pass
            time.sleep(0.5)
        raise ProviderError(f"El llama-server no quedo listo en {timeout:.0f}s.")

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 - forzar cierre si no termina
                self._proc.kill()


__all__ = ["LlamaServer", "chat_completion", "resolve_gpu_layers"]
