# 0006 — Input handling: file, paste, and URL

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

Laws and *boletines* reach users in several forms: downloaded PDFs, copied text,
or a link to an official source. Restricting input to one form would force users
into manual conversion steps.

## Decision

Support three input paths from v1, resolved by the `input` layer into raw text:

1. **Local file** — `.txt` read directly; `.pdf` extracted with PyMuPDF
   (`fitz`), the same extraction MuniGPT uses.
2. **Pasted text** — direct text / stdin.
3. **URL** — an official source: BCN / leychile.cl export endpoint (by
   `idNorma`) and Senado / Cámara *boletín* pages, reusing MuniGPT's
   `corpus_fetcher` fetch pattern (content-type/size sniffing, since BCN returns
   HTML error pages with HTTP 200).

The `input` layer knows nothing about the engine; it only returns text.

## Consequences

- Users are not forced to pre-convert PDFs or copy text by hand.
- URL fetching is the one network touch on the default (local) path (ADR 0005),
  and only retrieves a public source the user explicitly named.
- Scraping fragility is contained in one module and can degrade gracefully to the
  file/paste paths.

## Alternatives considered

- **File-only for v1** — simplest, but drops the "paste a link" convenience that
  makes the tool feel immediate.
- **URL-first (auto-scrape everything)** — most magical, but brittle against
  Chilean legislative sites; kept as one of three paths, not the only one.
