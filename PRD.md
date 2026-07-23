# PRD — leyllana

**Product:** leyllana
**Organization:** Germen Digital Socialista (GDS)
**Status:** Draft (pre-implementation)
**Owner:** Felipe Carvajal Brown
**Language of this document:** English. Product UI and output: Spanish.

---

## 1. Vision

Chilean law is public but not legible. Statutes and *boletines* (bills) are
written in a register that is hard to parse even for lawyers, and often opaque to
the legislators who vote on them and the citizens they bind. leyllana turns the
raw text of a law or bill into a plain-Spanish, structured explanation — a
"decodificador de leyes" — so that understanding a norm does not require a law
degree or a paid legal service.

leyllana is the first tool of Germen Digital Socialista. It is built local-first:
by default it runs entirely on the user's machine, and no data leaves that
machine unless the user explicitly opts into a cloud provider. This is both a
privacy property and a political stance — public understanding of the law should
not depend on a foreign cloud or a subscription.

## 2. Problem

- Legal and legislative text is dense, self-referential, and full of cross
  references; a single article can be unreadable without the ten it modifies.
- The people most affected by a law — workers, tenants, small operators — are the
  least equipped to read it.
- Even legislators and staffers lack time to fully digest every *boletín* they
  handle.
- Existing summarizers are cloud-only, English-first, and give no guarantee they
  are not inventing article numbers or obligations.

## 3. Goals and non-goals

### Goals (what v1 must achieve)
- Take a Chilean law or *boletín* as input and produce a clear, structured
  Spanish explanation.
- Run fully offline by default (local `llama.cpp` engine).
- Never fabricate legal content: the explanation is grounded strictly in the
  provided text.
- Be usable by a non-technical person through a desktop GUI.
- Offer two audience levels: `publico` (general public) and `tecnico`
  (legislator / staffer).

### Non-goals (explicitly out of scope for v1)
- Legal advice or interpretation of any kind (the tool is an aid, not
  *asesoría legal*).
- A hosted web service or multi-user backend.
- Multi-law comparison / diffing, full Q&A over a corpus, or legislative
  tracking — these are candidate future GDS tools, not part of leyllana v1.
- Any feature that requires data to leave the machine by default.

## 4. Users

- **General public** — wants to know, in one screen, what a law does and whether
  it affects them.
- **Legislators and staffers** — want a faithful, technical-register digest of a
  *boletín* fast, with key articles surfaced.
- **Journalists / civil society** — want a defensible plain-language reading they
  can quote from and check against the source.

## 5. Functional requirements

- **FR-1 Input, three ways.** Accept input as (a) a local file — `.txt` read
  directly, `.pdf` extracted via PyMuPDF; (b) pasted text; (c) a URL from an
  official source (BCN / leychile.cl export endpoint, Senado / Cámara *boletín*).
