"""Seleccion de proveedor segun la config (ADR 0003).

Mapea ``config.engine.provider`` a un backend concreto. ``local`` es el unico
cableado en el esqueleto; los proveedores de nube (ADR 0004) son opt-in y llegan
en Fase 2.
"""

from __future__ import annotations

from ..config import Config
from .base import Provider
from .local import LocalProvider

# Proveedores de nube previstos (ADR 0004), aun no cableados (Fase 2).
_CLOUD_PROVIDERS = frozenset({"claude", "openai", "codex", "gemini"})


def get_provider(config: Config) -> Provider:
    """Devuelve el proveedor indicado por ``config.engine.provider``."""
    name = config.engine.provider.lower()
    if name == "local":
        return LocalProvider(config)
    if name in _CLOUD_PROVIDERS:
        raise NotImplementedError(
            f"Proveedor de nube {name!r} (opt-in, ADR 0004): se implementa en Fase 2."
        )
    raise ValueError(f"Proveedor desconocido: {name!r}")


__all__ = ["get_provider"]
