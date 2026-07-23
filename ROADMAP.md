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
**Status: Done**

The `explain(text, nivel)` pipeline works end to end with the default local
engine, no GUI, provable from the CLI. Validated on a real BCN law (fetch ->
source-id -> local Qwen3 -> four sections), both single-pass and chunked.

- `input` layer: file (`.txt`/`.pdf` via PyMuPDF), paste/stdin, URL fetch
  (BCN/leychile XML, Senado/Camara HTML, PDF-over-URL), plus document validation
  and a Tesseract OCR fallback for scanned / empty / protected PDFs (FR-1.1,
  ADR 0011).
- `prompt` layer: Spanish structured prompt, `nivel` switch, anti-invention
  guardrail, scoped verbatim-citation of identifiers so every named article,
  date, or figure can be spot-checked against the source (FR-6.1, ADR 0014),
  disclaimer footer.
- `engine` layer: local provider driving the `llama-server` binary as a subprocess
  (ADR 0016), producing the four structured sections with Qwen3-4B (default) /
  Qwen3-1.7B (low-RAM), on a CPU baseline with optional GPU (ADR 0012, 0015).
- Long documents that exceed the model context are processed with a structure-
  aware map-reduce (extract grounded key points per fragment, then synthesize),
  keeping faithfulness front and center (ADR 0017).
- Output carries source identification (title, norm type, issuing body, date,
  URL, consultation date) when extractable, never invented (FR-7.1); captured in
  the same fetch that reads the text.
- **Deferred follow-ups (minor, not blockers):** RAM-based auto-switch between the
  default and low-RAM model; a richer GPU auto-detect than the current
  `nvidia-smi` probe; a persistent provider for the Phase 3 GUI; and measuring the
  map-reduce completeness on the 4B default (only the 1.7B was measured).
- Shaped by: ADR 0003, 0005, 0006, 0007, 0008, 0011, 0012, 0014, 0015, 0016, 0017.

## Phase 2 — Cloud providers and terminal
**Status: Not Started**

Make the engine swappable and add the side terminal.

- Provider abstraction: Claude / OpenAI-Codex / Gemini via API key.
- Explicit consent gate before any content leaves the machine for a cloud
  provider (FR-5.1, ADR 0013).
- Web-subscription path: driving provider CLIs from the embedded terminal.
- `pywinpty` terminal panel (Windows first).
- Shaped by: ADR 0003, 0004, 0013.

## Phase 3 — GUI
**Status: Not Started**

The PySide6 desktop app: source panel, result panel, embedded terminal, export.

- Load source, pick `nivel`, run, render the four sections, export to Markdown.
- Processing status while working: progress / stage indicator, elapsed time,
  percentage or fragment count when possible, and a cancel control (FR-10).
- Visual accessibility: light / dark themes, resizable type, adequate contrast.
- Show the source identification block in the result panel when available
  (FR-7.1, display side).
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
- RapidOCR cross-checking of the Tesseract output, and any vision-LLM OCR
  opt-in, beyond the Tesseract-only v1 path (ADR 0011).
- Full clickable span-linking of each cited mention to its exact source
  fragment, beyond the verbatim-citation traceability of v1 (ADR 0014).
