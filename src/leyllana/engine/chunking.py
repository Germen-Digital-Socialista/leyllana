"""Chunking de documentos largos para el map-reduce (ADR 0017).

Corta en limites naturales de la ley chilena (``Articulo``/``Titulo``/``Capitulo``/
``Parrafo``) agrupando articulos completos en trozos que caben en el contexto; si
una seccion sola es mas grande que el trozo, o el texto no tiene estructura, se cae
a un corte por tamano con solape. Todo es texto puro: no toca el modelo.
"""

from __future__ import annotations

import re

# Estimacion conservadora de tokens desde caracteres (espanol, ~3.5 chars/token).
_CHARS_PER_TOKEN = 3.5

# Solape por defecto (en caracteres) del fallback por tamano, para no cortar una
# idea justo en el borde entre dos trozos.
_DEFAULT_OVERLAP = 200

# Marcadores de estructura al inicio de linea (tolerante a acentos y a "Art.").
_STRUCTURE_RE = re.compile(
    r"^[ \t]*(?:art[ií]culo|art\.|t[ií]tulo|cap[ií]tulo|p[áa]rrafo)\b",
    re.IGNORECASE | re.MULTILINE,
)


def estimate_tokens(text: str) -> int:
    """Estima los tokens de ``text`` (aproximacion por caracteres)."""
    return int(len(text) / _CHARS_PER_TOKEN)


def _split_by_size(text: str, max_chars: int, overlap: int) -> list[str]:
    """Corta ``text`` en ventanas de ``max_chars`` con ``overlap`` de solape."""
    if len(text) <= max_chars:
        return [text]
    step = max(1, max_chars - overlap)
    return [text[i : i + max_chars] for i in range(0, len(text), step)]


def _segments(text: str) -> list[str]:
    """Parte ``text`` en segmentos que empiezan en cada marcador de estructura."""
    starts = [m.start() for m in _STRUCTURE_RE.finditer(text)]
    if not starts:
        return [text]
    # El preambulo antes del primer marcador es su propio segmento.
    bounds = ([0] if starts[0] != 0 else []) + starts + [len(text)]
    return [text[a:b] for a, b in zip(bounds, bounds[1:], strict=False) if text[a:b]]


def split_structural(
    text: str, *, max_chars: int, overlap: int = _DEFAULT_OVERLAP
) -> list[str]:
    """Divide ``text`` en trozos de a lo mas ``max_chars`` caracteres (ADR 0017).

    Prefiere cortar en limites de la ley chilena y agrupa segmentos consecutivos
    mientras quepan; un segmento mas grande que ``max_chars`` se parte por tamano
    con solape. Cada trozo devuelto mide a lo mas ``max_chars``.
    """
    if len(text) <= max_chars:
        return [text]

    # Segmentos por estructura; cada uno acotado a max_chars por si es enorme.
    pieces: list[str] = []
    for seg in _segments(text):
        pieces.extend(_split_by_size(seg, max_chars, overlap))

    # Agrupacion glotona: unir segmentos consecutivos mientras el total quepa.
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks


__all__ = ["estimate_tokens", "split_structural"]
