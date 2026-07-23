# 0016 — Local llama.cpp runtime: managed llama-server subprocess behind a pluggable backend

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0003 set a local `llama.cpp` default "mirroring the MuniGPT approach", and the
Phase 1 skeleton encoded that as a `llama-cpp-python` (in-process binding) optional
extra. Implementing the provider surfaced that MuniGPT does **not** use the
in-process binding: it runs the official `llama.cpp` `llama-server` binary as a
managed subprocess and calls its OpenAI-compatible `/v1/chat/completions` endpoint
with `--jinja`, so the GGUF's own chat template is applied.

MuniGPT made that choice for a concrete reason: prebuilt `llama-cpp-python` wheels
depend on specific CPU instruction sets and crash ("illegal instruction") on some
end-user hardware. That is exactly the diverse, low-end floor leyllana targets
(ADR 0015): a machine we do not control, where a generic wheel can fail to run at
all. So "mirror MuniGPT" points at the server binary, not the Python binding.

## Decision

The engine layer keeps its existing provider abstraction (ADR 0003): callers depend
only on `explain(...)`, and providers implement a small `generate(prompt) -> str`
Protocol. The local provider is backed by a **managed `llama-server` subprocess**:

- Bundle or point at the official `llama.cpp` `llama-server` binary. leyllana does
  not compile a Python binding on the user's machine.
- Start it as a managed subprocess bound to a loopback port, wait until it reports
  healthy, and stop it on shutdown.
- Call `POST /v1/chat/completions` (OpenAI-compatible) with the system and user
  messages, running the server with `--jinja` so the GGUF's embedded chat template
  is used (correct for Qwen3).
- Model path, context size, thread count, and GPU offload (`-ngl`, ADR 0012) come
  from config.

The provider interface is written so an in-process `llama-cpp-python` backend can be
added later behind the same `generate(...)` Protocol without touching callers. Only
the subprocess backend is implemented for v1 (the decision was to abstract both,
build the server backend now).

This **refines ADR 0003** (the "mirror MuniGPT" intent) and **applies ADR 0012**
(GPU offload via `-ngl`, CPU fallback). It supersedes the Phase 1 skeleton's
implicit in-process assumption and changes the engine optional dependency from
`llama-cpp-python` (a build-fragile pip package) to a light HTTP client plus the
external `llama-server` binary. It does not supersede ADR 0003's swappable-provider
or local-default decision, which stand.

## Consequences

- Distribution uses official prebuilt `llama.cpp` binaries, selectable per CPU
  capability, avoiding the wheel / CPU-instruction fragility that breaks in-process
  bindings on low-end machines.
- `--jinja` means leyllana never hand-formats Qwen3's chat template; the model's own
  template travels inside the GGUF.
- Cost: the provider manages a subprocess lifecycle (start, health check, port,
  shutdown) and makes a local HTTP call — more moving parts than a direct function
  call, and a class of failure (port in use, server did not become healthy) to
  handle loudly.
- The `llama-server` binary is an external artifact, not a pip dependency. Packaging
  it with the installer is Phase 4; in headless and dev use its path is
  config-driven.
- The engine extra no longer needs `llama-cpp-python`; a light HTTP client covers
  the server call. A future in-process backend can reintroduce `llama-cpp-python` as
  its own optional extra without disturbing callers.

## Alternatives considered

- **In-process `llama-cpp-python` binding** — simplest (pure Python, no subprocess
  or HTTP), but prebuilt wheels require specific CPU instructions and crash on some
  low-end or older CPUs; rejected as the v1 default for the conservative floor, kept
  as a possible future backend behind the same interface.
- **Hand-formatted raw completion against `llama-server`'s `/completion`** — more
  token-level control, but re-implements Qwen3's chat template and risks drift;
  rejected in favor of `/v1/chat/completions` with `--jinja`.
- **A full Python `llama.cpp` build step in the installer** — most control over the
  binary, but heavy and brittle to build per machine; rejected.
