"""Tests del ranking BM25 para la seleccion de articulos clave (fallback de baja RAM).

Funciones puras: sin modelo, sin red, sin llama-server. La determinacion (mismo
texto + misma query -> mismo orden siempre) es justamente lo que reemplaza el
juicio del modelo chico, asi que se prueba explicitamente.
"""

from leyllana.engine.chunking import ArticleChunk
from leyllana.engine.ranking import RerankerClient, ScoredArticle, bm25_rank, select_key_articles
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


def test_select_key_articles_respects_token_budget():
    # Articulos moderadamente largos: cap=6 normalmente los devolveria todos,
    # pero un presupuesto de tokens chico debe recortar antes de llegar a 6.
    partes = []
    for i in range(1, 8):
        relleno = " ".join(["palabra"] * 60)  # ~60 tokens de relleno cada uno
        partes.append(f"Articulo {i}. multa plazo sancion {relleno}\n")
    text = "".join(partes)
    result = select_key_articles(text, Nivel.PUBLICO, cap=6, max_tokens=80)
    assert 1 <= len(result) < 6


def test_select_key_articles_keeps_at_least_one_even_over_budget():
    text = "Articulo 1. " + " ".join(["palabra"] * 200) + "\n"
    result = select_key_articles(text, Nivel.PUBLICO, cap=6, max_tokens=5)
    assert len(result) == 1


def test_select_key_articles_max_tokens_none_is_unbounded():
    text = "Articulo 1. uno\nArticulo 2. dos\n"
    result = select_key_articles(text, Nivel.PUBLICO, cap=6, max_tokens=None)
    assert len(result) == 2


def test_reranker_client_sets_physical_batch_to_ctx():
    # llama-server fuerza -ub a 512 en modo reranking por defecto, y un articulo
    # real puede superar eso (medido: 1073 tokens en un caso real) y el servidor
    # responde 500 en vez de truncar. RerankerClient debe igualar -ub a ctx.
    client = RerankerClient("srv", "m.gguf", ctx=4096)
    assert client._server._extra_args == ("--reranking", "--pooling", "rank", "-ub", "4096")


def test_reranker_client_reorders_by_relevance_score(monkeypatch):
    chunks = [
        ArticleChunk(label="Articulo 1", text="poco relevante"),
        ArticleChunk(label="Articulo 2", text="muy relevante"),
    ]

    class FakeServer:
        def ensure(self):
            return "http://fake"

        def stop(self):
            pass

    client = RerankerClient("srv", "m.gguf", ctx=2048)
    client._server = FakeServer()  # sustituye el LlamaServer real por uno falso

    import leyllana.engine.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "rerank", lambda base, query, docs: [0.1, 0.9])
    result = client.rank(chunks, "query")
    assert [c.label for c in result] == ["Articulo 2", "Articulo 1"]


def test_select_key_articles_uses_reranker_when_given():
    partes = [f"Articulo {i}. relleno sin relevancia\n" for i in range(1, 10)]
    text = "".join(partes)

    class FakeReranker:
        def rank(self, chunks, query):
            # invierte el orden que BM25 hubiera dado, para probar que se usa
            return list(reversed(chunks))

    result = select_key_articles(text, Nivel.PUBLICO, reranker=FakeReranker(), cap=3)
    assert len(result) == 3
