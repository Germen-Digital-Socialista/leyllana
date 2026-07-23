"""Proveedor local: modelo llama.cpp via ``llama-server`` (ADR 0003, 0016).

Mapea el ``Prompt`` (system + user) a un chat OpenAI-compatible contra un
``llama-server`` gestionado. Modelo por defecto y ejecucion vienen de la config
(ADR 0015); la seleccion automatica por RAM del fallback queda para mas adelante.
"""

from __future__ import annotations

import atexit

from ..config import Config
from ..prompt import Prompt
from .base import ProviderError
from .server import LlamaServer, chat_completion


class LocalProvider:
    """Backend local llama.cpp. Implementa el Protocol ``Provider`` (engine.base)."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._server: LlamaServer | None = None

    def _ensure_server(self) -> str:
        """Crea (una vez) y arranca el ``llama-server`` del modelo por defecto."""
        if self._server is None:
            engine = self._config.engine
            model = engine.default_model
            if not engine.server_path:
                raise ProviderError(
                    "Configure engine.server_path (binario llama-server, ADR 0016)."
                )
            if not model.path:
                raise ProviderError(
                    "Configure la ruta del modelo (engine.models.default.path)."
                )
            self._server = LlamaServer(
                engine.server_path,
                model.path,
                ctx=model.ctx,
                gpu=engine.gpu,
                threads=engine.threads,
            )
            atexit.register(self._server.stop)
        return self._server.ensure()

    def generate(self, prompt: Prompt) -> str:
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
        )


__all__ = ["LocalProvider"]
