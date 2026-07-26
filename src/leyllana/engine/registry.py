"""Seleccion de proveedor segun la config (ADR 0003).

Mapea ``config.engine.provider`` a un backend concreto. ``local`` es el default
(ADR 0005) y ``cli`` es el camino de nube por suscripcion (ADR 0018). Los
proveedores por API key siguen previstos (ADR 0004) pero no implementados.
"""

from __future__ import annotations

from ..config import Config
from .base import Provider
from .cli_provider import CliProvider
from .local import LocalProvider

# Proveedores de nube por API key (ADR 0004), aun no cableados. El camino de nube
# disponible hoy es por suscripcion via ``cli`` (ADR 0018).
_API_PROVIDERS = frozenset({"claude", "openai", "codex", "gemini"})


def get_provider(config: Config) -> Provider:
    """Devuelve el proveedor indicado por ``config.engine.provider``."""
    name = config.engine.provider.lower()
    if name == "local":
        return LocalProvider(config)
    if name == "cli":
        return CliProvider(config)
    if name in _API_PROVIDERS:
        raise NotImplementedError(
            f"Proveedor por API key {name!r} (opt-in, ADR 0004): aun no implementado. "
            "Para usar una suscripcion, use provider = 'cli' (ADR 0018)."
        )
    raise ValueError(f"Proveedor desconocido: {name!r}")


__all__ = ["get_provider"]
