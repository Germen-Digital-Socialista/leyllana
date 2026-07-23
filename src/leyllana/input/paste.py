"""Texto pegado: el camino de entrada mas simple.

No hay I/O ni red; solo normaliza el texto que el usuario pego o mando por stdin.
"""

from __future__ import annotations


def read_paste(text: str) -> str:
    """Devuelve el texto pegado, con espacios de borde recortados."""
    return text.strip()