- **FR-1.1 Document validation and OCR fallback.** Detect empty, protected, or
  scanned files and incomplete text extraction, and warn the user before
  producing an explanation. When a PDF is scanned / image-only (no usable text
  layer), fall back to OCR — Tesseract via `pytesseract` (`-l spa`), rasterizing
  pages with pdf2image/Poppler; no vision model runs on the default path (same
  stack and no-hallucination posture as the `chilecompracl` OCR pipeline).
  **OCR runs only when necessary** — solely as a fallback when text extraction
  fails, never on documents that already yield a usable text layer. **OCR can
  fail or degrade** — scanned mis-reads (e.g. "artículo 12" read as "artículo
  72"), transcription errors, or missing system binaries (Tesseract/Poppler);
  the tool flags a failed or low-confidence extraction rather than silently
  feeding bad text to the model. Faithfulness caveat: the explanation is only as
  faithful as the extracted text. See ADR 0011.
- **FR-2 Structured output.** Produce fixed Spanish sections: **Qué hace**,
  **A quién afecta**, **Artículos clave**, **En una frase**.
- **FR-3 Audience level.** A `nivel` control with two values, `publico` and
  `tecnico`, that changes register and depth, not facts.
- **FR-4 Swappable engine.** A single `explain(text, nivel)` interface backed by
  a configurable provider (see ADR 0003). Default provider is local `llama.cpp`.
- **FR-5 Cloud opt-in.** Optional providers: Claude, OpenAI/Codex, Gemini —
  either via API key or via their web-subscription CLIs run in the app's embedded
  terminal panel (see ADR 0004).
- **FR-5.1 Consent for external services.** Before sending any content to a cloud
  provider, the app clearly states that the document will leave the machine and
  requires explicit confirmation — the local-first, sovereign posture is core to
  the project (ADR 0004, 0005).
- **FR-6 Anti-invention guardrail.** The engine prompt forbids inventing
  articles, numbers, citations, or obligations; output is grounded only in the
  input text. If the text is insufficient, the tool says so rather than guessing.
- **FR-6.1 Traceability.** Every article, figure, date, or obligation named in the
  explanation must use the wording exactly as it appears in the source (verbatim,
  enforced by the anti-invention guardrail), so a reader can spot-check each
  against the input. Full clickable span-linking of each mention to its source
  fragment is deferred (see ROADMAP).
- **FR-7 Disclaimer.** Every explanation carries a visible footer stating it is
  an aid and not legal advice.
- **FR-7.1 Source identification.** The output shows, when available, the document
  title, norm type, issuing body, date, version analyzed, URL, and consultation
  date. These are shown only when extractable and are never invented (same rule as
  FR-6).
- **FR-8 Export.** Save the explanation as Markdown.
- **FR-9 Embedded terminal.** A terminal panel beside the main UI (pywinpty on
  Windows) for driving provider CLIs alongside the app.
- **FR-10 Processing status.** During extraction and analysis, the UI shows that
  the system is still working: a progress bar or animated indicator, the current
  stage (**cargando**, **extrayendo texto**, **analizando**, **verificando**,
  **generando resultado**), and elapsed time. When technically possible, it shows
  the percentage complete or the number of fragments processed. The user can
  cancel the operation. (GUI phase — see ROADMAP Phase 3.)

## 6. Non-functional requirements

- **Local-first / sovereign:** default path makes no network calls. Cloud calls
  happen only on explicit user opt-in.
- **Faithfulness over fluency:** a correct "I can't tell from this text" beats a
  fluent fabrication.
- **Spanish throughout** for all UI and output.
- **CPU-compatible:** basic local operation requires no GPU (no GPU assumption).
  When a compatible GPU is present, it may optionally be used to improve
  performance. CPU remains the baseline, matching MuniGPT. See ADR 0012.
- **Single-language codebase** (Python) for maintainability.
- **Visual accessibility (GUI phase):** the interface supports light and dark
  modes, resizable typography, and adequate contrast for prolonged reading of
  legal documents.

## 7. Architecture (high level)

```
            ┌─────────────────────────── PySide6 desktop app ───────────────────────────┐
            │                                                                             │
  source ──▶│  input layer            engine layer            output layer   terminal    │
 (file/     │  resolve + extract  ──▶  explain(text,nivel) ──▶ structured  │  panel      │
  paste/    │  (txt/pdf/url)           swappable provider     Spanish +    │ (pywinpty:  │
  url)      │                          · local llama.cpp*      disclaimer  │  claude/    │
            │                          · claude / codex /      + export    │  codex/     │
            │                            gemini (api or CLI)               │  gemini CLI)│
            └─────────────────────────────────────────────────────────────────────────┘
                                        * default
```

Component boundaries (each independently testable):
- **input** — resolves a source to raw text: validates the document and, for
  scanned PDFs only when needed, OCRs it (ADR 0011). Knows nothing about the engine.
- **engine** — `explain(text, nivel) -> structured result`. Knows nothing about
  the GUI. Provider selected by config.
- **prompt** — builds the Spanish system+user prompt with guardrails and the
  `nivel` switch. Pure, no I/O.
- **gui** — PySide6 shell: source panel, result panel, embedded terminal.

## 8. Success criteria

- A non-technical user can load a real *boletín* and get a faithful,
  four-section Spanish explanation without touching a config file.
- With the network disabled, the default (local) path still works end to end.
- On a spot check against the source, the output invents nothing — every article
  or figure it names is present in the input.

## 9. Open questions

- Which exact light local model ships as the default (Qwen-class), and the
  low-RAM fallback, mirroring MuniGPT's config-driven selection.
- Terminal integration details on non-Windows platforms (pywinpty is
  Windows-specific; a ptyprocess-based backend would be the Linux/macOS path).
- Packaging/installer target for v1 (deferred to the roadmap).
- Bundling the OCR system binaries (Tesseract + Poppler) into the v1 installer
  for a non-technical user (Phase 4), since they are not pip dependencies.

## 10. References

- Decisions: `docs/adr/` (see the index in `docs/adr/README.md`).
- Sibling project reused for patterns: MuniGPT (local `llama.cpp`, PDF
  extraction, BCN fetch).
