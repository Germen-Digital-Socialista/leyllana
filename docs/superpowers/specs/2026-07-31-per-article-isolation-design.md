# Per-article isolation for "Articulos clave" — design spec

**Date:** 2026-07-31
**Status:** Approved by Felipe Carvajal Brown at the design level. Approval was delegated
to a six-lens research fan-out (robustness, small-model behaviour, latency/UX, architecture,
faithfulness, simplicity/YAGNI): all six independently ranked this approach first over the
two alternatives (in-prompt authoritative headers; post-generation citation guard).
Not yet an ADR, not yet implemented.
**Related:** the 2026-07-30 fallback-article-selection spec (this builds directly on it),
ADR 0007 (output contract), ADR 0008 (anti-invention), ADR 0014 (traceability), ADR 0017
(map-reduce condense). ROADMAP "After-number" section (the measured failure this fixes).

## 1. Problem

The segmentation fix (commit `353b924`) removed the *spurious-chunk* fabrication mode but
did not move end-to-end faithfulness, because a second, independent mode dominates: the small
model **misattributes real article content to the wrong article number.**

Measured on Ley 19.628 (`mediciones/validacion-20260731-postfix/resultados.md`): the model
emits `Articulo 17: ... se castiga con multa`, but that multa/procedure clause lives inside
**Articulo 16**; real Articulo 17 governs which economic-obligation data may be communicated.
Both articles are in the pre-selected set. The content is real; the *number* is wrong.

Two conditions co-occur in the current single generation call and together cause the swap:
1. `build_with_selection` (`src/leyllana/prompt/__init__.py`) concatenates every pre-selected
   `a.text` into one user message, so neighbouring articles are visible at once and content
   can bleed across their boundary.
2. `CITATION` asks the model to copy the article number "tal como aparece" — i.e. the model
   *chooses* the number, re-deriving it from prose that also contains cross-reference numbers.

This is the same class of failure the selection layer was built to remove. That layer exists
on one thesis: a ~1-2B model cannot be trusted with **judgment**, so BM25 + reranker replaced
"pick the important articles." The mislabeling is judgment too — binding content to a number.

**Scope of this spec:** the simple-law case only (ordinary laws such as 19.628, where each
article's opening line is an unambiguous label). The modifying-law case (Ley 21.719, where the
unit "article" is itself ambiguous — inserted vs transitory vs directive-target) is explicitly
**out of scope** and left to a separate follow-up.

## 2. Decision

Extend the layer's thesis one level deeper: take **attribution** away from the model, the same
way selection was taken away. Generate the "Articulos clave" section **one article per call**,
each call seeing **only that article's text**, and assemble the section **deterministically**,
stamping each bullet with the label the pipeline already holds (`ArticleChunk.label`).

The model never sees two articles at once (so content cannot bleed onto a neighbour's number)
and never emits an article number at all (so it cannot get the number wrong). The number
becomes a pipeline output, not a model output.

## 3. Components and data flow

`explain()` PUBLICO branch, after `select_key_articles` returns the pre-selected `articulos`:

1. **Overview call (narrative only).** A new `build_overview(condensed, articulos, nivel)`
   asks for only the three narrative sections — `Que hace`, `A quien afecta`, `En una frase`
   — and *not* `Articulos clave`. Parsed by a three-section parse. Dropping the fourth section
   from this call also removes the pre-existing truncation risk where the big four-section call
   exhausts `max_tokens` before reaching `En una frase`.
2. **Per-article gloss calls.** For each `art` in `articulos`, a new trimmed
   `build_gloss(art, nivel)` prompt asks the model to explain **this one article** in plain
   language (PUBLICO register, guardrail intact), with **no section headers, no article number**
   — the model must not cite the number; the pipeline stamps it. Returns a single short gloss.
3. **Deterministic assembly.** `articulos_clave` = the glosses joined as bullets, each stamped:
   `- **{short_label(art.label)}:** {gloss}`.
4. **Field-wise `Explanation`.** Built from the three parsed narrative sections + the assembled
   `articulos_clave`. The four-section `parse()` contract is untouched for other callers.

Progress/cancel: the per-article loop reuses the existing `Stage`/`check(cancel)`/`report`
machinery (the same one `_condense` uses for `fragmento i de total`), so each gloss call is
individually cancelable and reported.

## 4. New pure units (each testable with no model)

- **`short_label(label: str) -> str`** — derive a short citation from a full opening line.
  `"Articulo 17.- La comunicacion..."` -> `"Articulo 17"`; `"Articulo 16 sexies.- ..."` ->
  `"Articulo 16 sexies"`; `"TITULO II DE LOS DERECHOS"` -> `"Titulo II"`. Reuses the
  ordinal/suffix vocabulary already in `chunking.py` (`_ORDINAL`, `_SUFIJO`). If nothing
  matches, fall back to the first line truncated — never fabricate a number. Lives next to
  `split_by_article` in `chunking.py`.
- **`build_overview(condensed, articulos, nivel) -> Prompt`** — three-section variant. Pure.
- **`build_gloss(art, nivel) -> Prompt`** — single-article plain-language prompt. Pure.
- **three-section parse** — extract `Que hace` / `A quien afecta` / `En una frase` from the
  overview response; raise `ParseError` if any is missing (same no-fill discipline as `parse`).

## 5. Accepted trade-offs

- **Cross-article context loss.** A gloss whose meaning leans on a neighbour (e.g. Art 17's
  "segun el articulo 16") is written without that neighbour in view, so it may read thinner or
  hit the guardrail's "No se puede determinar...". This is accepted: a faithful-but-thin gloss
  is strictly better than a confident wrong-number citation, which is the failure we are
  paying down. If it proves material in measurement, a later revision can widen each gloss call
  to include the immediate neighbours read-only, without reintroducing model-chosen numbers.
- **Latency.** ~5-6 short serial calls replace one large call for this section. Per this repo's
  rule, that is a wall-clock cost, not a money cost. The latency lens found aggregate decode
  roughly unchanged; the added cost is per-call system-prompt reprocessing, which the trimmed
  `build_gloss` prompt keeps small.
- **Label stamp trust.** The stamp is only as correct as segmentation. Verified 0% noise for
  simple laws (`tools/audit_segmentation.py`); this is exactly why the modifying-law case is
  out of scope.

## 6. Optional invariant (not a dependency)

Under this design every stamped label is trivially in the pre-selected set, so a
"every stamped label came from the selected set" assertion is near-free. It is a regression
guard for future drift (and for the eventual modifying-law work), never relied on to fix the
measured bug. Ship it only if it costs nothing to add.

## 7. Verification

- Unit tests (no model) for `short_label`, `build_overview`, `build_gloss`, three-section parse,
  and the deterministic assembly (stamped bullet format, one bullet per selected article).
- End-to-end: re-run the nine-run protocol
  (`docs/superpowers/plans/2026-07-31-reranker-validation-protocol.md`) with the same fixed
  criterion and the same Qwen3-1.7B config, giving a directly comparable before/after against
  the 4/9 postfix baseline. This is the real proof and is the metric that decides success.

## 8. Not doing (YAGNI)

- No modifying-law disambiguation (separate follow-up).
- No in-prompt header instruction and no post-hoc citation dropper as the primary fix (both
  ranked below this by all six lenses; GUARD provably cannot see an in-set mislabel).
- No change to the TECNICO path (no article cap, does not use `select_key_articles`).
