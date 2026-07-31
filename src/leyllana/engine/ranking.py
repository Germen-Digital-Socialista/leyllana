"""Seleccion de articulos clave sin pedirle juicio al modelo chico (baja RAM).

Gemma 3 1B y Qwen3-1.7B fallan al elegir "los 5-6 articulos importantes" de una ley
larga: o inventan, o enumeran todo el articulado (ROADMAP.md, 2026-07-30). Este
modulo saca esa eleccion del modelo y la hace con BM25 (deterministico, sin modelo)
mas, opcionalmente, un re-rankeador cross-encoder chico (Qwen3-Reranker-0.6B via
``llama-server --reranking``). Ver el spec:
docs/superpowers/specs/2026-07-30-fallback-article-selection-design.md
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from ..types import ArticleChunk, Nivel
from .chunking import estimate_tokens, split_by_article
from .server import LlamaServer, rerank

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Parametros BM25 estandar (Robertson/Sparck Jones); no medidos aun para este
# corpus especifico, ver seccion 9 del spec.
_BM25_K1 = 1.5
_BM25_B = 0.75

# Query fija por nivel, derivada de lo que _NIVEL_INSTRUCTIONS[PUBLICO] ya le pide
# al modelo (prompt/__init__.py): obligacion, plazo, sancion, quien fiscaliza,
# vigencia. Solo PUBLICO tiene tope de articulos; TECNICO no usa esto.
_NIVEL_QUERIES: dict[Nivel, str] = {
    Nivel.PUBLICO: (
        "obligacion plazo sancion multa fiscaliza vigencia consecuencia "
        "incumplimiento"
    ),
}


def query_for_nivel(nivel: Nivel) -> str:
    """Devuelve la query BM25 fija para ``nivel``, o cadena vacia si no aplica."""
    return _NIVEL_QUERIES.get(nivel, "")


def _tokenize(text: str) -> list[str]:
    """Minusculas, sin acentos, solo palabras/numeros. Igual normalizacion en
    documento y query para que el conteo de terminos calce."""
    normalizado = unicodedata.normalize("NFKD", text.lower())
    sin_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))
    return _TOKEN_RE.findall(sin_acentos)


@dataclass(frozen=True)
class ScoredArticle:
    """Un ``ArticleChunk`` con su puntaje BM25 contra una query."""

    chunk: ArticleChunk
    score: float


def bm25_rank(chunks: list[ArticleChunk], query: str) -> list[ScoredArticle]:
    """Ordena ``chunks`` por BM25 contra ``query``, de mayor a menor puntaje.

    Puro y deterministico: mismo texto y misma query dan siempre el mismo orden.
    Reemplaza el "elige los articulos importantes" que el modelo chico no puede
    sostener de forma confiable (ver el docstring del modulo).
    """
    if not chunks:
        return []

    query_terms = _tokenize(query)
    docs = [_tokenize(c.text) for c in chunks]
    doc_lens = [len(d) for d in docs]
    avg_len = sum(doc_lens) / len(docs)
    n = len(docs)

    doc_freq: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    scored: list[ScoredArticle] = []
    for chunk, doc, doc_len in zip(chunks, docs, doc_lens, strict=True):
        term_freq: dict[str, int] = {}
        for t in doc:
            term_freq[t] = term_freq.get(t, 0) + 1

        score = 0.0
        for term in query_terms:
            freq = term_freq.get(term, 0)
            if freq == 0:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
            norm = 1 - _BM25_B + _BM25_B * (doc_len / avg_len if avg_len else 0)
            score += idf * (freq * (_BM25_K1 + 1)) / (freq + _BM25_K1 * norm)

        scored.append(ScoredArticle(chunk=chunk, score=score))

    return sorted(scored, key=lambda s: s.score, reverse=True)


class RerankerClient:
    """Cliente del modelo re-rankeador: un ``LlamaServer`` separado en modo
    ``--reranking``, siempre en CPU (el modelo es chico, ~0,6B; no vale la pena la
    deteccion de GPU para esto)."""

    def __init__(self, server_path: str, model_path: str, *, ctx: int = 2048) -> None:
        # ``-ub`` (physical batch) por defecto en llama-server queda forzado a 512
        # en modo reranking/embeddings; un articulo real puede superar eso
        # facilmente (medido: Articulo 9 de la Ley 21.663 son 1073 tokens) y el
        # servidor responde HTTP 500 "input is too large to process" en vez de
        # truncar en silencio. Igualarlo a ``ctx`` deja pasar cualquier articulo
        # que ya quepa en el contexto configurado.
        self._server = LlamaServer(
            server_path,
            model_path,
            ctx=ctx,
            gpu="cpu",
            threads=0,
            extra_args=("--reranking", "--pooling", "rank", "-ub", str(ctx)),
        )

    def rank(self, chunks: list[ArticleChunk], query: str) -> list[ArticleChunk]:
        """Reordena ``chunks`` por relevancia contra ``query`` (mayor a menor)."""
        base = self._server.ensure()
        scores = rerank(base, query, [c.text for c in chunks])
        pares = sorted(zip(chunks, scores, strict=True), key=lambda p: p[1], reverse=True)
        return [chunk for chunk, _ in pares]

    def close(self) -> None:
        self._server.stop()


def select_key_articles(
    text: str,
    nivel: Nivel,
    *,
    reranker: "RerankerClient | None" = None,
    cap: int = 6,
    shortlist_size: int = 15,
    max_tokens: int | None = None,
) -> list[ArticleChunk]:
    """Selecciona los articulos clave de ``text``, sin pedirle criterio al modelo.

    Si ``text`` tiene ``cap`` articulos o menos, son los candidatos sin rankear
    (mismo espiritu que el corte temprano de ``_condense`` en engine/__init__.py:
    no correr maquinaria de seleccion sobre algo que ya cabe). Si no, BM25 acota a
    ``shortlist_size`` candidatos; si hay ``reranker``, lo reordena y corta a
    ``cap``. Sin ``reranker``, el propio orden de BM25 se corta a ``cap``.

    ``max_tokens``, si se da, es un segundo corte por presupuesto de tokens (no
    solo cantidad): un articulo largo puede pesar mas que varios cortos juntos
    (medido: 6 articulos de una ley real sumaron 3393 tokens, mas que el
    presupuesto entero de 2472 del prompt), asi que un tope por cantidad sin tope
    de tokens deja pasar un prompt que el proveedor va a rechazar. Se agregan los
    candidatos en orden de relevancia mientras quepan; se conserva al menos uno
    aunque el mas relevante por si solo exceda ``max_tokens`` (el fallo, si lo
    hay, queda para el ``ProviderError`` real del proveedor, no se inventa un
    resultado vacio).
    """
    chunks = split_by_article(text)
    if len(chunks) <= cap:
        candidatos = chunks
    else:
        query = query_for_nivel(nivel)
        ranked = bm25_rank(chunks, query)
        shortlist = [r.chunk for r in ranked[:shortlist_size]]
        candidatos = shortlist[:cap] if reranker is None else reranker.rank(shortlist, query)[:cap]

    if max_tokens is None:
        return candidatos

    elegidos: list[ArticleChunk] = []
    usados = 0
    for chunk in candidatos:
        t = estimate_tokens(chunk.text)
        if elegidos and usados + t > max_tokens:
            break
        elegidos.append(chunk)
        usados += t
    return elegidos


__all__ = [
    "ScoredArticle",
    "RerankerClient",
    "bm25_rank",
    "query_for_nivel",
    "select_key_articles",
]
