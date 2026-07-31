# 0027 — Spec-based local model selection: fit the largest model the machine can run

- **Status:** Accepted — follow-on to [ADR 0015](0015-local-model-selection-qwen3.md);
  depends on [ADR 0023](0023-vulkan-build-and-device-verification.md) for the GPU path.
- **Date:** 2026-07-31
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0003 fixed a config-driven engine with "a default plus a low-RAM fallback";
ADR 0015 named them (Qwen3-4B default, a small fallback — now Gemma 3 1B per
ADR 0025) but left *which one runs on a given machine* to configuration and a
later decision. That decision was never made, and the code shows it:
`LocalProvider._ensure_server` (`src/leyllana/engine/local.py`) always starts the
**default** model, with a standing comment that "la seleccion automatica por RAM
del fallback queda para mas adelante." So today an 8 GB conservative-floor machine
(ADR 0015's own reference hardware) is handed the 4B unconditionally and can OOM or
swap-thrash on it, while the fallback tier is never reached without a manual config
edit. `llama.cpp` pre-allocates the whole KV cache at startup, so this failure lands
at server start, not mid-run.

The 2026-07-31 4B diagnostic (ROADMAP, "4B diagnostic" section) makes the tier a
real trade-off, not a wash: on Ley 19.628 the 4B default scored 3/3 faithful versus
0/3 on the 1.7B measured earlier, a genuine capability gain — but at ~18 min per run
on the CPU-only binary, roughly 10x the small model and impractical for a user. So
the faithful model needs a capable machine (and, on the GPU path, ADR 0023's Vulkan
build); the fast model is the one a weak machine can actually use. Picking between
them per machine is exactly the decision.

## Decision

**Auto-select the largest configured local model whose memory footprint fits a safe
fraction of the live backend's memory. An explicit model pin in `leyllana.toml`
always wins; auto-selection only fills the choice when none is pinned.**

- **Fill-only.** Selection runs as `auto` (parallel to the existing `gpu = "auto"`).
  When the user has pinned a model, that is honored unconditionally — the machine's
  specs never override a human's explicit choice (consistent with ADR 0021, the GUI
  owning the config). Auto only decides when the choice is left to it.
- **Basis: the live backend's memory.** On the CPU path, measure total system RAM.
  On the GPU path, read VRAM from the device list the binary itself reports
  (ADR 0023) — not a guess. Whichever backend is actually live is the one measured.
- **Safe fraction: ~60%.** A model is eligible only if its footprint fits under ~60%
  of that memory. On the 8 GB floor that is ~4.8 GB, matching ADR 0015's own "~5 GB
  usable after the OS" figure and leaving headroom for the OS, a browser, and KV
  growth.
- **Footprint = model file + KV cache at the configured ctx.** Computed from the
  actual GGUF file size on disk plus an estimate of the KV cache `llama.cpp`
  pre-allocates for the whole configured context. ADR 0015 warns the KV cache
  overtakes the model at long context; counting the file alone understates real
  memory at the exact moment the server starts. Reading the real file size (rather
  than a hardcoded per-model table) keeps the estimate correct when the user points
  the config at a different GGUF.
- **Floor: never refuse to run.** If even the smallest configured model exceeds the
  safe fraction, run it anyway and record a visible warning that it is over budget.
  A degraded run beats a refusal on the low-end machines this tool is for (ADR 0012:
  CPU / run-anywhere is a first-class configuration).

## Consequences

- ADR 0003/0015's "default plus low-RAM fallback" stops being aspirational: a
  low-RAM machine is routed to the fallback automatically instead of OOMing on the
  4B, and a capable machine gets the faithful 4B without a manual edit.
- **Depends on ADR 0023, which is Accepted but not yet implemented.** On CPU the
  RAM measurement works today. On the GPU path, `resolve_gpu_layers` still guesses
  from `nvidia-smi` and the bundled binary is CPU-only, so reading a real VRAM
  figure is blocked until 0023 lands. Until then, GPU-path auto-selection is pending;
  the CPU path is the shipping behavior.
- It selects *into* the fallback tier (Gemma 3 1B, ADR 0025), which is adopted but
  not yet validated for faithfulness. Auto-selection inherits that open item: this
  ADR decides the *mechanism*, not the fallback model's quality.
- New, small failure surface: one RAM read plus a couple of file stats at startup,
  and (on GPU) one device-list probe. Latency is negligible.
- The KV estimate is approximate; a wrong estimate could mis-pick a model near the
  ~60% boundary. Accepted — the fraction is deliberately below full memory to give
  that margin.
- If memory cannot be measured at all (a transient probe failure), auto-pick runs
  the smallest configured model and warns, rather than trusting a model it could not
  justify — consistent with the floor rule above.

## Alternatives considered

- **Keep running the default unconditionally (today's behavior).** Simplest — no new
  code. Rejected: it hands the ~18-min-per-run, capable-machine-only 4B to an 8 GB
  floor machine and can OOM at server start, and never reaches the fallback without a
  manual edit. This is the exact gap the standing `local.py` comment names.
- **A hardcoded per-model footprint table (model name → GB).** Rejected: brittle, and
  wrong the moment the user points the config at a different GGUF. Reading the actual
  file size plus a ctx-based KV estimate is self-updating.
- **Key off CPU core count or a micro-benchmark instead of memory.** Rejected: the
  measured failure is memory *fit* (KV pre-allocation, OOM at startup), not compute.
  Speed is a separate axis — handled by ADR 0023 on the GPU path — and is not what
  makes a run fail to start.
- **Partial GPU offload by layer count as the selection lever.** Rejected for this
  ADR: `-ngl` layer count is already `resolve_gpu_layers`' job. Model-tier selection
  is the coarser first decision and composes with it.
