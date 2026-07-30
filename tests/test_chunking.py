"""Tests del chunking estructura-aware para el map-reduce (ADR 0017).

Funciones puras: sin modelo ni red. Cubren la estimacion de tokens, el corte por
limites de la ley chilena (Articulo/Titulo/Capitulo) y el fallback por tamano.
"""

from leyllana.engine.chunking import ArticleChunk, estimate_tokens, split_by_article, split_structural


def test_split_by_article_one_chunk_per_articulo():
    text = (
        "Articulo 1. Texto uno.\n"
        "Articulo 2. Texto dos.\n"
        "Articulo 3. Texto tres.\n"
    )
    chunks = split_by_article(text)
    assert len(chunks) == 3
    assert all(isinstance(c, ArticleChunk) for c in chunks)
    assert chunks[0].label.lower().startswith("articulo 1")
    assert chunks[1].label.lower().startswith("articulo 2")
    assert "Texto uno." in chunks[0].text


def test_split_by_article_skips_preamble():
    # El preambulo (titulo de la ley antes del primer Articulo) no es un articulo
    # direccionable: no debe aparecer como su propio ArticleChunk.
    text = "Ley 21.663 sobre ciberseguridad.\nArticulo 1. Objeto de la ley.\n"
    chunks = split_by_article(text)
    assert len(chunks) == 1
    assert "Ley 21.663" not in chunks[0].text


def test_split_by_article_no_markers_returns_empty():
    chunks = split_by_article("texto sin estructura ni articulos")
    assert chunks == []


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 350) == 100  # ~3.5 chars/token


def test_split_returns_single_chunk_when_small():
    text = "Articulo 1. Texto breve."
    assert split_structural(text, max_chars=1000) == [text]


def test_split_breaks_at_article_boundaries():
    text = (
        "Articulo 1. " + "a" * 60 + "\n"
        "Articulo 2. " + "b" * 60 + "\n"
        "Articulo 3. " + "c" * 60 + "\n"
    )
    chunks = split_structural(text, max_chars=90)
    # cada articulo (~72 chars) no cabe junto a otro en 90 -> un articulo por chunk
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk.lstrip().lower().startswith("articulo")


def test_split_groups_articles_up_to_max():
    text = (
        "Articulo 1. corto uno.\n"
        "Articulo 2. corto dos.\n"
        "Articulo 3. corto tres.\n"
    )
    chunks = split_structural(text, max_chars=1000)
    assert len(chunks) == 1  # todos caben juntos
    assert "Articulo 1" in chunks[0] and "Articulo 3" in chunks[0]


def test_split_respects_accented_markers():
    text = "Artículo 1º. " + "x" * 80 + "\nArtículo 2º. " + "y" * 80 + "\n"
    chunks = split_structural(text, max_chars=100)
    assert len(chunks) == 2


def test_split_oversized_section_falls_back_to_fixed():
    # Un solo articulo mas grande que max_chars: se parte por tamano con solape.
    text = "Articulo 1. " + "z" * 500
    chunks = split_structural(text, max_chars=200)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 200


def test_split_never_exceeds_max_chars():
    text = "".join(f"Articulo {i}. " + "w" * 120 + "\n" for i in range(1, 20))
    chunks = split_structural(text, max_chars=300)
    assert chunks  # no vacio
    for chunk in chunks:
        assert len(chunk) <= 300
