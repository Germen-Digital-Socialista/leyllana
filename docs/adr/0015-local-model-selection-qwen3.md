# 0015 — Local model selection: Qwen3-4B default, Qwen3-1.7B low-RAM fallback

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0003 fixed a swappable engine with a local `llama.cpp` default and
config-driven model selection (a default plus a low-RAM fallback), but left the
concrete model unnamed. ADR 0012 set CPU as the performance baseline with GPU as
an optional accelerator. Phase 1 now needs an actual model to run, and it should
be chosen from the target hardware inward, not copied from a sibling project.

The target is deliberately the **conservative floor** of Chilean public-sector
and general-public hardware, not a developer workstation. The reference machine
for that floor is the class distributed through state programs (Becas TIC /
"PC del Gobierno"): an Intel Core i3-N300 (2023) with 8 GB RAM and a 128 GB SSD —
a low-power Alder Lake-N CPU (AVX2, no AVX-512), no discrete GPU. After the
operating system, roughly 5 GB of RAM is usable, and the small SSD makes model
file size a real constraint.

Two forces narrow the choice:

- **Fit.** In Q4_K_M, a 1.5-2B model is about 1-1.6 GB, a 3-4B model about
  2-2.5 GB, and a 7B model about 4.1 GB before runtime and KV cache. `llama.cpp`
  pre-allocates the KV cache for the whole context at startup, and at long
  context the cache overtakes the model, so a 7B model at any useful context does
  not fit the ~5 GB budget. 3-4B is the practical ceiling; ~1.5-2B is the
  comfortable floor. Inference on N-series CPUs is slow (single-digit
  tokens/second).
- **License.** leyllana is a sovereign, public-good, AGPL-3.0 tool. That argues
  for an OSI-permissive model with no usage caps or remote-revocation clauses.
  Qwen2.5-3B ships under the non-commercial Qwen Research License (a trap: its
  1.5B and 7B siblings are Apache 2.0, but not the 3B). Llama 3.2 uses Meta's
  custom license (700M monthly-active-user cap, EU restrictions, not OSI). Gemma
  uses Google's terms (remotely revocable, not OSI). The Qwen3 family (0.6B to
  235B) is uniformly Apache 2.0. Salamandra (Barcelona Supercomputing Center) is
  Apache 2.0 and Spanish-native, but ships without RLHF alignment and with weaker
  reasoning at 2B.

## Decision

The default local model is **Qwen3-4B-Instruct** (Q4_K_M), with
**Qwen3-1.7B-Instruct** (Q4_K_M) as the low-RAM fallback. Both are Apache 2.0.

- Both models are read from config by path (ADR 0003); nothing is bundled here.
  Packaging the default model with the installer is Phase 4.
- The engine maps the `Prompt(system, user)` onto `llama.cpp`'s **chat-completion**
  API, applying each model's chat template, rather than hand-formatting a raw
  completion string.
- GPU use follows ADR 0012: **auto-detect a compatible GPU and offload when
  present, fall back cleanly to CPU otherwise**, with a config override to force
  CPU or GPU. The 8 GB CPU floor never depends on a GPU.
- Generation defaults are conservative and config-driven: a capped context (about
  8K, so the KV cache fits the floor), a low temperature to curb invention
  (ADR 0008), and long *boletines* processed in fragments rather than a single
  long-context pass. Exact values are tuned during the pilot (Phase 4), not fixed
  here.

Salamandra remains a documented alternative worth benchmarking against Qwen3 on
real *boletines* during the pilot. If it produces more faithful Spanish legal
explanations, a later ADR can switch the default.

## Consequences

- The default runs within the ~5 GB usable RAM of the conservative floor, on CPU,
  under a license with no usage cap, royalty, or remote-revocation risk —
  consistent with the sovereign, AGPL posture (ADR 0005, 0009).
- Quality is capped by what a 4B model can do on dense legal Spanish. This is a
  deliberate trade for reach and portability. Users on capable hardware can point
  the config at a larger Apache-2.0 model or enable GPU offload.
- Slow CPU inference on N-series machines is accepted because CPU is the baseline
  (ADR 0012) and the GUI surfaces progress and a cancel control (FR-10). It also
  reinforces the need for fragment-based processing of long documents.
- The chat-template mapping ties the prompt layer to instruct-tuned models; a base
  (non-instruct) model would need a different path. Acceptable, since the design
  targets instruct models throughout.
- Naming concrete models dates this decision. If a better-fitting Apache-2.0 model
  appears, a new ADR supersedes this one rather than editing it.

## Alternatives considered

- **Qwen3-1.7B as the default** (0.6B fallback) — faster on the weakest CPUs, but
  leaves quality on the table on machines that can run 4B; kept as the fallback
  tier instead.
- **Salamandra-2b-instruct as the default** — Spanish-native and philosophically
  aligned (a public European model), but unaligned (no RLHF) and weaker at
  reasoning than Qwen3-4B; kept as a pilot benchmark, not the default.
- **Qwen2.5-3B / Llama 3.2 3B / Gemma 2-4B** — all strong at Spanish and small
  enough, but each carries a non-permissive or non-OSI license (Qwen Research,
  Meta, Google) that conflicts with a sovereign public tool; rejected on
  licensing.
- **A 7B model such as Mistral 7B (Apache 2.0)** — better quality, but about
  4.1 GB plus KV cache overflows the 8 GB CPU floor; rejected for the default,
  viable only as a config choice on higher-RAM machines.
- **Raw completion instead of the chat template** — more token-level control, but
  re-implements each model's chat format and risks drift; rejected.

This ADR is a follow-on to **ADR 0003** (it names the concrete model that 0003
left to configuration) and applies **ADR 0012** (CPU baseline, optional GPU). It
does not supersede either; both stand unchanged.
