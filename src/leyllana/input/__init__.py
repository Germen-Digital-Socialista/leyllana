"""Capa de entrada: resuelve una fuente a texto crudo.

No sabe nada del engine; solo devuelve texto (ADR 0006). Tres caminos desde v1:

1. Archivo local — ``.txt`` directo, ``.pdf`` via PyMuPDF.
2. Texto pegado — prefijo ``paste:`` o texto directo.
3. URL — fuente oficial (BCN/leychile, Senado/Camara).

``resolve`` despacha segun la forma de ``source``. Este es el unico limite donde
mas adelante vivira un toque de red (el fetch de URL); nada de red corre al
importar (ADR 0005).
"""

from __future__ import annotations

from ..types import SourceInfo

PASTE_PREFIX = "paste:"


def resolve_with_source(source: str) -> tuple[str, SourceInfo]:
    """Resuelve ``source`` a ``(texto, SourceInfo)``, validado (ADR 0006, 0011, FR-7.1).

    - ``paste:...``              -> texto pegado; sin procedencia (info vacia).
    - ``http://`` / ``https://`` -> fetch de URL oficial (texto + metadatos).
    - cualquier otra cosa        -> archivo local (.txt sin metadatos; .pdf con ellos).

    Antes de devolver, valida que el texto sea utilizable; si no lo es levanta
    ``ExtractionError`` en vez de pasar texto malo al engine (ADR 0011). Los
    metadatos de la fuente se capturan en el mismo fetch/apertura: nunca se inventan
    (ADR 0008) y un campo ausente queda en ``None``.
    """
    from .validation import validate_text

    if source.startswith(PASTE_PREFIX):
        from .paste import read_paste

        text = read_paste(source[len(PASTE_PREFIX) :])
        info = SourceInfo()
    elif source.startswith(("http://", "https://")):
        from .url import fetch_with_source

        text, info = fetch_with_source(source)
    else:
        from .files import read_file_with_source

        text, info = read_file_with_source(source)

    return validate_text(text, source=source), info


def resolve(source: str) -> str:
    """Resuelve ``source`` a texto crudo, ya validado (ADR 0006, ADR 0011)."""
    return resolve_with_source(source)[0]


__all__ = ["resolve", "resolve_with_source", "PASTE_PREFIX"]
