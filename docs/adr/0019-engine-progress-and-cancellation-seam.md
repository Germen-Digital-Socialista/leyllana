# 0019 — Progress and cancellation as an optional seam in `explain()`

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Felipe Carvajal Brown

## Context

`explain(text, nivel, config, consent)` is a blocking call that returns an
`Explanation` or raises. It reports nothing while it works and cannot be
stopped. For a CLI run that is fine: the user typed a command and waits for the
output.

The Phase 3 GUI cannot live with it. FR-10 requires the interface to show the
current stage, elapsed time, the number of fragments processed when that is
knowable, and to let the user cancel. None of those are possible against a
function that offers no observation point. The numbers make it concrete: Phase 1
measured 50 minutes for a 55-article law on the 4B default, split into 13
fragments by the map-reduce of ADR 0017. Fifty minutes with no visible progress
and no way out is not a usable interface.

There is a second, related problem. `explain()` calls `get_provider(config)` on
every invocation. In a CLI process that is free, because the process ends. In a
window that stays open, it means reloading the GGUF — minutes on CPU — on every
press of the button. The ROADMAP already carried this as a Phase-1 follow-up:
"a persistent provider for the Phase 3 GUI."

The constraint is that the CLI, the tests, and the existing behaviour must not
change. The engine also must not learn about Qt: the PRD's component boundaries
put the GUI on top of the engine, never the reverse.

## Decision

Add three **optional keyword-only** parameters to `explain()`, all defaulting to
`None`, so that omitting them leaves the function behaving exactly as before:

- `progress` — a callable receiving a `Progress` value at each stage change and
  each fragment.
- `cancel` — a `CancelToken`, checked before every provider call; when set, the
  run raises `Cancelled`.
- `provider` — an already-built provider to use instead of constructing one,
  which is what lets a long-lived caller keep a model warm across runs.

A new pure module, `leyllana/engine/progress.py`, holds the vocabulary: a
`Stage` enum carrying the five names PRD FR-10 already fixes, a frozen
`Progress` record, `Cancelled`, and `CancelToken` over a `threading.Event`. It
imports nothing from Qt or from the GUI.

Two rules govern what is reported:

1. **Fragment counts are only reported when they are real.** They come from the
   map loop of ADR 0017, the one countable unit of work in a run. A single-pass
   run reports no count at all, and the interface shows an indeterminate bar
   rather than a fabricated percentage. Inventing a progress number in a tool
   whose central promise is that it invents nothing would be the wrong kind of
   convenience.
2. **Cancellation is checked between provider calls**, and the token is passed
   down to the provider so a backend that can interrupt itself does (ADR 0020).

`Provider.generate()` widens to `generate(prompt, *, cancel=None)`. A provider
that cannot stop mid-call ignores the token rather than pretending to honour it.

## Consequences

- The GUI can honour FR-10 in full: stage, fragment n of N, elapsed time, and a
  cancel control that reaches the running work.
- The CLI is untouched. `cli.py` did not change, and the Phase 1 and 2 tests
  passed unmodified except for widening the fake providers' signature.
- The engine still knows nothing about the GUI. `progress.py` is plain Python
  and its tests need no window.
- `explain()` grows three parameters. That is real surface, and the mitigation
  is that all three are keyword-only and optional, so no existing caller sees
  them and none is required to care.
- Passing `provider` moves lifetime management to the caller. The GUI now owns
  when a `llama-server` starts and stops; `LocalProvider.close()` exists for
  that. A caller that passes a provider and never closes it holds the model in
  RAM, which is the intended behaviour in a window and would be a leak in a
  daemon.
- Cancellation between provider calls is cooperative, so its granularity is one
  provider call. What that means in practice is decided in ADR 0020.

## Alternatives considered

- **No engine change; spinner and elapsed time only.** The GUI threads the whole
  call and shows an indeterminate indicator; cancel kills the provider process.
  Cheapest by far, and it leaves FR-10's stage and fragment count unmet, which
  would mean editing the requirement to fit the implementation rather than the
  other way round.
- **Rewrite `explain()` as an event generator** yielding typed events. The
  richest model, and it changes the contract every existing caller and test
  depends on, forcing `cli.py` to drive a loop it has no use for.
- **A module-level callback or observer registry.** No signature change at all,
  but global mutable state shared between runs, and no clean way for two callers
  to observe different runs.
- **Comparing config field by field to decide whether to rebuild the provider**,
  instead of an explicit `provider` parameter. Saves a reload sometimes, at the
  cost of a window that can quietly keep using a model the user believes they
  changed.

This builds on ADR 0003 (swappable engine), 0016 (managed `llama-server`) and
0017 (map-reduce), and is the precondition for ADR 0020. It supersedes none.
