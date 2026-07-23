# 0003 — Swappable engine with a local llama.cpp default

- **Status:** Accepted. The CPU-only constraint is superseded by [ADR 0012](0012-cpu-baseline-optional-gpu.md); the swappable-engine and local-`llama.cpp`-default decision stands.
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

The "explain in plain language" step is an LLM task. The tool must respect the
org's local-first, sovereign posture while still allowing higher-quality cloud
models when a user wants them. Options ranged from local-only, to cloud-only, to
a configurable abstraction.

## Decision

Expose a single interface, `explain(text, nivel) -> structured result`, backed by
a **config-driven, swappable provider**. The **default provider is a local
`llama.cpp` model** (a light Qwen-class model, CPU-only), mirroring the MuniGPT
approach. Cloud providers (Claude, OpenAI/Codex, Gemini) are opt-in (see
ADR 0004).

Model selection is config-driven, not hardcoded — a default model plus a low-RAM
fallback, following MuniGPT's `models` config block pattern.

## Consequences

- The app works fully offline out of the box; cloud is never required.
- Callers (GUI, tests) depend only on `explain(...)`, not on any provider.
- A prompt/guardrail layer (ADR 0008) sits in front of every provider uniformly.
- Some plumbing cost for the abstraction, accepted as the price of not locking
  the org's flagship into one vendor.

## Alternatives considered

- **Local-only** — maximal sovereignty, but no path to higher-quality cloud
  output when a user has access.
- **Cloud-only (e.g. Claude API default)** — best demo quality, but abandons the
  offline/sovereign story that is core to GDS.
