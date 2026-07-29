# 0021 — The GUI reads and writes `leyllana.toml`

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Felipe Carvajal Brown

## Context

The PRD's first success criterion is that a non-technical user can load a real
*boletín* and get an explanation **without touching a config file**. Everything
that makes leyllana work is currently in one: which engine runs, where the
`llama-server` binary is, which GGUF to load, which CLI preset to drive. A
window that can display those but not change them does not meet the criterion;
it just moves the config file one step away.

So the Ajustes dialog has to save. The question is where.

`config.load()` reads `leyllana.toml` with `tomllib`, which is read-only by
design — the standard library ships a TOML parser and no writer. Qt offers
`QSettings`, which would write to the Windows registry or an ini file under
`AppData` with no new code at all.

## Decision

**The GUI reads and writes the same `leyllana.toml` the CLI already loads.**

`config.save(config, path)` emits the fields the dataclasses declare —
`[engine]`, `[engine.models.default]`, `[engine.models.fallback]`,
`[engine.cli]` and a new `[gui]` — as a small hand-written emitter, since
`tomllib` cannot write. `resolve_path()` is split out of `load()` so the window
can tell the user which file it is about to edit instead of leaving them to
guess.

Three properties are deliberate:

- **The write is atomic**: a temporary file in the same directory, then
  `os.replace`. A failure halfway through leaves the previous configuration
  intact rather than a truncated file that no longer loads. Config is the one
  file whose corruption stops the whole application from starting.
- **A field that is `None` is omitted, not written as an empty string.** `None`
  means "not configured" and `""` means "configured with nothing"; the second
  produces a provider error whose message makes no sense. This is the same rule
  `SourceInfo` already follows for source metadata.
- **A new `[gui]` table** carries `theme` and `font_size`, so the visual
  accessibility settings live with everything else rather than in a second
  place.

## Consequences

- One source of truth. What Ajustes shows, what the window uses, and what
  `leyllana --url ...` uses in the same directory are the same values. There is
  no state in which the window and the terminal disagree about which provider is
  configured.
- The config file stays inspectable and hand-editable, which matters for a
  local-first tool: the user can see exactly what it is set up to do, and can
  fix it in a text editor if the window will not start.
- **Saving from the application rewrites the file and drops hand-written
  comments.** This is the real cost, it is not avoidable with a small emitter,
  and it is stated in the header the writer emits, in `leyllana.example.toml`,
  and here. `leyllana.example.toml` remains the commented reference.
- The emitter only knows the fields the dataclasses declare. A key someone adds
  by hand for a future feature survives being read (unknown keys are ignored)
  but not being saved over. For the current schema that is a complete round
  trip, verified by test.
- A hand-written TOML emitter is code we now own. It is bounded to strings,
  numbers and string lists, escapes backslashes and quotes so Windows paths
  survive, and is covered by a round-trip test.
- Changing the engine settings invalidates the warm provider of ADR 0019, so the
  next run reloads the model. Changing only the appearance does not, because
  unloading a model to grow the type size would be absurd.

## Alternatives considered

- **`QSettings` in the registry or `AppData`.** Zero writer code and idiomatic
  Qt. Rejected because it creates a second source of truth: the window would
  say one provider and `leyllana.toml` another, and neither would be wrong. For
  a tool whose posture is that the user can see and control what it does, hiding
  its configuration in the registry is the wrong direction.
- **A read-only settings view**, with edits made by hand in the file. Least code
  and it keeps comments, and it fails the PRD success criterion outright.
- **Writing both**, `QSettings` for GUI preferences and `leyllana.toml` for the
  engine. Splits the problem in half rather than solving it, and puts the
  boundary somewhere the user has no reason to expect.
- **Adding a TOML-writing dependency** (`tomlkit`), which would preserve
  comments and formatting on round trip. That is a genuine advantage, and it
  buys a runtime dependency for the base package to solve a problem the example
  file already covers. Worth revisiting if the config grows enough that losing
  comments actually hurts.

This builds on ADR 0003 (config-driven provider selection) and ADR 0019 (the
session that owns the provider). It supersedes none.
