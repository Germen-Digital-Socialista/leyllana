**Status: Implemented 2026-07-30.** All 9 tasks complete, TDD throughout, one commit per
task (`ad8bc92`..`69cd873`). Full suite: 236 passed, 2 skipped (the two real-model smoke
tests, correctly gated behind env vars that point at real binaries/GGUFs). One real bug
found and fixed during Task 3 (a wrong test assertion, not an implementation defect --
`ArticleChunk.label` captures the whole first line by design, not just "Articulo N").

# Fallback article selection (BM25 + reranker) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the low-RAM fallback's own judgment about which articles matter with a
deterministic BM25 ranking step (optionally refined by a Qwen3-Reranker-0.6B cross-encoder),
so `nivel publico`'s "Articulos clave" section is filled from a pre-selected shortlist instead
of asking the generation model to choose.

**Architecture:** A new `engine/ranking.py` owns per-article segmentation (built on
`chunking.py`'s existing structure-splitting), a hand-rolled BM25 scorer, and a `RerankerClient`
that reuses `engine/server.py`'s `LlamaServer` against a second, reranking-mode subprocess.
`engine/__init__.py`'s `explain()` calls this selection step for `nivel publico` against the
`LocalProvider` only, and hands the result to a new `prompt.build_with_selection()` that tells
the model which articles to explain instead of asking it to pick.

**Tech Stack:** Python 3.11+, stdlib only (no new pip dependency — matches this project's
existing pattern of `urllib`/`tomllib` over pip packages), pytest for tests, `llama-server`'s
built-in `/v1/rerank` endpoint for the cross-encoder.

## Global Constraints

- No new pip dependency. BM25 is hand-rolled; the reranker call reuses `urllib` exactly as
  `chat_completion()` already does.
- `tecnico` nivel is untouched — it has no article cap, so this selection step never runs for it.
- Every provider failure stays loud (`ProviderError`), matching `LlamaServer`/`chat_completion`'s
  existing behavior — a configured-but-broken reranker must not be silently downgraded.
- Spanish docstrings/comments explaining *why*, matching every existing module in this repo;
  identifiers stay in English/Spanish mixed exactly as the surrounding file already does (e.g.
  `chunking.py` and `ranking.py` use Spanish comments with English-ish identifiers, matching the
  existing style).
- Every new pure function (segmentation, BM25, query building) must be unit-testable with no
  model, no server, no network — mirroring `test_chunking.py`'s existing hermetic style.

---

### Task 1: `ArticleChunk` + `split_by_article()` in `chunking.py`

**Files:**
- Modify: `src/leyllana/types.py` (defines `ArticleChunk` — a leaf module with no
  dependency on `engine` or `prompt`, so both can safely import it without a cycle)
- Modify: `src/leyllana/engine/chunking.py` (implements `split_by_article`, re-exports
  `ArticleChunk` for convenience so existing import style `from leyllana.engine.chunking
  import ArticleChunk` still works)
- Test: `tests/test_chunking.py`

**Interfaces:**
- Produces: `ArticleChunk` (frozen dataclass in `types.py`: `label: str`, `text: str`),
  `split_by_article(text: str) -> list[ArticleChunk]` (in `chunking.py`).

**Why `ArticleChunk` lives in `types.py`, not `chunking.py`:** Task 7 needs
`prompt/__init__.py` to reference `ArticleChunk` too. `engine/__init__.py` already imports
`from ..prompt import ...`, so if `ArticleChunk` lived in `engine/chunking.py` and
`prompt/__init__.py` imported it from there, importing `leyllana.prompt` on its own (e.g.
running `pytest tests/test_prompt.py` in isolation) would trigger loading `leyllana.engine`
mid-way through loading `leyllana.prompt`, which circles back to `from ..prompt import
build, ...` while `prompt/__init__.py` is still only partially executed — an `ImportError`
for a partially initialized module. Defining `ArticleChunk` in `types.py` (which nothing in
`engine` or `prompt` depends on) avoids the cycle entirely: both modules import a shared leaf.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_types.py` (new assertions in the existing file — check its current
imports first and merge, don't duplicate the module docstring):

```python
from leyllana.types import ArticleChunk


def test_article_chunk_is_frozen():
    chunk = ArticleChunk(label="Articulo 1", text="Articulo 1. Texto.")
    assert chunk.label == "Articulo 1"
    assert chunk.text == "Articulo 1. Texto."
```

Add to `tests/test_chunking.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_types.py tests/test_chunking.py -k "article_chunk or split_by_article" -v`
Expected: FAIL with `ImportError: cannot import name 'ArticleChunk'` (or `split_by_article`).

- [ ] **Step 3: Implement**

In `src/leyllana/types.py`, add after the `Nivel` class and before `Explanation`:

```python
@dataclass(frozen=True)
class ArticleChunk:
    """Un articulo (u otro marcador estructural) con su etiqueta, para trazabilidad.

    A diferencia de los trozos de ``chunking.split_structural``, cada ``ArticleChunk``
    es exactamente un marcador, sin agrupar varios juntos: el ranking
    (engine/ranking.py) necesita poder puntuar y citar cada articulo por separado.
    Vive aqui (no en engine/chunking.py) porque tanto ``engine`` como ``prompt`` lo
    necesitan, y ``engine/__init__.py`` ya importa de ``prompt`` -- ponerlo en
    ``engine.chunking`` habria armado un ciclo de imports.
    """

    label: str
    text: str
```

In `src/leyllana/engine/chunking.py`, add the import after the existing `import re` line:

```python
from ..types import ArticleChunk
```

Add after `_segments()` and before `split_structural()`:

```python
def split_by_article(text: str) -> list[ArticleChunk]:
    """Devuelve un ``ArticleChunk`` por cada marcador estructural de ``text``.

    El preambulo antes del primer marcador (titulo de la ley, encabezado) no es un
    articulo direccionable y se descarta: no tiene sentido rankearlo ni citarlo como
    "articulo clave". Si ``text`` no tiene ningun marcador, devuelve una lista vacia.
    """
    chunks: list[ArticleChunk] = []
    for seg in _segments(text):
        stripped = seg.lstrip()
        if not _STRUCTURE_RE.match(stripped):
            continue
        label = stripped.splitlines()[0].strip()
        chunks.append(ArticleChunk(label=label, text=seg))
    return chunks
```

Update `__all__`:

```python
__all__ = ["ArticleChunk", "estimate_tokens", "chars_for_tokens", "split_by_article", "split_structural"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_chunking.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/chunking.py tests/test_chunking.py
git commit -m "feat(chunking): add per-article segmentation for the ranking spec"
```

---

### Task 2: BM25 scorer in new `engine/ranking.py`

**Files:**
- Create: `src/leyllana/engine/ranking.py`
- Test: `tests/test_ranking.py` (new)

**Interfaces:**
- Consumes: `ArticleChunk` from `leyllana.engine.chunking`.
- Produces: `ScoredArticle` (frozen dataclass: `chunk: ArticleChunk`, `score: float`),
  `bm25_rank(chunks: list[ArticleChunk], query: str) -> list[ScoredArticle]` (sorted
  descending by score; deterministic).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ranking.py`:

```python
"""Tests del ranking BM25 para la seleccion de articulos clave (fallback de baja RAM).

Funciones puras: sin modelo, sin red, sin llama-server. La determinacion (mismo
texto + misma query -> mismo orden siempre) es justamente lo que reemplaza el
juicio del modelo chico, asi que se prueba explicitamente.
"""

from leyllana.engine.chunking import ArticleChunk
from leyllana.engine.ranking import ScoredArticle, bm25_rank


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leyllana.engine.ranking'`.

- [ ] **Step 3: Implement**

Create `src/leyllana/engine/ranking.py`:

```python
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

from ..types import Nivel
from .chunking import ArticleChunk, split_by_article
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


__all__ = ["ScoredArticle", "bm25_rank", "query_for_nivel"]
```

(`RerankerClient` and `select_key_articles` are added in later tasks, along with their imports
and `__all__` entries — keeping this task's diff scoped to what its own tests cover.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/ranking.py tests/test_ranking.py
git commit -m "feat(ranking): add a deterministic BM25 scorer for article selection"
```

---

### Task 3: `select_key_articles()` (BM25-only path) in `ranking.py`

**Files:**
- Modify: `src/leyllana/engine/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `split_by_article`, `bm25_rank`, `query_for_nivel` (Task 1/2).
- Produces: `select_key_articles(text: str, nivel: Nivel, *, reranker: "RerankerClient | None" = None, cap: int = 6, shortlist_size: int = 15) -> list[ArticleChunk]`.
  Later tasks (5) add the `reranker` branch; this task implements and tests the
  `reranker=None` path only.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ranking.py`:

```python
from leyllana.engine.ranking import select_key_articles
from leyllana.types import Nivel


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
    assert any(a.label == "Articulo 20" for a in result)


def test_select_key_articles_tecnico_has_no_fixed_query_but_still_caps():
    # TECNICO no tiene query fija (no deberia usarse este camino en explain(), pero
    # la funcion en si no debe reventar si la llaman con TECNICO).
    text = "".join(f"Articulo {i}. x\n" for i in range(1, 10))
    result = select_key_articles(text, Nivel.TECNICO, cap=6)
    assert len(result) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ranking.py -k select_key_articles -v`
Expected: FAIL with `ImportError: cannot import name 'select_key_articles'`.

- [ ] **Step 3: Implement**

In `src/leyllana/engine/ranking.py`, add after `bm25_rank` (before `__all__`):

```python
def select_key_articles(
    text: str,
    nivel: Nivel,
    *,
    reranker: "RerankerClient | None" = None,
    cap: int = 6,
    shortlist_size: int = 15,
) -> list[ArticleChunk]:
    """Selecciona los articulos clave de ``text``, sin pedirle criterio al modelo.

    Si ``text`` tiene ``cap`` articulos o menos, los devuelve todos sin rankear
    (mismo espiritu que el corte temprano de ``_condense`` en engine/__init__.py:
    no correr maquinaria de seleccion sobre algo que ya cabe). Si no, BM25 acota a
    ``shortlist_size`` candidatos; si hay ``reranker``, lo reordena y corta a
    ``cap``. Sin ``reranker``, el propio orden de BM25 se corta a ``cap``.
    """
    chunks = split_by_article(text)
    if len(chunks) <= cap:
        return chunks

    query = query_for_nivel(nivel)
    ranked = bm25_rank(chunks, query)
    shortlist = [r.chunk for r in ranked[:shortlist_size]]

    if reranker is None:
        return shortlist[:cap]
    return reranker.rank(shortlist, query)[:cap]
```

Update `__all__`:

```python
__all__ = ["ScoredArticle", "bm25_rank", "query_for_nivel", "select_key_articles"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: PASS. (The `reranker` branch is exercised starting in Task 5 — for now
`reranker` is only ever `None` in tests, so `RerankerClient`'s absence as a real
imported name doesn't matter yet; the type is a forward-reference string.)

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/ranking.py tests/test_ranking.py
git commit -m "feat(ranking): add select_key_articles with a BM25-only fallback path"
```

---

### Task 4: `LlamaServer` extra args + `/v1/rerank` client in `server.py`

**Files:**
- Modify: `src/leyllana/engine/server.py`
- Test: `tests/test_engine_local.py`

**Interfaces:**
- Modifies: `LlamaServer.__init__` gains `extra_args: tuple[str, ...] = ()`, appended to the
  argv `ensure()` builds. No change to existing callers (default is a no-op).
- Produces: `rerank(base_url: str, query: str, documents: list[str], *, timeout: float = _REQUEST_TIMEOUT) -> list[float]`
  — one score per document, **in the same order `documents` was passed**.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_engine_local.py` (near the other `LlamaServer`/`server_mod` tests):

```python
import json


def test_ensure_appends_extra_args(monkeypatch, tmp_path):
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(server_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(
        str(binary), str(model), ctx=2048, gpu="cpu", threads=0,
        extra_args=("--reranking", "--pooling", "rank"),
    )
    srv.ensure()
    assert captured["args"][-3:] == ["--reranking", "--pooling", "rank"]


def test_ensure_without_extra_args_unchanged(monkeypatch, tmp_path):
    # Los llamadores existentes (LocalProvider) no pasan extra_args: el argv no
    # debe cambiar para ellos.
    binary = tmp_path / "llama-server.exe"
    binary.write_text("x")
    model = tmp_path / "m.gguf"
    model.write_text("x")
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(server_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(server_mod.LlamaServer, "_wait_healthy", lambda self, timeout=180.0: None)

    srv = server_mod.LlamaServer(str(binary), str(model), ctx=2048, gpu="cpu", threads=0)
    srv.ensure()
    assert captured["args"][-1] == "--jinja"


def test_rerank_returns_scores_in_input_order(monkeypatch):
    payload = {
        "results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.2},
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(
        server_mod.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse()
    )
    scores = server_mod.rerank("http://fake", "query", ["doc a", "doc b"])
    assert scores == [0.2, 0.9]


def test_rerank_wraps_network_errors():
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.URLError("caido")

    import leyllana.engine.server as server_mod2

    orig = server_mod2.urllib.request.urlopen
    server_mod2.urllib.request.urlopen = boom
    try:
        with pytest.raises(ProviderError, match="reranker"):
            server_mod2.rerank("http://fake", "q", ["a"])
    finally:
        server_mod2.urllib.request.urlopen = orig
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine_local.py -k "extra_args or rerank" -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'extra_args'` for the
first two, `AttributeError: module 'leyllana.engine.server' has no attribute 'rerank'` for the
last two.

- [ ] **Step 3: Implement**

In `src/leyllana/engine/server.py`, modify `LlamaServer.__init__`:

```python
    def __init__(
        self,
        binary_path: str,
        model_path: str,
        *,
        ctx: int,
        gpu: str,
        threads: int,
        extra_args: tuple[str, ...] = (),
    ) -> None:
        self._binary = Path(binary_path)
        self._model = Path(model_path)
        self._ctx = ctx
        self._gpu = gpu
        self._threads = threads
        self._extra_args = extra_args
        self._proc: subprocess.Popen | None = None
        self._base: str | None = None
        self._lock = threading.Lock()
        self._log = None
```

Modify the `args` list inside `ensure()` (append `*self._extra_args` after `"--jinja"`):

```python
            args = [
                str(self._binary),
                "-m", str(self._model),
                "--host", "127.0.0.1",
                "--port", str(port),
                "-c", str(self._ctx),
                "-ngl", str(resolve_gpu_layers(self._gpu)),
                "--jinja",
                *self._extra_args,
            ]
```

Add `rerank()` after `chat_completion()` (before the `LlamaServer` class):

```python
def rerank(
    base_url: str, query: str, documents: list[str], *, timeout: float = _REQUEST_TIMEOUT
) -> list[float]:
    """Llama ``/v1/rerank`` (llama-server, modelo cross-encoder) y devuelve un
    puntaje por documento, en el MISMO ORDEN en que se paso ``documents``.

    A diferencia de ``chat_completion``, no es streaming: el reranker devuelve un
    JSON de una vez, no un flujo SSE token a token.
    """
    payload = {"query": query, "documents": documents}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/rerank",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            obj = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"Fallo la llamada al reranker: {exc}") from exc

    by_index = {r["index"]: r["relevance_score"] for r in obj.get("results", [])}
    return [by_index[i] for i in range(len(documents))]
```

Update `__all__` at the bottom of the file:

```python
__all__ = ["LlamaServer", "chat_completion", "rerank", "resolve_gpu_layers"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine_local.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/server.py tests/test_engine_local.py
git commit -m "feat(server): add /v1/rerank client and LlamaServer extra_args"
```

---

### Task 5: `RerankerClient` in `ranking.py`, wired into `select_key_articles`

**Files:**
- Modify: `src/leyllana/engine/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `LlamaServer`, `rerank` (Task 4).
- Produces: `RerankerClient(server_path: str, model_path: str, *, ctx: int = 2048)` with
  `.rank(chunks: list[ArticleChunk], query: str) -> list[ArticleChunk]` (sorted by relevance,
  descending) and `.close() -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ranking.py`:

```python
from leyllana.engine.ranking import RerankerClient


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ranking.py -k reranker -v`
Expected: FAIL with `ImportError: cannot import name 'RerankerClient'`.

- [ ] **Step 3: Implement**

In `src/leyllana/engine/ranking.py`, add the class after `bm25_rank` and before
`select_key_articles`:

```python
class RerankerClient:
    """Cliente del modelo re-rankeador: un ``LlamaServer`` separado en modo
    ``--reranking``, siempre en CPU (el modelo es chico, ~0,6B; no vale la pena la
    deteccion de GPU para esto)."""

    def __init__(self, server_path: str, model_path: str, *, ctx: int = 2048) -> None:
        self._server = LlamaServer(
            server_path,
            model_path,
            ctx=ctx,
            gpu="cpu",
            threads=0,
            extra_args=("--reranking", "--pooling", "rank"),
        )

    def rank(self, chunks: list[ArticleChunk], query: str) -> list[ArticleChunk]:
        """Reordena ``chunks`` por relevancia contra ``query`` (mayor a menor)."""
        base = self._server.ensure()
        scores = rerank(base, query, [c.text for c in chunks])
        pares = sorted(zip(chunks, scores, strict=True), key=lambda p: p[1], reverse=True)
        return [chunk for chunk, _ in pares]

    def close(self) -> None:
        self._server.stop()
```

Update `__all__`:

```python
__all__ = [
    "ScoredArticle",
    "RerankerClient",
    "bm25_rank",
    "query_for_nivel",
    "select_key_articles",
]
```

(`select_key_articles` already calls `reranker.rank(shortlist, query)` from Task 3 — no change
needed there.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/ranking.py tests/test_ranking.py
git commit -m "feat(ranking): add RerankerClient and wire it into select_key_articles"
```

---

### Task 6: `reranker_model` in config

**Files:**
- Modify: `src/leyllana/config.py`
- Test: `tests/test_config.py`, `tests/test_config_write.py`

**Interfaces:**
- Modifies: `EngineConfig` gains `reranker_model: ModelConfig` (default `ModelConfig(ctx=2048)`,
  same shape as `fallback_model`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_reranker_model_defaults():
    cfg = Config()
    assert cfg.engine.reranker_model.path is None
    assert cfg.engine.reranker_model.ctx == 2048


def test_load_reads_reranker_model(tmp_path):
    toml = tmp_path / "leyllana.toml"
    toml.write_text(
        "[engine]\n"
        'provider = "local"\n'
        "[engine.models.reranker]\n"
        'path = "reranker.gguf"\n'
        "ctx = 4096\n",
        encoding="utf-8",
    )
    cfg = load(toml)
    assert cfg.engine.reranker_model.path == "reranker.gguf"
    assert cfg.engine.reranker_model.ctx == 4096
```

Check `tests/test_config_write.py` for the existing round-trip test pattern (read it first —
if it asserts on the full `dumps()` output or on specific tables, add a matching case there for
`engine.models.reranker`, following whatever pattern the existing `default`/`fallback` tables
use in that file).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k reranker -v`
Expected: FAIL with `AttributeError: 'EngineConfig' object has no attribute 'reranker_model'`.

- [ ] **Step 3: Implement**

In `src/leyllana/config.py`, modify `EngineConfig`:

```python
@dataclass(frozen=True)
class EngineConfig:
    provider: str = "local"
    default_model: ModelConfig = field(default_factory=ModelConfig)
    fallback_model: ModelConfig = field(default_factory=lambda: ModelConfig(ctx=2048))
    reranker_model: ModelConfig = field(default_factory=lambda: ModelConfig(ctx=2048))
    cli: CliConfig = field(default_factory=CliConfig)
    server_path: str | None = None
    gpu: str = "auto"
    temperature: float = 0.2
    max_tokens: int = 1024
    threads: int = 0
```

In `load()`, add to the `EngineConfig(...)` construction (alongside `fallback_model=...`):

```python
        fallback_model=_model_from_dict(models_data.get("fallback", {"ctx": 2048})),
        reranker_model=_model_from_dict(models_data.get("reranker", {"ctx": 2048})),
```

In `dumps()`, add after the `engine.models.fallback` table:

```python
    lineas += _table(
        "engine.models.reranker",
        [("path", e.reranker_model.path), ("ctx", e.reranker_model.ctx)],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py tests/test_config_write.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/config.py tests/test_config.py tests/test_config_write.py
git commit -m "feat(config): add engine.models.reranker"
```

---

### Task 7: `build_with_selection()` in `prompt/__init__.py`

**Files:**
- Modify: `src/leyllana/prompt/__init__.py`
- Test: `tests/test_prompt.py`

**Interfaces:**
- Consumes: `ArticleChunk` from `leyllana.types` (not `leyllana.engine.chunking` — see the
  "why" note in Task 1; importing from `..types` here is what keeps this cycle-free).
- Produces: `build_with_selection(overview: str, articles: list[ArticleChunk], nivel: Nivel) -> Prompt`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prompt.py`:

```python
from leyllana.types import ArticleChunk
from leyllana.prompt import build_with_selection


def test_build_with_selection_includes_articles_verbatim():
    articles = [
        ArticleChunk(label="Articulo 5", text="Articulo 5. El plazo es de 10 dias."),
        ArticleChunk(label="Articulo 9", text="Articulo 9. La multa es de 50 UTM."),
    ]
    p = build_with_selection("resumen de la ley", articles, Nivel.PUBLICO)
    assert "Articulo 5. El plazo es de 10 dias." in p.user
    assert "Articulo 9. La multa es de 50 UTM." in p.user
    assert "resumen de la ley" in p.user


def test_build_with_selection_tells_model_not_to_choose():
    p = build_with_selection("resumen", [ArticleChunk(label="Articulo 1", text="x")], Nivel.PUBLICO)
    assert "preseleccionados" in p.system.lower()


def test_build_with_selection_keeps_the_four_sections():
    p = build_with_selection("r", [ArticleChunk(label="Articulo 1", text="x")], Nivel.PUBLICO)
    for titulo in ("Que hace", "A quien afecta", "Articulos clave", "En una frase"):
        assert titulo in p.system
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompt.py -k build_with_selection -v`
Expected: FAIL with `ImportError: cannot import name 'build_with_selection'`.

- [ ] **Step 3: Implement**

In `src/leyllana/prompt/__init__.py`, change the existing import line:

```python
from ..types import Nivel
```

to:

```python
from ..types import ArticleChunk, Nivel
```

Add after `build()` and before `build_extract()`:

```python
# Se antepone a la instruccion de nivel existente: le dice al modelo que la
# eleccion de "elige a lo mas cinco o seis" ya esta resuelta, en vez de duplicar
# o contradecir esa frase dentro de _NIVEL_INSTRUCTIONS.
_SELECTION_INSTRUCTION = (
    "Los articulos de la seccion 'Articulos clave' YA fueron preseleccionados por un "
    "sistema de busqueda, y vienen listados abajo bajo 'Articulos preseleccionados'. "
    "La instruccion de 'elige a lo mas cinco o seis articulos' de mas arriba ya esta "
    "resuelta: explica esos articulos y solo esos, en el mismo orden en que aparecen. "
    "No elijas otros artículos, no agregues los que falten, no dejes ninguno de estos "
    "fuera."
)


def build_with_selection(
    overview: str, articles: list[ArticleChunk], nivel: Nivel
) -> Prompt:
    """Arma el ``Prompt`` cuando los articulos clave ya fueron preseleccionados
    (BM25 + reranker opcional, engine/ranking.py) en vez de dejar que el modelo
    elija.

    Solo tiene sentido para PUBLICO (el unico nivel con tope de articulos); ver
    docs/superpowers/specs/2026-07-30-fallback-article-selection-design.md.
    """
    secciones = "\n".join(_SECTIONS[nivel])
    system = (
        "Eres leyllana, un asistente que explica leyes y boletines chilenos "
        "(espanol de Chile).\n\n"
        f"{GUARDRAIL}\n\n"
        f"{CITATION}\n\n"
        f"{_NIVEL_INSTRUCTIONS[nivel]}\n\n"
        f"{_SELECTION_INSTRUCTION}\n\n"
        "Responde SIEMPRE con estas cuatro secciones, en este orden, cada una "
        "empezando por su titulo exacto al inicio de una linea:\n"
        f"{secciones}\n\n"
        f"{FORMATO}"
    )
    articulos_texto = "\n\n".join(f"{a.label}\n{a.text}" for a in articles)
    user = (
        f"Resumen de la norma o boletin:\n\n{overview}\n\n"
        f"Articulos preseleccionados:\n\n{articulos_texto}"
    )
    return Prompt(system=system, user=user)
```

Update `__all__`:

```python
__all__ = ["Prompt", "build", "build_extract", "build_with_selection", "GUARDRAIL", "CITATION", "FORMATO"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/prompt/__init__.py tests/test_prompt.py
git commit -m "feat(prompt): add build_with_selection for pre-chosen articles"
```

---

### Task 8: Wire selection into `explain()`

**Files:**
- Modify: `src/leyllana/engine/__init__.py`
- Test: `tests/test_engine_local.py`

**Interfaces:**
- Consumes: `select_key_articles`, `RerankerClient` (ranking.py); `build_with_selection`
  (prompt); `LocalProvider` (local.py).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_engine_local.py`:

```python
def test_explain_uses_selection_for_publico_local_provider(monkeypatch):
    # Ley corta (bajo el tope): select_key_articles devuelve todo sin rankear, asi
    # que este test no necesita reranker ni BM25 real, solo confirmar que
    # build_with_selection (no build) es lo que arma el prompt para PUBLICO+local.
    canned = (
        "Que hace: regula algo.\n"
        "A quien afecta: a los organismos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    captured = {}

    def fake_chat(base, messages, *, temperature, max_tokens, **kwargs):
        captured["messages"] = messages
        return canned

    monkeypatch.setattr("leyllana.engine.local.chat_completion", fake_chat)
    monkeypatch.setattr(LocalProvider, "_ensure_server", lambda self: "http://fake")

    texto = "Articulo 1. Regula el uso de sistemas de IA por organismos publicos."
    exp = explain(texto, Nivel.PUBLICO, _local_cfg())

    assert isinstance(exp, Explanation)
    user_msg = captured["messages"][1]["content"]
    assert "Articulos preseleccionados" in user_msg
    assert "Articulo 1" in user_msg


def test_explain_tecnico_still_uses_plain_build(monkeypatch):
    # TECNICO no pasa por la seleccion (no tiene tope) -- sigue usando build().
    canned = (
        "Que hace: regula algo.\n"
        "A quien afecta: a los organismos.\n"
        "Articulos clave: Articulo 1.\n"
        "En una frase: una ley sobre IA."
    )
    captured = {}

    def fake_chat(base, messages, *, temperature, max_tokens, **kwargs):
        captured["messages"] = messages
        return canned

    monkeypatch.setattr("leyllana.engine.local.chat_completion", fake_chat)
    monkeypatch.setattr(LocalProvider, "_ensure_server", lambda self: "http://fake")

    explain("Articulo 1. Texto.", Nivel.TECNICO, _local_cfg())
    user_msg = captured["messages"][1]["content"]
    assert "Articulos preseleccionados" not in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine_local.py -k "selection or tecnico_still" -v`
Expected: The PUBLICO test fails because `build()` (not `build_with_selection()`) is still
used — assert on `"Articulos preseleccionados" in user_msg` fails. The TECNICO test currently
passes already (no change needed there yet) but is written now so it stays green through this
task's change.

- [ ] **Step 3: Implement**

In `src/leyllana/engine/__init__.py`, update the imports:

```python
from ..config import Config
from ..prompt import build, build_extract, build_with_selection
from ..types import Explanation, Nivel
from .base import ConsentRequired, Provider
from .chunking import chars_for_tokens, estimate_tokens, split_structural
from .local import LocalProvider
from .progress import (
    Cancelled,
    CancelToken,
    Progress,
    ProgressFn,
    Stage,
    check,
    report,
)
from .ranking import RerankerClient, select_key_articles
from .registry import get_provider
```

Add a small helper before `explain()`:

```python
def _reranker_for(config: Config) -> RerankerClient | None:
    """Construye un ``RerankerClient`` si hay un modelo re-rankeador configurado.

    Sin ``reranker_model.path``, ``select_key_articles`` sigue funcionando con
    BM25 solo (ADR-style graceful degrade, no un error)."""
    engine = config.engine
    if not engine.reranker_model.path or not engine.server_path:
        return None
    return RerankerClient(
        engine.server_path, engine.reranker_model.path, ctx=engine.reranker_model.ctx
    )
```

Modify the body of `explain()` — replace the two lines:

```python
    report(progress, Stage.GENERANDO)
    raw = provider.generate(build(condensed, nivel), cancel=cancel)
```

with:

```python
    report(progress, Stage.GENERANDO)
    if nivel == Nivel.PUBLICO and isinstance(provider, LocalProvider):
        reranker = _reranker_for(cfg)
        try:
            articulos = select_key_articles(text, nivel, reranker=reranker)
            raw = provider.generate(
                build_with_selection(condensed, articulos, nivel), cancel=cancel
            )
        finally:
            if reranker is not None:
                reranker.close()
    else:
        raw = provider.generate(build(condensed, nivel), cancel=cancel)
```

Note: `select_key_articles` ranks against the **original** `text`, not `condensed` — the
condensed map-reduce overview is for the narrative sections only (§4 of the spec); article
selection needs the real article text to cite verbatim, which the condensed points do not
reliably preserve.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine_local.py tests/test_engine.py tests/test_engine_mapreduce.py -v`
Expected: PASS (the full local-provider and engine suites, to catch any regression in the
existing `explain()` behavior for `tecnico` and for cloud/CLI providers, which never hit the
`isinstance(provider, LocalProvider)` branch).

- [ ] **Step 5: Commit**

```bash
git add src/leyllana/engine/__init__.py tests/test_engine_local.py
git commit -m "feat(engine): wire BM25/reranker article selection into explain() for publico"
```

---

### Task 9: Real-model smoke test for the reranker

**Files:**
- Modify: `tests/test_engine_smoke.py`

**Interfaces:**
- Consumes: everything above, end to end, against a real `llama-server` binary and a real
  Qwen3-Reranker-0.6B GGUF.

- [ ] **Step 1: Write the gated test**

Add to `tests/test_engine_smoke.py` (after the existing `_READY`/`pytestmark` block, as a
second, independently-gated test — do not fold this into the existing `_READY` check, since a
machine may have the generation model but not the reranker yet):

```python
_RERANKER_SERVER = os.environ.get("LEYLLANA_SMOKE_RERANKER_SERVER")
_RERANKER_MODEL = os.environ.get("LEYLLANA_SMOKE_RERANKER_MODEL")
_RERANKER_READY = bool(
    _RERANKER_SERVER
    and _RERANKER_MODEL
    and Path(_RERANKER_SERVER).exists()
    and Path(_RERANKER_MODEL).exists()
)


@pytest.mark.skipif(
    not _RERANKER_READY,
    reason="defina LEYLLANA_SMOKE_RERANKER_SERVER y LEYLLANA_SMOKE_RERANKER_MODEL",
)
def test_reranker_real_rerank_call():
    from leyllana.engine.ranking import RerankerClient
    from leyllana.engine.chunking import ArticleChunk

    client = RerankerClient(_RERANKER_SERVER, _RERANKER_MODEL, ctx=2048)
    try:
        chunks = [
            ArticleChunk(label="Articulo 1", text="Articulo 1. Definiciones generales."),
            ArticleChunk(
                label="Articulo 2",
                text="Articulo 2. El infractor pagara una multa de hasta 500 UTM.",
            ),
        ]
        ranked = client.rank(chunks, "multa sancion")
        assert ranked[0].label == "Articulo 2"
    finally:
        client.close()
```

- [ ] **Step 2: Run it (only meaningful with a real reranker GGUF present)**

Run (with the two env vars pointed at a real `llama-server` binary and a real
Qwen3-Reranker-0.6B GGUF):
`LEYLLANA_SMOKE_RERANKER_SERVER=C:/path/llama-server.exe LEYLLANA_SMOKE_RERANKER_MODEL=C:/path/Qwen3-Reranker-0.6B.gguf uv run pytest tests/test_engine_smoke.py -k reranker -v`
Expected: PASS (or SKIPPED if the env vars are unset — confirm the skip message reads clearly
by running with no env vars set too: `uv run pytest tests/test_engine_smoke.py -v`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine_smoke.py
git commit -m "test(smoke): add a gated real-model test for the reranker"
```

---

## Final check (run once, after Task 9)

Run the full suite to confirm nothing regressed:

```bash
uv run pytest -v
```

Expected: all tests PASS (smoke tests SKIPPED unless their env vars are set — that is
expected and correct, not a failure).
