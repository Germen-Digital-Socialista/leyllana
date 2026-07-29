# 0022 — The terminal panel mirrors what the engine sends to the cloud

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0004 described the embedded terminal as the mechanism for the cloud path:
the user would drive Claude Code or Codex in a panel beside the app. ADR 0018
then made the cloud path a **headless subprocess** instead, because driving an
interactive CLI and parsing its TTY output for the explanation text is not
reliable enough for a tool that must not garble an article number.

That was the right call, and it left the terminal panel orphaned. Phase 3
shipped it as a bare shell: useful for `claude` login or checking quota, and
connected to nothing. Pressing Explicar with `provider = "cli"` runs
`claude -p --safe-mode --tools "" --output-format text --system-prompt-file ...`
in a temporary directory with the prompt on stdin, and the user sees none of it.

For a project whose central claim is that nothing leaves your machine without
you knowing, "we send your document somewhere and you cannot see it happen" is
the wrong shape. The consent dialog of ADR 0013 asks permission but shows
nothing; afterwards the user has only our word for what was sent.

## Decision

**The terminal panel becomes the window onto what actually left the machine.**

When a cloud run happens, the panel prints, into the same view as the live
shell:

- the **exact argv** the engine invoked, including the resolved path of the
  temporary system-prompt file;
- the **size of the payload** written to stdin, in characters, and which
  fragment of how many it belongs to;
- the **response** the CLI returned;
- the **exit code and elapsed time**.

It stays a live shell the rest of the time. The transcript is interleaved
notices, not a mode.

The document text itself is **not** printed. The size is. A 99.468-character law
dumped into a scrolling panel is noise, not transparency, and the user already
has the document open in the left panel.

The mechanism is a `trace` callable threaded through `get_provider(config,
trace=...)` and held by the provider. `explain()` does not change: the session
already owns provider construction (ADR 0019), so it is the session that
supplies the sink. The engine emits structured `TraceEvent` values and does no
formatting, so the panel decides how they look.

**The response is printed when it arrives, not as it streams.** `CliProvider`
uses `Popen.communicate`, which returns stdout when the process exits, and that
is precisely what makes its cancellation polling free of the classic
write-stdin-while-reading-stdout deadlock. Incremental stdout would mean closing
stdin then reading in a loop with stderr drained on a side thread. That is
achievable and it is not worth trading a deadlock-free path for a nicer
animation.

Scope is the cloud path only. The local provider talks to `127.0.0.1` and its
traffic never leaves the machine, so there is nothing to disclose; tracing it
would be a debug feature wearing a transparency costume.

## Consequences

- The sovereignty claim becomes checkable instead of asserted. After a cloud
  run the user can read the command that ran and how much text went with it.
- The orphaned panel of ADR 0004 gets a purpose that fits the architecture ADR
  0018 chose, without reopening the decision to drive the CLI interactively.
- The panel is no longer hidden behind the **Ver** menu. It gets a visible
  toggle in the status bar, because a transparency feature nobody can find is
  not one.
- The trace is display-only and is never persisted. Nothing about the run is
  written to disk, which keeps the local-first posture intact and means the
  transcript is gone when the window closes. An export-the-transcript feature
  would be its own decision.
- `get_provider` grows an optional parameter. Every existing caller omits it and
  gets exactly today's behaviour.
- The argv is printed verbatim, which includes whatever the user put in
  `engine.cli.command`. If someone configures a command containing a secret,
  that secret appears in the panel. The presets do not, and the CLI path exists
  precisely so that leyllana never handles credentials (ADR 0004), so the
  configuration where this bites is one we do not ship and do not recommend.
- On a 13-fragment map-reduce the panel gets 13 invocation blocks. That is
  accurate, and it is a lot of output; the view already caps its scrollback.

## Alternatives considered

- **One-way: a button that types the command into the shell without running
  it.** Cheap, keeps the paths cleanly separate, and lets the user tweak flags
  by hand. Rejected as the primary answer because it shows what *would* happen
  rather than what *did*, and the transparency problem is about actual runs.
- **Make the terminal the real cloud path**, as ADR 0004 imagined. Most
  integrated, and it means parsing an interactive TTY for the explanation text,
  which ADR 0018 rejected on reliability grounds that have not changed. Would
  have superseded part of 0018 to buy back a known problem.
- **Leave it independent and merely easier to find.** Least work, and it makes
  the panel permanently a convenience rather than part of what the tool
  promises.
- **Mirror the local provider too.** Symmetric and slightly useful for
  debugging a slow model, and it dilutes the point: the panel would fill with
  loopback traffic that was never a privacy question, making the cloud blocks
  harder to notice.

This builds on ADR 0004 (embedded terminal), 0013 (consent), 0018 (headless CLI
provider) and 0019 (the session that owns the provider). It supersedes none:
ADR 0004's terminal panel keeps the purpose it was given, and ADR 0018's
headless subprocess remains how a cloud explanation is produced.
