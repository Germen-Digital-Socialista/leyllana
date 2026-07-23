# 0011 — Input validation and OCR fallback

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

ADR 0006 fixed three input paths and specified `.pdf` extraction via PyMuPDF.
That covers documents with a real text layer, but Chilean legal and legislative
PDFs are frequently scans or image-only exports with no extractable text, and
some are empty, password-protected, or yield only partial text. Feeding empty or
garbled text to the engine produces confident-looking output with no basis in a
readable source — exactly the failure mode ADR 0008 exists to prevent. We need a
defined behavior for "the input did not yield usable text" *before* the text
ever reaches the prompt and engine layers.

A vision-language model could read scanned pages directly, but running one on the
default path would break the local-first, CPU-first posture (ADR 0005) and
reintroduce hallucination risk at the extraction step. The sibling project
`chilecompracl` already solved the same problem with a Tesseract-based pipeline
and an explicit no-hallucination posture, which we reuse here.

## Decision

Add a validation-and-OCR stage inside the `input` layer, between raw extraction
and returning text. Its behavior:

1. **Validate first.** After PyMuPDF extraction, detect empty, password-
   protected, or image-only PDFs and incomplete extraction by measuring per-page
   text density, and warn the user before any explanation is produced.
2. **OCR only as a fallback, only when needed.** When a PDF has no usable text
   layer (near-empty text density per page), route it to OCR. OCR never runs on a
   document that already yields a usable text layer.
3. **Tesseract-primary, vision-free default.** OCR uses Tesseract via
   `pytesseract` with Spanish (`-l spa`), rasterizing pages with pdf2image /
   Poppler at a fixed DPI (300, matching `chilecompracl`). No vision model runs
   on the default path.
4. **Fail loudly, not silently.** Missing system binaries (Tesseract / Poppler),
   a failed extraction, or a low-confidence result are surfaced to the user as a
   flagged or low-confidence extraction, never passed silently to the engine.
5. **Faithfulness caveat.** OCR can mis-read (for example "artículo 12" read as
   "artículo 72") and introduce transcription errors. The explanation is only as
   faithful as the extracted text, and that caveat is shown to the user,
   consistent with ADR 0008.

The OCR system binaries (Tesseract + Poppler) are an optional install; the Python
packages (`pytesseract`, `pdf2image`, `pillow`) live behind an optional `ocr`
extra so the base install stays lean.

## Consequences

- Scanned Chilean laws and *boletines* become usable without a manual OCR step,
  while clean documents are left untouched (no needless OCR pass).
- The anti-invention guarantee (ADR 0008) now also covers the extraction step:
  empty or garbage text is flagged instead of being silently explained.
- OCR adds a heavy native dependency. It is optional and only on the scanned-PDF
  path; the default text path gains no new dependency.
- OCR accuracy is a real, disclosed limitation; a low-confidence extraction is a
  visible state, not a hidden risk.
- RapidOCR cross-checking and any vision-LLM opt-in are deliberately out of scope
  for v1 (see ROADMAP).

## Alternatives considered

- **Vision-LLM OCR on the default path** — highest accuracy on messy scans, but
  breaks local-first / CPU-first and reintroduces hallucination at extraction;
  rejected for v1, kept as a candidate opt-in later.
- **No OCR, reject scanned PDFs** — simplest, but leaves a large share of real
  Chilean legal PDFs unusable.
- **Always-on OCR** — one uniform code path, but wastes time and can degrade
  clean documents that already have a perfect text layer.

This ADR **extends ADR 0006** (input handling); it does not supersede it. The
three input paths and PyMuPDF extraction still stand, with validation and OCR
added as a fallback stage.
