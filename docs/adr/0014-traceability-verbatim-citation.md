# 0014 — Traceability by verbatim citation

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0008 bans invention: the model must ground its output in the input and never
fabricate articles, numbers, citations, or obligations. That is a *negative*
guarantee — do not invent. Trust also needs a *positive* one: when the
explanation names an article, figure, date, or obligation, a reader must be able
to find that exact thing in the source and confirm it. Paraphrasing a citation,
even faithfully, makes spot-checking harder and blurs the line between what the
source says and what the model rephrased. Full clickable span-linking of each
mention to its source fragment is desirable but heavier than v1 warrants.

## Decision

**Traceability in v1 is by verbatim citation.** Every article, figure, date, or
obligation named in the explanation must use the wording exactly as it appears in
the source, so each can be spot-checked against the input by a simple text match.

This is the positive complement of the ADR 0008 anti-invention guardrail and is
enforced through the same prompt layer. Full clickable span-linking — each
mention hyperlinked to its exact source fragment — is **deferred to the ROADMAP**;
it is a richer traceability mechanism layered on top of this rule, not a change
to it.

## Consequences

- Faithfulness is checkable by anyone: a named article or figure can be found
  verbatim in the source, with no tooling required.
- Reinforces ADR 0008 — verbatim quoting is the mechanism that makes "never
  invent" auditable rather than merely asserted.
- Some stylistic cost: the plain-language explanation must still quote key legal
  terms exactly rather than smoothing them, which the `nivel` register (ADR 0007)
  has to accommodate.
- Sets up, but does not build, the deferred span-linking feature; the verbatim
  rule is the foundation it will attach to.

## Alternatives considered

- **Faithful paraphrase (no verbatim requirement)** — reads more smoothly, but
  makes each claim harder to verify and blurs source versus model; rejected for a
  legal-explanation tool.
- **Full clickable span-linking now** — best traceability, but heavy to build and
  maintain against variable source formats; deferred to the ROADMAP.
- **Post-hoc citation-checking pass** — useful later, but the prompt-level
  verbatim rule is the minimum bar for v1 (same reasoning as ADR 0008).

This ADR complements ADR 0007 and ADR 0008; it does not supersede them.
