"""Proveedor local: modelo llama.cpp via ``llama-server`` (ADR 0003, 0016).

Mapea el ``Prompt`` (system + user) a un chat OpenAI-compatible contra un
``llama-server`` gestionado. La ejecucion viene de la config (ADR 0015); cual de
los modelos configurados se arranca lo decide ``select_model`` segun la memoria de
la maquina (ADR 0027), a menos que la config fije uno.
"""

from __future__ import annotations

import atexit

from ..config import Config
from ..prompt import Prompt
from .base import ProviderError
from .model_fit import live_memory_bytes, select_model
from .progress import CancelToken
from .server import LlamaServer, chat_completion, plan_offload


class LocalProvider:
    """Backend local llama.cpp. Implementa el Protocol ``Provider`` (engine.base)."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._server: LlamaServer | None = None
        # Que modelo se eligio y por que (ADR 0027). Se llena en ``_ensure_server``.
        self.model_report: str = ""

    def _ensure_server(self) -> str:
        """Crea (una vez) y arranca el ``llama-server`` del modelo elegido.

        Elige entre los modelos configurados el mas grande que entra en una
        fraccion segura de la memoria viva (ADR 0027): VRAM del dispositivo si la
        GPU esta activa (ADR 0023), o RAM total en CPU. Una eleccion fijada en la
        config gana.
        """
        if self._server is None:
            engine = self._config.engine
            if not engine.server_path:
                raise ProviderError(
                    "Configure engine.server_path (binario llama-server, ADR 0016)."
                )
            plan = plan_offload(engine.gpu, engine.server_path)
            live = live_memory_bytes(
                plan.device.total_mib if plan.device is not None else None
            )
            choice = select_model(engine, live)
            self.model_report = choice.report
            if not choice.model.path:
                raise ProviderError(
                    "Configure la ruta del modelo (engine.models.default.path)."
                )
            self._server = LlamaServer(
                engine.server_path,
                choice.model.path,
                ctx=choice.model.ctx,
                gpu=engine.gpu,
                threads=engine.threads,
                kv_cache_type=engine.kv_cache_type,
            )
            atexit.register(self._server.stop)
        return self._server.ensure()

    def generate(self, prompt: Prompt, *, cancel: CancelToken | None = None) -> str:
        """Genera la respuesta del modelo local para ``prompt``."""
        base = self._ensure_server()
        engine = self._config.engine
        messages = [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ]
        return chat_completion(
            base,
            messages,
            temperature=engine.temperature,
            max_tokens=engine.max_tokens,
            cancel=cancel,
        )

    def close(self) -> None:
        """Detiene el ``llama-server`` y libera la RAM del modelo.

        La CLI no lo necesita (el ``atexit`` de arriba basta para un proceso que
        termina), pero la GUI mantiene el proveedor vivo entre corridas y necesita
        poder soltarlo cuando cambia la config o se cierra la ventana.
        """
        if self._server is not None:
            self._server.stop()
            self._server = None


__all__ = ["LocalProvider"]
