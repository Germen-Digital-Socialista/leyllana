# 0024 — License-bar exception for the low-RAM fallback slot only

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0015 set a project-wide licensing bar: every shipped local model must be
OSI-permissive with no usage caps or remote-revocation clauses, reasoning from
leyllana's sovereign, AGPL-3.0 posture (ADR 0005, 0009). That ADR rejected
Gemma 2-4B on exactly this ground: Google's Gemma Terms of Use are confirmed
non-OSI and remotely revocable — Google grants itself the right to restrict or
terminate access if it judges a use in violation of its Prohibited Use Policy,
and that policy must be passed downstream to every user of a product built on
Gemma.

Separately, the low-RAM fallback slot's incumbent (Qwen3-1.7B, Apache 2.0) has
an unrelated problem: unpredictable faithfulness. ROADMAP.md (2026-07-30)
records four test runs of the same law on the same model producing four
different outcomes — faithful, faithful, vacuous, and a fabricated,
entirely invented different law — with no explanation tying the split to build
version or platform. Gemma 3 1B is the strongest verified Spanish/multilingual
candidate among the small models surveyed (its technical report documents a
pretraining mixture specifically revised to improve non-English performance),
but adopting it for the fallback slot requires accepting the same license
ADR 0015 already rejected.

Felipe's own estimate of this tool's expected scale — a small pilot within his
party, on the order of ten users — is the basis for treating this as a
scoped, low-exposure exception for one model slot, not a reversal of the
project's licensing stance as a whole.

## Decision

For the **low-RAM fallback slot only**, ADR 0015's OSI-permissive /
no-remote-revocation bar is waived. The fallback model may ship under Google's
Gemma Terms of Use, including its Prohibited Use Policy and Google's unilateral
right to restrict or terminate access. The default model slot (Qwen3-4B,
Apache 2.0) is unaffected and keeps ADR 0015's bar in full.

## Consequences

- leyllana's licensing posture is no longer "every shipped model is
  OSI-permissive," but "every shipped model except the low-RAM fallback." This
  must be stated plainly wherever the project documents its licensing stance
  (README, PRD), not left implicit.
- Google retains a unilateral, remote right to restrict or terminate use of the
  fallback model — a risk ADR 0015 ruled out for the project as a whole.
  Accepted here on the basis of small, known user scale, not on a judgment that
  the risk is negligible in general.
- leyllana must carry Google's Prohibited Use Policy forward to its own users
  for this one model component, an obligation the AGPL-3.0 license covering
  leyllana's own code (ADR 0009) does not otherwise impose.
- If usage ever grows past the small-pilot scale this waiver was scoped
  against, it should be revisited — the reasoning here is scale-dependent, not
  a general judgment that the licensing risk is acceptable.

## Alternatives considered

- **Hold ADR 0015's bar for every model, fallback included** — rejected for
  this decision; would leave Phi-4 Mini (MIT, no conflict) or LFM2/LFM2.5-1.2B
  (Apache-based but with a USD 10M-revenue commercial-use cap, so not strictly
  OSI either) as the only replacement candidates, both untested for Spanish or
  faithfulness on this task.

This ADR is a follow-on to **ADR 0015** (qualifies its licensing criterion for
the fallback slot only; the default-model criterion is untouched) and clears
the licensing objection that **ADR 0025** (fallback model swap) depends on.
