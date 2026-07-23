"""Contrato de proveedor: como el engine habla con cualquier backend LLM.

Un proveedor recibe un ``Prompt`` ya armado (con guardrail y disclaimer) y
devuelve texto crudo. No sabe de GUI ni de niveles; eso lo resuelven las capas
``prompt`` y ``engine``.
"""

from __future__ import annotations

from typing import Protocol

from ..prompt import Prompt


class Provider(Protocol):
    """Backend que convierte un ``Prompt`` en texto de respuesta."""

    def generate(self, prompt: Prompt) -> str:
        """Genera la respuesta del modelo para ``prompt``."""
        ...
