# 0010 — Public repository and naming

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

leyllana is the first repository under the `Germen-Digital-Socialista` GitHub
organization (0 repos before it). Two decisions had to be fixed at creation time:
the repository name and its visibility.

## Decision

- **Name:** `leyllana` — the repository equals the product; the name derives from
  "lenguaje llano" (plain language).
- **Visibility:** **public from the first commit.** Open source from day one fits
  the org's transparency ethos and invites contributors early.
- **README:** ships flashy from commit #1 — logo, static badges, SEO-friendly
  description, and topics/tags — and is written in Spanish via the `voz-de-felipe`
  skill (see repo `CLAUDE.md`).

## Consequences

- The org debuts publicly with this repo, so the first commit must already look
  intentional (README, LICENSE, logo, docs), not a bare scaffold.
- Future GDS tools can follow the same repo conventions; a `gds-*` prefix was
  considered and left optional for later tools.
- Being public from the start means the early, pre-code state is visible; the
  README sets expectations (early access / work in progress).

## Alternatives considered

- **Private until launch** — safer first impression, one command to flip later,
  but rejected in favor of open-from-day-one.
- **`gds-leyllana` / `ley-llana` / `decodificador`** — naming variants; `leyllana`
  chosen as the cleanest product-equals-repo name.
