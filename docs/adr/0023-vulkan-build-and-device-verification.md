# 0023 — Vulkan `llama-server` build, and verifying the device instead of guessing

- **Status:** Accepted — complements [ADR 0012](0012-cpu-baseline-optional-gpu.md) and [ADR 0016](0016-llama-server-subprocess-runtime.md).
- **Date:** 2026-07-29
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0012 decided the policy: CPU is the baseline, GPU is an optional accelerator,
config-driven, with a safe fallback on a machine without one. ADR 0016 decided the
runtime: a managed `llama-server` subprocess, "bundle or point at the official
`llama.cpp` binary". Neither says **which** official build, because at the time it
did not appear to be a distinguishable choice.

It is. Measured 2026-07-29 on the development machine:

- The binary in `backend/bin` (b9929) is a **CPU-only build**. It contains no
  `ggml-cuda.dll`, no `ggml-vulkan.dll`, no GPU backend of any kind, and
  `llama-server --list-devices` prints an empty list.
- `engine.gpu = "auto"` resolves through `resolve_gpu_layers`, which probes for
  `nvidia-smi` on the `PATH`, finds it, and passes `-ngl 999` to that binary. The
  binary ignores it silently. **The config has been reporting a GPU path that cannot
  exist**, and every performance figure previously recorded as "GPU" was CPU.
- A GPU-capable build on the same machine and the same GGUF does the same call at
  **1278 vs 85 tok/s** prompt processing and **35 vs 11 tok/s** generation. Combined
  with a larger context it takes one real norm (Ley 21.663, 99.468 characters) from
  **22,9 min to 4,8 min**.

So ADR 0012's promise is currently unimplementable with what we ship, and the failure
is silent, which is the mode this project treats as worst.

## Decision

**Ship a Vulkan build of `llama-server` as the GPU path, keep a CPU build as the
baseline, and make the GPU mode verify the device rather than infer it.**

- The bundled GPU binary is the official `llama.cpp` **Vulkan** build. One artifact
  covers NVIDIA, AMD, Intel and older GPUs.
- CPU remains the baseline exactly as ADR 0012 states. A machine with no usable GPU
  stays a first-class configuration, and the CPU build stays supported and tested.
- **`gpu = "auto"` must ask the binary what it can actually use**, not guess from the
  presence of an unrelated tool. `nvidia-smi` on the `PATH` says nothing about the
  backend compiled into our binary, and on the evidence above it says the wrong
  thing. Detection reads the device list the binary itself reports.
- **The engine records which device it ended up on, and the reason.** When GPU was
  requested and is not available, that is stated rather than absorbed. A silent
  fallback to CPU is a 5x slowdown presented as normal operation, which is the exact
  shape of failure that made the earlier numbers uninterpretable.

## Consequences

- ADR 0012's optional-GPU promise becomes true instead of aspirational, on NVIDIA,
  AMD and Intel alike.
- The Phase 4 installer grows by a second binary set, and packaging must pick between
  them at install or run time. Accepted: the alternative is shipping a GPU switch that
  does nothing.
- Vulkan is measurably slower than CUDA on NVIDIA — published comparisons put CUDA
  ahead by roughly 36% on prompt processing and 10% on generation. Accepted, because
  that gap is small next to the 15x and 3x gap against CPU, and because a single
  artifact that also serves integrated Intel and AMD graphics matches the hardware
  this tool is actually for.
- The Vulkan build compiles its shader pipelines on first use (~27 s, measured cold
  then warm). The first run after installation is slower than every run after it, and
  a progress indicator that goes quiet there will look like a hang (FR-10).
- Detection and device reporting add code and a second path to test, and the CPU-only
  case must keep working with no GPU binary present at all.
- Trusting the binary's own device list means the check depends on invoking it, which
  is one more startup cost and one more thing that can fail; failing that check must
  fall back to CPU rather than abort.

## Alternatives considered

- **CUDA build for NVIDIA, plus a CPU fallback.** Fastest on the development machine.
  Rejected: two artifacts to bundle and choose between, a larger installer, no benefit
  for AMD or Intel users, and llama.cpp issue #24744 documents Windows update flows
  replacing a CUDA build with a Vulkan or CPU one — a silent regression on precisely
  this setup, which is how the current CPU-only build plausibly arrived.
- **Stay CPU-only and remove the GPU claim.** Honest and the simplest to package, and
  it would have meant superseding ADR 0012 rather than complementing it. Rejected: it
  discards a measured 4 to 5x on likely pilot hardware, on the very axis the pilot is
  meant to evaluate (ROADMAP Phase 4).
- **Bundle CPU only and let the user point `server_path` at their own GPU build.**
  Costs nothing to package and keeps ADR 0012 intact. Rejected: the target user is
  non-technical (PRD section 4), so in practice this is CPU-only for everyone the
  decision is about.
- **Leave `gpu = "auto"` probing `nvidia-smi`.** Rejected on the measurement above: it
  returns the wrong answer on this machine today, and a detector that is confidently
  wrong is worse than no detector.
