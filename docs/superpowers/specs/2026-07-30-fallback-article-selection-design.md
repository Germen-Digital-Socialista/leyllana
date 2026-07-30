# Low-RAM fallback article selection — design spec

**Date:** 2026-07-30
**Status:** Approved by Felipe Carvajal Brown (design level). Not yet an ADR, not yet
implemented.
**Related:** ROADMAP.md ("Gemma 3 1B tried as a replacement...", "Low-RAM, no-GPU target"),
ADR 0007 (output contract), ADR 0008 (anti-invention), ADR 0014 (traceability), ADR 0015
(model selection), ADR 0016 (llama-server subprocess runtime), ADR 0017 (map-reduce, which
ruled retrieval out of scope for the *explain* task itself — this spec reopens that call for
the fallback path only, not the base pipeline), ADR 0024/0025 (Gemma 3 1B fallback swap and
its licensing waiver).

## 1. Purpose

The low-RAM fallback model keeps failing at one specific sub-task: picking the 5-6 most
important articles out of a long law for `nivel publico`'s "Articulos clave" section.

- Qwen3-1.7B's failure mode (Phase 1, and the 2026-07-30 re-test) was outright fabrication —
  inventing an entire nonexistent law, twice — a more severe failure than a selection problem,
  but the four inconsistent re-test outcomes never isolated whether document length/complexity
  was a contributing factor.
- Gemma 3 1B's failure, reproduced three times on 2026-07-30 with a real running harness, was
  narrower and more diagnostic: it cannot obey "choose at most 5-6 articles," in any of three
  attempts, including one where a one-shot example explicitly demonstrated a single selected
  article as the target shape. It enumerated the articulado instead of judging importance,
  exhausted `max_tokens` doing so, and never reached "En una frase."

That third finding reframes the problem. Both models are being asked to do two things in one
generation call: **judge which articles matter, and write prose about them.** Gemma's repeated,
undeterred-by-anchoring failure suggests the judgment half of that task may be beyond what a
~1-2B model can hold alongside everything else the prompt already asks of it (register, citation
format, no conversational wrapper, whole-law gist). This spec removes the judgment half from the
generation call entirely, replacing it with a deterministic ranking step upstream.

## 2. Why this is model-agnostic, and where it fits relative to the model-swap thread

This is **not an alternative to ADR 0025's Gemma swap** — it is a separate, orthogonal fix that
should be validated against whichever model is cheapest to test first. Per Felipe's direction,
that means testing against **Qwen3-1.7B** first (already on the machine, already characterized),
not spending a new testing cycle on Gemma or another candidate before this exists.

If this design works, it changes what's being asked of ADR 0025 too: Gemma was sought as a
replacement partly *because* Qwen3-1.7B's failures looked like a capacity problem. If article
selection is handled upstream of the model in both cases, the fallback model's job shrinks to
"explain a small, pre-vetted set of articles plus a whole-law gist" — a materially easier task
than "read a whole law, decide what matters, and explain it," which may change which model is
actually needed. That reassessment is out of scope for this spec; it is flagged here so it is
not lost.

## 3. Architecture

A new module, `engine/ranking.py`, holds three pieces:

1. **Per-article segmentation.** `chunking.py`'s `_segments()` already splits text at
   `Articulo`/`Titulo`/`Capitulo`/`Parrafo` boundaries; `split_structural()` then *groups*
   consecutive segments up to `max_chars`. This spec needs the ungrouped form — one chunk per
   article, each carrying its article label for citation tracing. Add a new public function,
   e.g. `split_by_article(text) -> list[ArticleChunk]` (`ArticleChunk` a small frozen dataclass:
   `label: str`, `text: str`), built on the existing `_segments()` logic rather than duplicating
   it.
2. **BM25 scorer.** Hand-rolled, no new dependency (this project has none today; BM25 is
   ~30 lines of term-frequency/IDF arithmetic, consistent with the existing pattern of using the
   standard library over a pip package — `urllib` instead of `requests`, `tomllib` instead of a
   TOML library). Scores every article in the loaded law against a query built from the active
   `nivel`'s own criteria (see §4). Pure function, deterministic, no I/O.
