# 0025 — Low-RAM fallback model: Gemma 3 1B replaces Qwen3-1.7B

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0015 named Qwen3-1.7B-Instruct as the low-RAM fallback. Phase 1
(2026-07-23) measured it fabricating complete fiction on a long norm, twice,
exit code 0 both times — a well-formed, plausible-looking explanation of a law
that does not exist. A 2026-07-30 investigation deepened this rather than
resolving it: across four separate test runs of the same law on the same model
(two on a capped WSL2 Debian environment, two native on Windows, two different
llama.cpp builds), the outcomes were faithful, faithful, vacuous, and
fabricated-a-different-law — four different results with no split explained by
build version or platform. ROADMAP.md records the conclusion plainly: "the
low-RAM model's faithfulness is not currently predictable run to run, on any
binary tested so far."

Gemma 3 1B (`ggml-org/gemma-3-1b-it-GGUF`) was tried the same day as a
candidate replacement and failed outright on a different axis: the output
contract. `explain()`'s parser correctly rejected the response
(`ParseError: La respuesta del modelo no trae las secciones: en una frase`)
because it never produced the required "en una frase" section. That was a
single, non-repeated attempt, and nothing was concluded about Gemma's
faithfulness from a run that failed before faithfulness could even be
assessed. Separately, Gemma 3's technical report documents a pretraining data
mixture specifically revised to improve multilingual/Spanish performance —
the strongest verified Spanish-language rationale among the small candidates
surveyed (LFM2/LFM2.5-1.2B, whose pretraining mix is ~75% English; Phi-4 Mini,
evaluated in ROADMAP only as a speed reference point, never for Spanish).
ADR 0024 waives ADR 0015's OSI/no-revocation licensing bar for this slot
specifically, clearing the one non-faithfulness objection to Gemma.

## Decision

The low-RAM fallback slot changes from Qwen3-1.7B-Instruct to **Gemma 3 1B**
(`ggml-org/gemma-3-1b-it-GGUF`, Q4_K_M), chosen for its verified Spanish/
multilingual pretraining strength among the small candidates surveyed. This is
adopted as the fallback going forward, **not as a validated replacement**: the
one prior attempt failed on the output contract before faithfulness could be
assessed at all, so this decision commits to (a) fixing the output-contract
failure — the prompt or parser must work with this model's instruction-
following behavior — and (b) then running the same faithfulness battery
Qwen3-1.7B was subjected to (repeated runs on the same document, citations
spot-checked against source) before this model can be considered proven. The
default model slot (Qwen3-4B-Instruct, Apache 2.0) is unchanged by this ADR.

## Consequences

- Ships with an **open implementation item**: the output-contract failure
  (missing "en una frase" section) must be fixed before this model can run
  end to end. This ADR records the decision to adopt Gemma, not that it
  already works.
- Faithfulness on Gemma 3 1B is currently **unverified in either direction** —
  zero data points, against Qwen3-1.7B's four inconsistent ones. This is a bet
  that a model with genuinely stronger verified Spanish pretraining is more
  likely to be reliably faithful, not a measured improvement over the model it
  replaces.
- Depends on **ADR 0024**'s licensing waiver for this slot. If that waiver is
  ever reversed, this model choice needs revisiting too.
- Qwen3-1.7B's specific, measured failure — confident fabrication of an
  entire invented law, exiting cleanly — remains the historical record and the
  reason a replacement was sought, even after the swap; Phase 1's finding is
  not retracted by this decision.

## Alternatives considered

- **Phi-4 Mini** — genuinely MIT-licensed, no conflict with ADR 0015's bar at
  all, but zero testing on Spanish or on faithfulness for this task; rejected
  for now in favor of the candidate with a verified Spanish-quality rationale,
  not on any measured faithfulness comparison.
- **LFM2 / LFM2.5-1.2B** — Apache-based license but with a USD 10M-revenue
  commercial-use cap (not strictly OSI either), and a pretraining mix reported
  as ~75% English; weaker Spanish signal than Gemma 3 and no licensing
  advantage over it. Rejected.
- **Characterize Qwen3-1.7B further before replacing it** — run a larger,
  controlled batch to explain the four-way inconsistency before deciding
  anything. Considered and set aside: Felipe chose to move to a replacement
  candidate now rather than spend another session on the incumbent model.
- **Feed the existing fallback only retrieved/relevant excerpts instead of the
  whole document** — targets document length as the possible trigger for
  fabrication rather than swapping models. Rejected for this decision as a
  separate, deferred capability (it reopens ADR 0017's "no query in the
  explain task" call and needs its own brainstorming round per the retrieval
  design spec); tracked there, not here.

This ADR is a follow-on to **ADR 0015** (supersedes its fallback-model choice
only; the 4B default is untouched) and depends on **ADR 0024** (the licensing
waiver that clears this model for the fallback slot).
