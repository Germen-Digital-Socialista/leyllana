# 0004 — Cloud providers via web-subscription CLIs in an embedded terminal

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

Many users have a chat subscription (ChatGPT, Claude, Gemini) but no metered API
budget. The provider CLIs (Claude Code, Codex CLI, Gemini CLI) authenticate
against those web subscriptions rather than a pay-per-token API key. leyllana
should let those users benefit from cloud models without buying API credits, and
without forcing the app to reimplement each provider's auth.

## Decision

Support two cloud paths, both opt-in on top of the local default (ADR 0003):

1. **API key** — the user pastes an Anthropic / OpenAI / Google key in settings;
   the engine calls that provider's API directly.
2. **Web-subscription via CLI** — the user drives the provider's own CLI (Claude
   Code, Codex, Gemini) from an **embedded terminal panel** that runs beside the
   main UI. This reuses the provider's existing subscription auth; leyllana does
   not store or handle those credentials.

The terminal panel is a first-class part of the GUI (see ADR 0002), backed by
`pywinpty` on Windows.

## Consequences

- Users with only a chat subscription can still use a cloud model.
- leyllana avoids storing OAuth/session credentials for the CLI path — the CLI
  owns its own auth.
- The embedded terminal is a hard requirement on the GUI stack, which is why
  Streamlit/Gradio were rejected (ADR 0002).
- Cross-platform terminal support beyond `pywinpty` (Linux/macOS) is deferred.

## Alternatives considered

- **API keys only** — simpler, but excludes subscription-only users.
- **Local + Claude API only for v1** — smallest surface, but drops the
  multi-provider and web-subscription goals the org asked for.
- **A "copy-prompt to web chat" mode** — no terminal, user pastes manually;
  clunkier and less integrated than running the CLIs in-app.
