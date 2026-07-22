# 0005 — Local-first and data sovereignty by default

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

leyllana processes legal and legislative text, sometimes before it is public or
while it is politically sensitive. The org's values (Germen Digital Socialista)
frame public understanding of the law as something that should not depend on a
foreign cloud or a paid subscription. MuniGPT already proved a fully-offline
posture is viable for Chilean legal text.

## Decision

**Local-first is the default and the network path is opt-in.** With the default
provider (ADR 0003), leyllana makes no network calls: input handling, inference,
and output all happen on the user's machine. Any data leaving the machine
requires an explicit user action — choosing a cloud provider (ADR 0004).

## Consequences

- The default experience is private and works with the network disabled.
- Local-first is both a privacy property and the org's political stance, stated
  plainly in the README and PRD.
- The URL-input feature (ADR 0006) is the one default-path network touch, and
  only fetches a public source the user explicitly pointed at.
- Some quality ceiling on the local model vs. frontier cloud models, accepted as
  the cost of sovereignty; cloud is there for users who choose it.

## Alternatives considered

- **Cloud-by-default with a local option** — better out-of-box quality, but
  inverts the org's posture and sends legal text off-machine by default.
