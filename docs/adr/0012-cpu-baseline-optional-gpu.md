# 0012 — CPU baseline with optional GPU acceleration

- **Status:** Accepted — supersedes the CPU-only constraint of [ADR 0003](0003-swappable-engine-local-default.md).
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0003 chose a swappable engine with a local `llama.cpp` default and pinned
that default as **CPU-only**, mirroring MuniGPT. CPU-only guarantees the tool
runs anywhere and keeps the local-first promise, but it leaves real performance
on the table: local `llama.cpp` inference over legal-length documents is slow on
CPU, and many target machines — including likely pilot hardware — have a usable
GPU sitting idle. We want the run-anywhere guarantee of CPU without forbidding
acceleration where it exists.

## Decision

**The performance baseline is CPU; GPU is an optional accelerator.**

- The tool must run fully on CPU with no GPU present. That remains the guarantee,
  and CPU is the assumption for packaging, testing, and support.
- When a compatible GPU is detected, the local engine may use it to accelerate
  inference. This is **config-driven**, with a safe default that never fails on a
  CPU-only machine (fall back to CPU when GPU/drivers are absent).
- GPU is an optimization, never a requirement. A machine with no GPU is a
  first-class, supported configuration, not a degraded one.

This supersedes **only** the "CPU-only" constraint of ADR 0003. The rest of
ADR 0003 — swappable provider, local `llama.cpp` default, config-driven model
selection — stands unchanged.

## Consequences

- The offline / sovereign guarantee is intact: CPU-only stays fully supported and
  is the baseline everything is tested against (ADR 0005).
- Users with a GPU get materially faster local inference without switching engine
  or provider.
- Added complexity: GPU detection, a config switch to force CPU or GPU, and
  testing both paths. Accepted as the price of not throttling capable hardware.
- Packaging targets CPU as the floor; GPU support must degrade cleanly to CPU
  when hardware or drivers are missing.

## Alternatives considered

- **Keep CPU-only (ADR 0003 as written)** — simplest and maximally portable, but
  needlessly slow for users who have a GPU; that gap is the reason to revisit.
- **GPU-required or GPU-by-default** — fastest where available, but breaks the
  run-anywhere / local-first guarantee on low-end machines; rejected.
- **Manual-only GPU flag, no auto-detect** — safe but most users would never
  enable it; config-driven auto-detect with a CPU fallback and an override is the
  better default.
