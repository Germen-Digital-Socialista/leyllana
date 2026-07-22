# 0007 — Output contract: structured Spanish sections and audience levels

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

The problem statement is that dense law is unreadable "even for senators and the
public" — two audiences with different needs. Free-form prose summaries are
harder to scan and easier to pad with filler.

## Decision

The engine returns a **fixed structured output** in Spanish with these sections:

- **Qué hace** — what the norm does.
- **A quién afecta** — who it binds / affects.
- **Artículos clave** — the key articles, in plain language.
- **En una frase** — a single-sentence takeaway.

A **`nivel`** control selects the audience register: `publico` (general public)
or `tecnico` (legislator / staffer). `nivel` changes tone and depth only, never
the facts.

Output is shown in the GUI and exportable to Markdown (PRD FR-8).

## Consequences

- Scannable, consistent results that are easy to compare across laws.
- The same input serves both a citizen and a staffer via `nivel`.
- Fixed sections make faithfulness checks (ADR 0008) easier: each section can be
  checked against the source.

## Alternatives considered

- **One flowing prose summary** — simplest, but harder to scan and no audience
  toggle.
- **Structured sections, single audience** — loses the citizen-vs-staffer split
  that the core problem demands.
- **TL;DR one-liner only** — punchy for social media, too thin as the primary
  output.
