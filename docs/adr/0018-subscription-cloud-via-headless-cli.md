# 0018 — Subscription cloud providers driven as a headless CLI subprocess

- **Status:** Accepted. Complements [ADR 0004](0004-cloud-via-web-cli-terminal.md)
  and [ADR 0013](0013-consent-before-cloud-send.md); supersedes nothing.
- **Date:** 2026-07-26
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0004 allowed two opt-in cloud paths: an API key, and a web subscription used
through the provider's own CLI, typed by hand into an embedded terminal panel.

Phase 2 narrowed that. The API-key path is deferred — it costs metered tokens for
a capability an existing Claude Pro Max subscription already covers. The
subscription path is the one that matters now. But the terminal panel cannot
deliver it yet: it is a Qt widget and there is no GUI until Phase 3, and even
once it exists, driving the CLI by hand means the user pastes the document in
themselves. The app can do that.

That raised the real question: does running `claude -p` as the engine tie
leyllana to Claude? It does not. Codex, Gemini and Kimi all accept a prompt
non-interactively and all authenticate against their own subscription. The
mechanism is identical; only the argv differs, plus whether the CLI has a flag
for a system prompt.

## Decision

Add **one generic provider, `cli`**, that runs any agent CLI as a subprocess.

- The argv comes from config: a named `preset`, or an explicit `command` for any
  CLI without one. `command` wins if both are set.
- The **document goes on the CLI's stdin**, never in argv.
- The **system prompt goes in a file**, passed through the CLI's own
  system-prompt-file flag (the `{system_file}` slot in the argv template). A CLI
  with no such flag receives it prepended to stdin instead.
- **Shipped presets: `claude` and `kimi`**, each verified end to end against a
  real BCN norm. Codex and Gemini work through `command`, but ship no preset
  because they were not tested.
- leyllana **stores no credentials**. The CLI owns its own auth.
- Sending requires **explicit consent per run** (ADR 0013). In the headless CLI
  that is the `--acepto-nube` flag; without it the run aborts before the first
  subprocess starts.
- The API-key providers stay named in the registry with a clear
  not-implemented error pointing at this path.

## Consequences

- A user with only a chat subscription gets a cloud model, with no API budget and
  no key pasted into the app.
- Any other agent CLI is a config line, not new code, so the org is not relocked
  into a single vendor (ADR 0003).
- The provider declares its own context budget, so a document that fits in one
  cloud call is no longer split by the map-reduce sized for the local model
  (ADR 0017).
- The default local path is untouched: no network, no consent prompt (ADR 0005).

### Platform constraints every new preset must respect

Both of these were found by running the thing, and both fail *silently* — exit
code 0, plausible Spanish output, wrong content:

- **The system prompt must never be an argv value.** On Windows a CLI installed
  as a `.cmd` shim cuts a multi-line argument at the first newline. The model
  then runs with only the opening role line: no anti-invention guardrail, no
  citation rule, no output contract. Observed result was a confidently invented
  compliance deadline and citations to statutes absent from the source — exactly
  what ADR 0008 exists to prevent.
- **The child's pipes must be forced to UTF-8** (`PYTHONIOENCODING`). A
  Python-based CLI defaults to the Windows ANSI codepage: it crashed on the first
  `Í` of a real decree, and in the argv path returned accented words silently
  replaced.

This is why a preset is only shipped after a real end-to-end run, never from
reading a `--help` page.

## Alternatives considered

- **A Claude-only provider** — marginally simpler to read, but every additional
  CLI becomes another class and another ADR, and it relocks the flagship tool
  into one vendor.
- **Superseding ADR 0004** — rejected. Nothing in 0004 became false: the manual
  terminal panel is still wanted and still lands with the GUI in Phase 3.
- **Implementing the API-key path in this phase** — rejected. It spends metered
  tokens to duplicate what the subscription already does.
- **No ADR, treating this as an implementation detail of 0004** — rejected. The
  decision log would no longer describe how the code actually reaches a cloud
  model.
