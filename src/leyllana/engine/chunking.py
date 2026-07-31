"""Chunking de documentos largos para el map-reduce (ADR 0017).

Corta en limites naturales de la ley chilena (``Articulo``/``Titulo``/``Capitulo``/
``Parrafo``) agrupando articulos completos en trozos que caben en el contexto; si
una seccion sola es mas grande que el trozo, o el texto no tiene estructura, se cae
a un corte por tamano con solape. Todo es texto puro: no toca el modelo.
"""

from __future__ import annotations

import re

from ..types import ArticleChunk

# Estimacion conservadora de tokens desde caracteres (espanol, ~3.5 chars/token).
_CHARS_PER_TOKEN = 3.5

# Solape por defecto (en caracteres) del fallback por tamano, para no cortar una
# idea justo en el borde entre dos trozos.
_DEFAULT_OVERLAP = 200

# Marcadores de estructura al inicio de linea (tolerante a acentos y a "Art.").
# Se usa para el corte por tamano del map-reduce (``split_structural``), donde un
# limite de mas es inofensivo: solo mueve un borde entre trozos que igual se
# reagrupan por tamano.
_STRUCTURE_RE = re.compile(
    r"^[ \t]*(?:art[ií]culo|art\.|t[ií]tulo|cap[ií]tulo|p[áa]rrafo)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Marcador de APERTURA de articulo, mas estricto que ``_STRUCTURE_RE`` y sensible
# a mayusculas a proposito. Lo usa ``split_by_article``, cuyos trozos se rankean y
# se citan como "articulos clave": un trozo espurio ahi se convierte en una cita
# fabricada. BCN corta su texto a ~55 caracteres, de modo que una referencia
# cruzada envuelta ("...del\narticulo 30 bis, ...") caia al inicio de una linea y
# ``_STRUCTURE_RE`` la tomaba como un articulo nuevo (medido 2026-07-31: 6 trozos
# espurios de 47 bastaron para hacer fallar las tres corridas de la Ley 21.719).
# Dos senales distinguen una apertura real de una referencia envuelta:
#   - Mayuscula inicial: BCN abre cada articulo con "Articulo" en mayuscula; una
#     referencia envuelta conserva la minuscula de media oracion ("articulo 16.").
#   - Forma "Articulo <n> .-/.": el numero u ordinal va seguido de la marca ".-"
#     (o un punto), no de una continuacion ("Articulo 93 de la Constitucion...").
_ORDINAL = (
    r"(?:\d+|primero|segundo|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno|"
    r"d[eé]cimo)"
)
_SUFIJO = r"(?:bis|ter|qu[áa]ter|quinquies|sexies|septies|octies|nonies|decies)"
# La rama de articulo es sensible a mayusculas a proposito (la mayuscula es la
# senal). La rama de encabezado estructural va con flag ``(?i:...)`` acotado: no
# es fuente del defecto (las 7 referencias envueltas medidas eran "articulo") y
# BCN escribe los titulos en versalitas ("TITULO II"), asi que respetarlos exige
# ignorar la caja solo ahi. Sin esto se perderian encabezados reales.
_ARTICLE_OPEN_RE = re.compile(
    r"^[ \t]*(?:"
    rf"(?:Art[ií]culo|Art\.)[ \t]+{_ORDINAL}[ \t]*[º°]?[ \t]*(?:{_SUFIJO})?[ \t]*[.\-]"
    r"|"
    r"(?i:t[ií]tulo|cap[ií]tulo|p[áa]rrafo)\b"
    r")",
    re.MULTILINE,
)


def estimate_tokens(text: str) -> int:
    """Estima los tokens de ``text`` (aproximacion por caracteres)."""
    return int(len(text) / _CHARS_PER_TOKEN)


def chars_for_tokens(tokens: int) -> int:
    """Caracteres aproximados que caben en ``tokens`` (inverso de la estimacion)."""
    return int(tokens * _CHARS_PER_TOKEN)


def _split_by_size(text: str, max_chars: int, overlap: int) -> list[str]:
    """Corta ``text`` en ventanas de ``max_chars`` con ``overlap`` de solape."""
    if len(text) <= max_chars:
        return [text]
    step = max(1, max_chars - overlap)
    return [text[i : i + max_chars] for i in range(0, len(text), step)]


def _segments(text: str, marker: re.Pattern[str] = _STRUCTURE_RE) -> list[str]:
    """Parte ``text`` en segmentos que empiezan en cada ``marker`` de estructura."""
    starts = [m.start() for m in marker.finditer(text)]
    if not starts:
        return [text]
    # El preambulo antes del primer marcador es su propio segmento.
    bounds = ([0] if starts[0] != 0 else []) + starts + [len(text)]
    return [text[a:b] for a, b in zip(bounds, bounds[1:], strict=False) if text[a:b]]


def split_by_article(text: str) -> list[ArticleChunk]:
    """Devuelve un ``ArticleChunk`` por cada marcador estructural de ``text``.

    El preambulo antes del primer marcador (titulo de la ley, encabezado) no es un
    articulo direccionable y se descarta: no tiene sentido rankearlo ni citarlo como
    "articulo clave". Si ``text`` no tiene ningun marcador, devuelve una lista vacia.

    Corta con ``_ARTICLE_OPEN_RE``, mas estricto que el marcador del map-reduce: una
    referencia cruzada envuelta por el ajuste de linea de BCN no abre segmento, asi
    que su texto queda dentro del articulo que la contiene y no se rankea aparte.
    """
    chunks: list[ArticleChunk] = []
    for seg in _segments(text, _ARTICLE_OPEN_RE):
        stripped = seg.lstrip()
        if not _ARTICLE_OPEN_RE.match(stripped):
            continue
        label = stripped.splitlines()[0].strip()
        chunks.append(ArticleChunk(label=label, text=seg))
    return chunks


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


__all__ = ["ArticleChunk", "estimate_tokens", "chars_for_tokens", "split_by_article", "split_structural"]
