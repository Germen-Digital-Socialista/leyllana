# 0002 — GUI stack: PySide6/Qt desktop

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

leyllana needs a GUI (not only a CLI) and, per ADR 0004, an embedded terminal
panel beside the main UI to drive provider web-subscription CLIs. The candidate
stacks were: reuse MuniGPT's Electron + React + FastAPI stack; a Streamlit/Gradio
single-file web GUI; or a Python-native desktop toolkit (PySide6/Qt).

## Decision

Build the GUI with **PySide6/Qt** as a native desktop application.

The deciding factor is the embedded-terminal requirement. Streamlit and Gradio
are stateless web forms and cannot host a live interactive PTY/terminal.
PySide6 can host a real terminal panel (via `pywinpty` on Windows) next to the
explanation UI, keeps the whole app in one language (Python), and matches the
local-first, CPU-only posture of the default engine.

## Consequences

- One-language codebase (Python) across engine, input, and GUI.
- The embedded terminal (ADR 0004) is feasible in-process.
- More hand-written UI than a web toolkit; slower to a polished look than
  Streamlit, but it is the only option of the two finalists that meets the spec.
- Electron was excluded to avoid a JS/Node build chain and a heavier stack for
  the org's first repo.

## Alternatives considered

- **Reuse MuniGPT's Electron + React + FastAPI** — proven and installable, but a
  heavier multi-language stack; set aside for the first GDS repo.
- **Streamlit / Gradio** — fastest to a clickable demo, but cannot host the
  required embedded interactive terminal.