3. **Reranker client.** A thin wrapper reusing `LlamaServer` from `engine/server.py` — a second
   managed subprocess, same lifecycle pattern as the generation model, started with
   `--reranking --pooling rank` against a **Qwen3-Reranker-0.6B** GGUF instead of a chat model.
   Calls `/v1/rerank` (llama-server's built-in endpoint for cross-encoder GGUFs) with the BM25
   shortlist and returns the final ranked top-N.

Qwen3-Reranker-0.6B: Apache 2.0 (same family already vetted in ADR 0015, no licensing question),
small enough that reranking ~15 short article candidates costs roughly 1-2 seconds on CPU —
negligible next to the multi-minute generation cost this whole effort is downstream of.

## 4. Data flow (nivel `publico` only)

`tecnico` has no article cap ("no hay tope") — the selection-judgment failure this spec targets
doesn't occur there, so `tecnico`'s behavior is unchanged.

For `publico`:

1. `split_by_article(text)` → all articles in the loaded law.
2. Build a fixed query string from `_NIVEL_INSTRUCTIONS[Nivel.PUBLICO]`'s existing criteria
   (already latent in `prompt/__init__.py`): obligación, plazo, sanción, quién fiscaliza, entrada
   en vigencia, consecuencia de incumplimiento.
3. BM25-rank all articles against that query → keep a shortlist (top 15, or all of them if the
   law has fewer than 15 articles — see §5).
4. If a reranker is configured (§5): send the shortlist to `/v1/rerank` → take the final top 5-6
   by `relevance_score`. If not configured: the BM25 shortlist's own top 5-6 is the result.
5. Those articles go into the synthesis prompt **verbatim**, alongside the existing map-reduce
   condensed overview (still needed for "Que hace" / "A quien afecta" / "En una frase", which need
   whole-law gist, not per-article detail). The prompt changes from "choose the important
   articles" to "here are the important articles, explain them" — the model is told, not asked
   to decide.

This only replaces the selection step inside `build()`'s article-clave portion; `_condense()`'s
existing map-reduce for the narrative sections is untouched.

## 5. Config

New table, same shape as `default`/`fallback`:

```toml
[engine.models.reranker]
path = "C:/.../Qwen3-Reranker-0.6B-Q8_0.gguf"
ctx = 2048
```

`ModelConfig` already has `path`/`ctx`; reuse the dataclass rather than inventing a new one.
Selection ranking activates only when `engine.provider == "local"`, `nivel == publico`, and the
document has more articles than the cap.

## 6. Error handling

Following this codebase's existing swappable-provider philosophy (ADR 0003): degrade
explicitly, never fail silently, never fail loudly for a missing optional piece.

- **No reranker configured** (`engine.models.reranker.path` is `None`): skip straight to
  BM25-only ranking. This is a real, working mode, not a stub — BM25 alone was measured
  elsewhere in this project's own research as within 0.3 points of dense retrieval for legal
  text specifically.
- **Fewer articles than the cap:** skip ranking entirely, include all of them. Mirrors
  `_condense()`'s existing "if it already fits, return as-is" short-circuit — no scoring
  machinery runs on a law too short to need it.
- **Reranker server fails to start or errors mid-call:** a real `ProviderError`, loud, matching
  how every other provider failure in this codebase already behaves (`LlamaServer.ensure()`,
  `chat_completion()`). Not caught and silently downgraded to BM25 — a configured-but-broken
  reranker is a real problem to see, not paper over.

## 7. Testing

- **Article segmentation** (`split_by_article`) and **BM25 scoring** are both pure functions
  over text — fully unit-testable with a small fixture law and a known expected ranking. No
  model, no server, no network. Deterministic, so a golden-set assertion (given this text and
  this query, expect this exact top-N) is a real, stable test, not a flaky one.
- **Reranker round-trip** gets a real-model smoke test gated behind an env var, matching the
  existing pattern in `tests/test_engine_smoke.py` (skipped unless
  `LEYLLANA_SMOKE_RERANKER_SERVER`/`LEYLLANA_SMOKE_RERANKER_MODEL` point at real binaries/GGUFs).
- **Faithfulness** (are the selected articles actually the right ones, does the final output
  still avoid fabrication) is not something a unit test can certify — it needs the same
  human-spot-check protocol already used throughout this project's model testing: run against a
  real law, verify cited articles and their content against the source text by hand.

## 8. What this spec does not do

- Does not touch `tecnico`'s behavior (no cap there, no selection-judgment failure to fix).
- Does not implement the corpus-wide retrieval layer (`dirigente`/`autoridad comunal`) — that is
  a separate, larger capability already scoped in
  `docs/superpowers/specs/2026-07-30-retrieval-layer-design.md`, unrelated to this fix beyond
  sharing the word "retrieval."
- Does not decide ADR 0025's fate (keep Gemma, revert to Qwen3-1.7B, or something else) — see
  §2. That reassessment happens after this is built and measured, not before.
- Does not add a corpus-storage compression layer (LLMLingua-2 or similar) — a separate,
  already-recorded lead in ROADMAP.md, orthogonal to this spec's single-document scope.

## 9. Open questions for the implementation plan

- Exact BM25 parameters (`k1`, `b`) — standard defaults (`k1=1.5`, `b=0.75`) are the reasonable
  starting point; not worth tuning before there is a failing test to tune against.
- Shortlist size (top 15 before rerank) is a starting guess, not a measured number — cheap to
  change once real timing/quality data exists.
- Where the Qwen3-Reranker-0.6B GGUF gets downloaded from and what exact quantization — same
  due-diligence pattern as every other model choice in this project (verify the license and the
  source before committing a path into config).
