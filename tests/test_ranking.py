"""Tests del ranking BM25 para la seleccion de articulos clave (fallback de baja RAM).

Funciones puras: sin modelo, sin red, sin llama-server. La determinacion (mismo
texto + misma query -> mismo orden siempre) es justamente lo que reemplaza el
juicio del modelo chico, asi que se prueba explicitamente.
"""

from leyllana.engine.chunking import ArticleChunk
from leyllana.engine.ranking import ScoredArticle, bm25_rank, select_key_articles
from leyllana.types import Nivel


def _chunk(n: int, texto: str) -> ArticleChunk:
    return ArticleChunk(label=f"Articulo {n}", text=texto)


def test_bm25_rank_empty_returns_empty():
    assert bm25_rank([], "obligacion plazo") == []


def test_bm25_rank_scores_relevant_article_higher():
    chunks = [
        _chunk(1, "Definiciones generales de la presente ley, sin mas contenido."),
        _chunk(2, "El infractor debera pagar una multa y cumplir el plazo fijado por la Agencia."),
        _chunk(3, "Disposiciones transitorias sobre la entrada en vigencia del reglamento."),
    ]
    ranked = bm25_rank(chunks, "multa plazo")
    assert isinstance(ranked[0], ScoredArticle)
    assert ranked[0].chunk.label == "Articulo 2"
    assert ranked[0].score > ranked[-1].score


def test_bm25_rank_is_deterministic():
    chunks = [_chunk(1, "obligacion y plazo"), _chunk(2, "sancion y multa")]
    first = bm25_rank(chunks, "plazo multa")
    second = bm25_rank(chunks, "plazo multa")
    assert [r.chunk.label for r in first] == [r.chunk.label for r in second]
    assert [r.score for r in first] == [r.score for r in second]


def test_bm25_rank_ignores_accents_and_case():
    chunks = [_chunk(1, "El PLAZO de Ejecución vence en marzo.")]
    ranked = bm25_rank(chunks, "plazo ejecucion")
    assert ranked[0].score > 0


def test_select_key_articles_returns_all_under_cap():
    text = "Articulo 1. uno\nArticulo 2. dos\nArticulo 3. tres\n"
    result = select_key_articles(text, Nivel.PUBLICO, cap=6)
    assert len(result) == 3


def test_select_key_articles_caps_with_bm25_when_no_reranker():
    partes = [f"Articulo {i}. contenido generico sin relevancia especial\n" for i in range(1, 20)]
    partes.append("Articulo 20. multa plazo sancion fiscaliza vigencia obligacion\n")
    text = "".join(partes)
    result = select_key_articles(text, Nivel.PUBLICO, cap=6)
    assert len(result) == 6
    assert any(a.label.startswith("Articulo 20") for a in result)


def test_select_key_articles_tecnico_has_no_fixed_query_but_still_caps():
    # TECNICO no tiene query fija (no deberia usarse este camino en explain(), pero
    # la funcion en si no debe reventar si la llaman con TECNICO).
    text = "".join(f"Articulo {i}. x\n" for i in range(1, 10))
    result = select_key_articles(text, Nivel.TECNICO, cap=6)
    assert len(result) == 6
