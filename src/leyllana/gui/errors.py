"""Traduccion de las excepciones del engine a un aviso en espanol.

Misma escalera que ya usa la CLI en ``cli.py``, con las mismas palabras: si un
usuario compara lo que dice la ventana con lo que dijo la terminal, tiene que
leer lo mismo. Lo que cambia es el destino, un cuadro de dialogo en vez de
``stderr``.

Sin Qt: es una funcion pura y se prueba como tal.
"""

from __future__ import annotations

from ..engine import ConsentRequired, ParseError
from ..engine.base import ProviderError
from ..input.validation import ExtractionError


def mensaje(exc: BaseException) -> str:
    """Devuelve el texto a mostrar para ``exc``.

    El orden importa y sigue al de la CLI: las excepciones concretas primero, y
    ``ValueError``/``FileNotFoundError`` al final como red de seguridad. Nada de
    ``str(exc)`` a secas: sin el encabezado, un mensaje del engine aparece en la
    ventana sin decir de que tipo de problema se trata.
    """
    if isinstance(exc, ConsentRequired):
        return str(exc)
    if isinstance(exc, ExtractionError):
        return f"Entrada no utilizable: {exc}"
    if isinstance(exc, ParseError):
        return f"Respuesta del modelo no valida: {exc}"
    if isinstance(exc, NotImplementedError):
        return f"Funcionalidad aun no disponible: {exc}"
    if isinstance(exc, ProviderError):
        return f"No se pudo generar la explicacion: {exc}"
    if isinstance(exc, (FileNotFoundError, ValueError)):
        return f"Error: {exc}"
    return f"Error inesperado: {exc}"


__all__ = ["mensaje"]
