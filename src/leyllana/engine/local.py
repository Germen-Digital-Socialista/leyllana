"""Proveedor local llama.cpp (ADR 0003), stub de Fase 1.

Modelo Qwen ligero. CPU como base, con GPU opcional cuando esta presente
(ADR 0012). ``llama_cpp`` se importa de forma perezosa dentro de ``generate``;
el esqueleto no carga ningun modelo ni requiere la dependencia instalada.
"""

from __future__ import annotations

from ..config import Config
from ..prompt import Prompt


class LocalProvider:
    """Backend local llama.cpp. Implementa el Protocol ``Provider`` (engine.base)."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def generate(self, prompt: Prompt) -> str:
        """Genera la respuesta con el modelo local. (Fase 1: por implementar.)"""
        raise NotImplementedError(
            "Proveedor local llama.cpp (extra `engine`): se implementa en Fase 1."
        )


__all__ = ["LocalProvider"]
