# 0026 — Per-article isolation for the "Artículos clave" citations

- **Status:** Accepted
- **Date:** 2026-07-31
- **Deciders:** Felipe Carvajal Brown

## Context

The `nivel publico` path pre-selects key articles deterministically (BM25 + a
Qwen3-Reranker cross-encoder) because the small local model cannot be trusted to
*judge* which articles matter. That selection layer works but is itself not yet
recorded in an ADR.

A second, independent failure survived the 2026-07-31 segmentation fix and
dominated the 9-run measurement: the model **misattributed real content to the
wrong article number**. Given the pre-selected articles concatenated into one
prompt, it bound Ley 19.628's multa clause (which lives in Artículo 16) to the
label "Artículo 17", and collapsed Ley 21.719's transitory "Artículo sexto" into
a confusing "Artículo 6". The content was real; the number was wrong — which for a
tool whose promise is faithful citation is a fabrication.

A six-lens research fan-out (robustness, small-model behaviour, latency,
architecture, faithfulness, simplicity) ranked three fixes; all six independently
placed per-article isolation first. The reasoning that carried every lens: binding
content to a number is *judgment*, the exact thing the selection layer exists to
take away from the model — so the consistent fix extends that thesis rather than
adding an instruction and hoping a 1.7B model obeys it.

## Decision

Build the "Artículos clave" section **one article per model call**, each call
seeing **only that article's text**, and stamp the article number deterministically
from the chunk's own label (`chunking.short_label`) rather than letting the model
emit it. The three narrative sections (Qué hace / A quién afecta / En una frase)
come from a separate overview call that is **grounded in the selected articles**
(not the condensed summary alone) and requests only those three sections. The model
never sees two articles at once and never writes a number.

## Consequences

- **The misattribution mode is eliminated, verified:** zero mislabels across all 9
  runs. The number is a pipeline output; it cannot be wrong.
- **Aggregate faithfulness improved 4/9 → 5/9**, and the hardest case (Ley 21.719, a
  modifying law) went 0/3 → 2/3 because the labeling that sank it is fixed. The
  control held 3/3, now with correct labels *and* accurate glosses.
- **Two costs, honestly:** (1) it exposed a distinct within-article comprehension
  failure — glossing Ley 19.628's 4,296-char Art 16 in isolation, the model inverts
  the two-track appeal (3/3 fabricated on that doc, a regression there); (2) 4 of ~24
  glosses returned "No se puede determinar" — honest, not fabrication, but a cited
  article that refuses is not useful. Both are separately tracked in ROADMAP; neither
  is addressed here.
- Extra latency: ~5-6 short serial calls replace one for this section (wall-clock,
  not money — local engine).
- Touches the output contract (ADR 0007) — `Explanation` is now built field-wise,
  three sections parsed plus one assembled — and serves the anti-invention guardrail
  (ADR 0008). The BM25+reranker selection layer it builds on remains un-recorded and
  still warrants its own ADR.

## Alternatives considered

- **In-prompt authoritative headers** — keep the single call, wrap each article under
  a pipeline-controlled header, instruct the model to cite only the header number and
  treat body numbers as cross-references. Rejected: the model still holds all articles
  at once and must obey a negative meta-instruction, exactly what a 1.7B follows least
  reliably; each block already opens with its number today, yet the model still
  mislabeled.
- **Post-generation citation guard** — let the model generate, then drop citations
  whose number isn't in the pre-selected set. Rejected: it cannot see the measured
  failure (Art-16 content labeled "Artículo 17" when both 16 and 17 are in the set)
  and risks deleting a real citation.
