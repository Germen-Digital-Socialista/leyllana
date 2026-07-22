# 0008 — Anti-invention and not-legal-advice guardrails

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

A tool that explains law is only trustworthy if it never invents legal content.
An LLM that fabricates an article number, an obligation, or a figure is worse
than no tool, because the output looks authoritative. This mirrors both the
org's house rule ("never invent facts") and MuniGPT's product requirement.
Separately, the tool must not be mistaken for legal advice.

## Decision

Two non-negotiable guardrails apply to every provider (local and cloud):

1. **Anti-invention.** The prompt (built by the `prompt` layer) instructs the
   model to ground its explanation strictly in the provided text and to never
   invent articles, *norma* ids, *boletín* numbers, citations, figures, dates, or
   obligations. If the text is insufficient to answer a section, the tool says so
   explicitly instead of guessing.
2. **Not legal advice.** Every explanation carries a visible footer stating it is
   an aid to understanding, not *asesoría legal*, and that legal questions belong
   with a qualified lawyer.

## Consequences

- Faithfulness is a first-class, testable property (spot-check: every article or
  figure named must be present in the input).
- The tool may sometimes answer "no se puede determinar con este texto" — this is
  a feature, not a defect.
- These guardrails are enforced in the shared prompt layer, so swapping providers
  (ADR 0003) cannot bypass them.

## Alternatives considered

- **Trust the model / no explicit guardrail** — rejected; fabrication risk is the
  central failure mode for this product.
- **Post-hoc citation checking only** — useful later, but the prompt-level ban is
  the minimum bar for v1.
