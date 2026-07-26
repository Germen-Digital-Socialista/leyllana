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

## Phase 2 — Cloud via a subscription CLI
**Status: Done**

The cloud path works without an API key: leyllana drives an agent CLI as a
subprocess and rides the user's existing subscription. Validated end to end on a
real BCN norm with both shipped presets, in both audience levels.

- Generic `cli` provider (ADR 0018): argv from config, document on stdin, system
  prompt by file. Any other agent CLI is a config line, not new code.
- Verified presets: `claude` (Claude Code) and `kimi`. Codex and Gemini work
  through an explicit `command` but ship no preset, because an untested preset is
  a claim we cannot make.
- Explicit consent gate before any content leaves the machine (FR-5.1,
  ADR 0013), surfaced headless as `--acepto-nube`. The run aborts before the
  first subprocess, so the map-reduce cannot leak a first fragment either.
- The chunking budget now comes from the provider's own context, so a document
  that fits in one cloud call is no longer split (ADR 0017).
- `leyllana.example.toml` documents the options.
- **Found while verifying, both silent (exit 0, plausible wrong Spanish):** a
  multi-line system prompt in argv is truncated at the first newline by a Windows
  `.cmd` shim, stripping the anti-invention guardrail; and a Python-based CLI
  mangles accented Spanish on its pipes unless UTF-8 is forced. Both are fixed and
  recorded as constraints in ADR 0018.
- **Deliberately excluded:** API-key providers (now Phase 5) and the `pywinpty`
  terminal panel (now Phase 3, with the GUI it belongs to).
- Shaped by: ADR 0003, 0004, 0013, 0017, 0018.

## Phase 3 — GUI
**Status: Not Started**

The PySide6 desktop app: source panel, result panel, embedded terminal, export.

- Load source, pick `nivel`, run, render the four sections, export to Markdown.
- Processing status while working: progress / stage indicator, elapsed time,
  percentage or fragment count when possible, and a cancel control (FR-10).
- Visual accessibility: light / dark themes, resizable type, adequate contrast.
- Show the source identification block in the result panel when available
  (FR-7.1, display side).
- Settings: engine/provider selection, and the CLI preset for the subscription
  path (ADR 0018).
- Embedded `pywinpty` terminal panel (Windows first), for driving a provider CLI
  by hand alongside the app (ADR 0004). Moved here from Phase 2: it is a Qt
  widget and had no window to live in.
- Shaped by: ADR 0002, 0004, 0007, 0018.

## Phase 4 — Packaging and pilot
**Status: Not Started**

Ship something a non-technical user can install and run, then test it on real
*boletines* with real readers.

- Windows installer bundling the app + default model.
- Pilot with a small set of real laws/bills and target readers.
- Faithfulness spot-check pass (output invents nothing vs. source).

## Phase 5 — Cloud providers by API key
**Status: Not Started**

The metered path, for users who have a key but no subscription. Deferred past the
pilot on purpose: the subscription path of Phase 2 already covers the cloud need,
so this should not hold up putting the tool in front of real readers.

- Claude / OpenAI / Gemini via a key the user pastes, stored locally only.
- Reuses the consent gate and the provider seam already built (ADR 0013, 0018);
  the names are already in the registry with a clear not-implemented error.
- Shaped by: ADR 0003, 0004, 0013.

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
