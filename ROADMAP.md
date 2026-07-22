# ROADMAP — leyllana

Phase-based, not calendar-dated. Status values: **Not Started** / **In Progress**
/ **Blocked** / **Done**. Each phase links the ADRs that shaped it.

---

## Phase 0 — Foundation and decisions
**Status: Done**

Repository, license, brand, and the decision record that fixes the architecture
before any code.

- Repo created (public) under `Germen-Digital-Socialista`, AGPL-3.0.
- PRD, ROADMAP, and the initial ADR set written.
- README, logo, `.gitignore`, `CLAUDE.md`.
- Shaped by: ADR 0001, 0002, 0003, 0004, 0005, 0009, 0010.

## Phase 1 — Core engine (headless)
**Status: Not Started**

The `explain(text, nivel)` pipeline working end to end with the default local
engine, no GUI. Provable from a test harness / CLI entry point.

- `input` layer: file (`.txt`/`.pdf`), paste/stdin, URL fetch (BCN/Senado).
- `prompt` layer: Spanish structured prompt, `nivel` switch, anti-invention
  guardrail, disclaimer footer.
- `engine` layer: local `llama.cpp` provider producing the four structured
  sections.
- Shaped by: ADR 0003, 0005, 0006, 0007, 0008.

## Phase 2 — Cloud providers and terminal
**Status: Not Started**

Make the engine swappable and add the side terminal.

- Provider abstraction: Claude / OpenAI-Codex / Gemini via API key.
- Web-subscription path: driving provider CLIs from the embedded terminal.
- `pywinpty` terminal panel (Windows first).
- Shaped by: ADR 0003, 0004.

## Phase 3 — GUI
**Status: Not Started**

The PySide6 desktop app: source panel, result panel, embedded terminal, export.

- Load source, pick `nivel`, run, render the four sections, export to Markdown.
- Settings: engine/provider selection, API keys (stored locally only).
- Shaped by: ADR 0002, 0004, 0007.

## Phase 4 — Packaging and pilot
**Status: Not Started**

Ship something a non-technical user can install and run, then test it on real
*boletines* with real readers.

- Windows installer bundling the app + default model.
- Pilot with a small set of real laws/bills and target readers.
- Faithfulness spot-check pass (output invents nothing vs. source).

---

## Deliberately deferred (candidate future GDS tools, not leyllana v1)

- Multi-law comparison / redline diffing.
- Q&A over a law with cited articles.
- Legislative tracking / scanning for new AI-related *boletines*.
- Cross-platform terminal backend (Linux/macOS) beyond `pywinpty`.
