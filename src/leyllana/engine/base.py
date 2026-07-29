"""Contrato de proveedor: como el engine habla con cualquier backend LLM.

Un proveedor recibe un ``Prompt`` ya armado (con guardrail y disclaimer) y
devuelve texto crudo. No sabe de GUI ni de niveles; eso lo resuelven las capas
``prompt`` y ``engine``.
"""

from __future__ import annotations

from typing import Protocol

from ..prompt import Prompt
from .progress import CancelToken


class ProviderError(RuntimeError):
    """El proveedor no pudo generar una respuesta.

    Cubre configuracion incompleta (falta binario o modelo), un ``llama-server``
    que no arranca o no responde, o una respuesta con forma inesperada. Se muestra
    al usuario en vez de continuar con texto invalido (ADR 0016).
    """


class ConsentRequired(RuntimeError):
    """Falta el consentimiento explicito para enviar contenido a la nube (ADR 0013).

    Se levanta antes del primer envio. Elegir un proveedor de nube en la config no
    basta por si solo: cada corrida necesita una accion afirmativa del usuario, para
    que un ajuste olvidado nunca mande solo un documento fuera del equipo.
    """


class Provider(Protocol):
    """Backend que convierte un ``Prompt`` en texto de respuesta."""

    def generate(self, prompt: Prompt, *, cancel: CancelToken | None = None) -> str:
        """Genera la respuesta del modelo para ``prompt``.

        ``cancel`` es opcional y solo lo usa quien puede interrumpirse de verdad
        (el proveedor local lee la respuesta en streaming y corta entre tokens,
        ADR 0020). Un proveedor que no puede detenerse a media llamada lo ignora
        sin fingir que lo respeta.
        """
        ...
