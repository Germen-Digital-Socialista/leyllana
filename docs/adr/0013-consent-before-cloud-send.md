# 0013 — Explicit consent before sending content to a cloud provider

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0004 allows opt-in cloud providers; ADR 0005 makes local-first the default
and states that any data leaving the machine requires an explicit user action.
Choosing a cloud provider once is not enough on its own: a user could select a
provider and then forget that every subsequent document is being sent off-
machine. Because leyllana processes legal and legislative text that may be
sensitive or not yet public, the moment of sending must be unmistakable — this is
both a privacy property and the org's political posture.

## Decision

**No document content reaches a cloud provider without an explicit consent step.**

Before any content is sent to a cloud provider, the app presents an unmistakable
confirmation that:

1. states plainly that the document will leave the machine, and names the
   provider it is going to, and
2. requires an affirmative action to proceed.

The default local path is untouched by this: it makes no network calls and shows
no consent prompt. The exact UX — consent on every send versus a remembered
per-session consent, and the precise wording — is a GUI-phase detail. The non-
negotiable is that sending is never silent, never a default, and never the
consequence of a stale setting alone.

## Consequences

- The default local experience is unchanged: nothing leaves the machine and no
  prompt appears (ADR 0005).
- A user cannot send sensitive legal text to a third party by accident or via a
  forgotten setting.
- Slight friction on the cloud path, accepted deliberately — that friction is the
  point of the guardrail.
- The consent copy is user-facing Spanish and must name the provider and the fact
  of leaving the machine; vague wording does not satisfy this ADR.

## Alternatives considered

- **Provider selection is consent enough (no separate step)** — simplest, but
  lets a one-time choice silently apply to every later document; rejected, that is
  the exact risk this ADR addresses.
- **Consent once per session, remembered** — a reasonable middle ground; left as
  a GUI-phase decision *within* the rule that the first send is always explicit.
- **A global settings toggle only** — easy to forget it is on; rejected as the
  sole mechanism.

This ADR complements ADR 0004 and ADR 0005; it does not supersede them.
