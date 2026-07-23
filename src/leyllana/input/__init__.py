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

PASTE_PREFIX = "paste:"


def resolve(source: str) -> str:
    """Resuelve ``source`` a texto crudo, ya validado (ADR 0006, ADR 0011).

    - ``paste:...``            -> texto pegado (todo lo que sigue al prefijo).
    - ``http://`` / ``https://`` -> fetch de URL oficial.
    - cualquier otra cosa      -> ruta de archivo local (.txt / .pdf).

    Antes de devolver, valida que el texto sea utilizable; si no lo es levanta
    ``ExtractionError`` en vez de pasar texto malo al engine (ADR 0011).
    """
    from .validation import validate_text

    if source.startswith(PASTE_PREFIX):
        from .paste import read_paste

        text = read_paste(source[len(PASTE_PREFIX) :])
    elif source.startswith(("http://", "https://")):
        from .url import fetch

        text = fetch(source)
    else:
        from .files import read_file

        text = read_file(source)

    return validate_text(text, source=source)


__all__ = ["resolve", "PASTE_PREFIX"]
