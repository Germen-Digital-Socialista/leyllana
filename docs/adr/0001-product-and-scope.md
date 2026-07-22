# 0001 — Product and scope: a plain-language Chilean law explainer

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

Germen Digital Socialista (GDS) needs a first, concrete tool. The founding idea
is to make AI useful for legislation — both legislating about AI and using AI to
make dense legislation readable. The second is the more immediately tool-shaped
and addresses a real, widely felt pain: Chilean laws and *boletines* are hard to
read even for lawyers, legislators, and the public.

## Decision

leyllana v1 is a single-purpose tool: given the text of a Chilean law or
*boletín*, produce a plain-Spanish, structured explanation. The name comes from
"lenguaje llano" (plain language). It is GDS's flagship repository.

Scope is deliberately narrow: one job done well. Explaining a law — not
comparing, not answering arbitrary questions, not tracking legislation.

## Consequences

- A tight, demoable v1 that party members, staffers, and journalists can run.
- Everything else (diffing, Q&A, tracking) is pushed to future tools, keeping v1
  achievable.
- The product's value depends on faithfulness (see ADR 0008); a plausible but
  wrong explanation is worse than none.

## Alternatives considered

- **Summarize + redline what changed** — more useful to staffers but more
  technical and less universal; deferred.
- **Q&A over a law** — powerful but larger surface and higher fabrication risk.
- **Track/scan AI-related bills** — serves the other GDS mission but is a
  scraping/monitoring product, not a readability tool; deferred.
