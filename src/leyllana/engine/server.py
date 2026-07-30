"""Ejecucion del modelo local via el binario ``llama-server`` (ADR 0016).

En vez de un binding en proceso (``llama-cpp-python``, cuyas ruedas precompiladas
fallan en algunas CPU de gama baja), se arranca el ``llama-server`` oficial como
subproceso gestionado y se le habla por su API compatible con OpenAI
(``/v1/chat/completions``) con ``--jinja``, de modo que se aplica la plantilla de
chat propia del GGUF (correcta para Qwen3). Toda la comunicacion es a ``localhost``
con la biblioteca estandar (``urllib``): el backend de servidor no necesita
dependencias pip, solo el binario externo.

La respuesta se lee **en streaming** (ADR 0020). Con la llamada de una sola pieza
que habia antes, una corrida de 50 minutos no se podia interrumpir en absoluto:
el proceso quedaba bloqueado en un ``urlopen`` hasta el timeout. Leyendo el flujo
token a token se puede mirar la senal de cancelacion entre uno y otro, que es lo
que hace que el boton Cancelar de la GUI signifique algo (PRD FR-10).
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
from collections.abc import Callable
from pathlib import Path

from .base import ProviderError
from .progress import Cancelled, CancelToken

# El arranque en frio incluye cargar el GGUF; en CPU puede tardar (ADR 0015).
_HEALTH_TIMEOUT = 180.0
_REQUEST_TIMEOUT = 600.0
# Descarga "todo a GPU" cuando hay GPU; en un build CPU-only es inofensivo.
_GPU_ALL_LAYERS = 999
# Marca de fin del flujo SSE en la API compatible con OpenAI.
_SSE_DONE = "[DONE]"


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


def sse_delta(line: bytes | str) -> str | None:
    """Extrae el trozo de texto de una linea SSE, o ``None`` si no trae ninguno.

    Devuelve ``None`` para las lineas en blanco que separan eventos, para la marca
    de fin, y para cualquier trama que no se pueda leer. Una trama rota se salta en
    silencio en vez de tumbar la corrida: el flujo sigue y lo que se pierde es un
    token, no la explicacion entera.
    """
    texto = line.decode("utf-8", "replace") if isinstance(line, bytes) else line
    texto = texto.strip()
    if not texto.startswith("data:"):
        return None
    cuerpo = texto[len("data:") :].strip()
    if not cuerpo or cuerpo == _SSE_DONE:
        return None
    try:
        obj = json.loads(cuerpo)
        return obj["choices"][0]["delta"].get("content") or None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
        return None


def chat_completion(
    base_url: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float = _REQUEST_TIMEOUT,
    cancel: CancelToken | None = None,
    on_token: Callable[[str], None] | None = None,
) -> str:
    """Llama ``/v1/chat/completions`` en streaming y devuelve el texto completo.

    Lee la respuesta trama a trama y consulta ``cancel`` entre una y otra, asi que
    cancelar corta en el siguiente token en vez de esperar al final. La unica
    ventana en que no responde de inmediato es el procesado del prompt, antes del
    primer token: ahi todavia no llega nada que leer. Se dice aqui porque un boton
    que promete detener algo y no lo hace es peor que no tenerlo.

    ``on_token`` recibe cada trozo segun llega, para un indicador vivo.
    ``enable_thinking=False`` evita los bloques ``<think>`` que Qwen3 emite por
    defecto y que ensuciarian las cuatro secciones de salida.
    """
    payload = {
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    partes: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            for linea in resp:
                if cancel is not None and cancel.is_cancelled():
                    # Salir del ``with`` cierra la conexion, y el llama-server deja
                    # de generar al perder al cliente.
                    raise Cancelled("La explicacion fue cancelada por el usuario.")
                trozo = sse_delta(linea)
                if trozo is None:
                    continue
                partes.append(trozo)
                if on_token is not None:
                    on_token(trozo)
    except Cancelled:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"Fallo la llamada al modelo local: {exc}") from exc

    if not partes:
        raise ProviderError("El llama-server no devolvio texto.")
    return "".join(partes)


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
        self._log = None

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
            # El log del servidor es lo unico que dice que dispositivos vio, cuantas
            # capas descargo, cuantos tokens tenia el prompt de verdad y si rechazo
            # la peticion. Descartarlo dejaba esas preguntas sin respuesta posible,
            # asi que con el diagnostico encendido se guarda (ADR 0023).
            salida = self._abrir_log()
            # cwd = carpeta del binario: llama.cpp carga sus backends ggml-*.dll
            # (por CPU) relativos al ejecutable/cwd; asi se encuentran siempre.
            self._proc = subprocess.Popen(
                args,
                cwd=str(self._binary.parent),
                stdout=salida,
                stderr=salida,
            )
            self._wait_healthy()
            return self._base

    def _abrir_log(self):
        """Destino de la salida del servidor: un archivo si hay, DEVNULL si no.

        Devuelve DEVNULL cuando el diagnostico esta apagado, que es el
        comportamiento por defecto, y tambien si el archivo no se puede abrir: un
        log que no se puede escribir no debe impedir que el modelo corra.
        """
        from ..diagnostics import log_servidor

        destino = log_servidor()
        if destino is None:
            return subprocess.DEVNULL
        try:
            self._log = destino.open("ab")
        except OSError:
            return subprocess.DEVNULL
        return self._log

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
        if self._log is not None:
            self._log.close()
            self._log = None


__all__ = ["LlamaServer", "chat_completion", "resolve_gpu_layers"]
