# 0020 — Streaming local generation, so cancelling stops the work

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0019 gives `explain()` a cancellation token and checks it between provider
calls. That bounds a cancel by the length of one provider call, which raises the
obvious question: how long is one call?

On the local path it can be very long. `chat_completion()` posted
`stream: false` to `llama-server` and blocked inside a single `urlopen` with a
600-second timeout. On a single-pass run there is exactly one such call, so
cancellation between calls means no cancellation at all. On the 13-fragment
map-reduce of Ley 21.663 it means waiting out one fragment, minutes on CPU.

A Cancelar button that visibly does nothing for minutes is worse than no button:
it teaches the user that the interface is lying to them, in a tool whose whole
argument is that it can be trusted.

The cloud path has the same shape for a different reason. `CliProvider` ran
`subprocess.run` with a ten-minute timeout, which cannot be interrupted either.

## Decision

**Read the local model's response as a stream and check for cancellation between
tokens.**

`chat_completion()` now requests `stream: true` and reads the server-sent-event
frames one at a time, accumulating the content deltas. Between frames it checks
the cancel token; when set, it leaves the response context, which closes the
connection, and `llama-server` stops generating once it loses the client. An
optional `on_token` hook exposes each chunk as it arrives.

Two behaviours are fixed alongside it:

- A malformed frame is **skipped**, not fatal. The cost of a broken frame is one
  token; the cost of raising would be the whole explanation.
- An empty response is a visible `ProviderError`. Previously an empty string
  flowed downstream and surfaced as "the model's answer is missing sections,"
  which points the user at the wrong problem.

`CliProvider` gets the same property by the means available to a subprocess: it
drives `Popen` and polls `communicate` on a one-second timeout, so cancelling
kills the CLI instead of waiting out the configured timeout, and a CLI that
exceeds its timeout is killed rather than left running.

**The limit is stated rather than hidden.** Cancellation is not instant during
prompt processing, before the first token arrives, because nothing has arrived
to read. That window is real, it is recorded in the function's docstring, and it
is the honest boundary of what the button promises.

## Consequences

- Cancelling a local run stops it within one token, in practice milliseconds,
  instead of up to ten minutes.
- Cancelling a cloud run kills the CLI within about a second.
- `on_token` opens the way to a live token readout, and to showing the
  explanation as it is written, which is a possible later improvement and is not
  built here.
- The local path now depends on `llama-server` speaking SSE correctly. It is the
  same OpenAI-compatible endpoint already in use (ADR 0016) and needs no new
  dependency: the frames are parsed with the standard library.
- More parsing code than a single `json.loads` of a whole response, and it can
  fail in more ways. That is covered by tests over frames, over a `[DONE]`
  sentinel, over a malformed frame, and over cancellation mid-stream.
- Three tests in `test_engine_local.py` patched the non-streaming helper and no
  longer described anything real; their subject moved to `test_streaming.py`,
  and what replaced them covers the health check, which is what that helper is
  still for.
- Closing the connection mid-generation discards the partial answer. That is
  deliberate: a half-generated explanation of a law is exactly the artefact this
  tool must not hand anyone.

## Alternatives considered

- **Cooperative cancellation between fragments only**, leaving the request
  non-streaming. No change to the server module, and on a 13-fragment run the
  wait is bounded by one fragment. Rejected because on a single-pass run it
  bounds nothing, and that is the common case for the short *boletines* that
  make up most of the pilot corpus.
- **Cancel by killing the `llama-server` subprocess.** Immediate and simple, and
  it throws away the loaded model, so the next run pays the full cold start,
  minutes on CPU. That directly undoes the warm provider of ADR 0019.
- **Polling the socket with a short read timeout** so the loop can check the
  token even during prompt processing. It would close the one remaining window,
  and a timeout mid-read can leave the buffered reader in an inconsistent state
  and lose data. Not worth risking a corrupted response to shave seconds off a
  cancel.
- **Closing the response object from the cancelling thread** to interrupt a
  blocked read. Attractive in principle; whether it unblocks depends on details
  of how `http.client` holds the socket that I did not want to rely on without
  verifying, so it was not adopted on a guess.

This builds on ADR 0016 (managed `llama-server`), 0018 (CLI provider) and 0019
(cancellation seam). It supersedes none.
