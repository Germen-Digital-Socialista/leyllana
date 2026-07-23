"""Contrato de proveedor: como el engine habla con cualquier backend LLM.

Un proveedor recibe un ``Prompt`` ya armado (con guardrail y disclaimer) y
devuelve texto crudo. No sabe de GUI ni de niveles; eso lo resuelven las capas
``prompt`` y ``engine``.
"""

from __future__ import annotations

from typing import Protocol

from ..prompt import Prompt


class ProviderError(RuntimeError):
    """El proveedor no pudo generar una respuesta.

    Cubre configuracion incompleta (falta binario o modelo), un ``llama-server``
    que no arranca o no responde, o una respuesta con forma inesperada. Se muestra
    al usuario en vez de continuar con texto invalido (ADR 0016).
    """


class Provider(Protocol):
    """Backend que convierte un ``Prompt`` en texto de respuesta."""

    def generate(self, prompt: Prompt) -> str:
        """Genera la respuesta del modelo para ``prompt``."""
        ...
