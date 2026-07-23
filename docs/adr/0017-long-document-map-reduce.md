# 0017 — Long-document handling: structure-aware map-reduce with grounded extraction

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** Felipe Carvajal Brown

## Context

The engine sends the whole document plus the prompt to the local model in a single
pass. Real Chilean laws routinely exceed the model's context window: validated
empirically, Ley 19.880 is ~64k characters (~15k tokens), about 3.6x the 4096-token
CPU-floor context (ADR 0015). Feeding an over-length text either errors or silently
drops the tail, and neither is acceptable for a tool whose promise is a faithful
whole-document explanation.

We need a defined way to process documents longer than the context window while
holding the anti-invention guarantee (ADR 0008) and verbatim-citation traceability
(ADR 0014). The hard tension is that multi-pass summarization is exactly where a
model drifts from the source or invents, so any long-document strategy has to be
faithfulness-first, not merely length-handling.

## Decision

When a document exceeds the model's usable context, the engine processes it with a
**structure-aware map-reduce**:

1. **Fit check.** Estimate the token length. If the text fits the usable context
   (context minus the output and system-prompt budget), run the existing single
   pass unchanged.
2. **Map — structure-aware chunking.** Split the text at natural Chilean-law
   boundaries (`Artículo`, `Título`, `Capítulo`, `Párrafo` markers), grouping whole
   articles into chunks that fit the context. Fall back to fixed-size splits with
   overlap when a single section is larger than a chunk or the text is
   unstructured.
3. **Map — grounded extraction.** For each chunk, the model extracts faithful key
   points with their verbatim article references, under the anti-invention
   guardrail (ADR 0008). It summarizes only what the chunk actually says.
4. **Reduce — synthesis.** The pooled key points become the input to the normal
   four-section prompt (reusing `build()`), so the final output honors the same
   output contract (ADR 0007) and guardrail. If the pooled points still exceed the
   context, the reduce repeats hierarchically.

The multi-pass cost is accepted: it is N+1 model passes and therefore slow on the
CPU baseline, which reinforces the progress and cancel controls (FR-10) and the
fragment-based processing already anticipated in ADR 0015.

## Consequences

- Long laws become explainable within a small context window instead of erroring or
  being silently truncated.
- Faithfulness is defended at every step: extraction is grounded and guardrailed,
  synthesis works from those grounded points under the same guardrail, and citations
  are carried as verbatim article references (ADR 0008, 0014). Multi-pass
  summarization still carries more drift risk than a single pass; that risk is
  disclosed, and it is the reason extraction is grounded rather than free-form.
- Slower: a long document is N+1 passes on an already-slow CPU path, which the pilot
  must account for (FR-10 progress and cancel).
- Short documents are unaffected: the fit check keeps the single-pass path for
  anything that fits the context.
- Structure-aware splitting adds Chilean-law-specific parsing (article and title
  markers); the size-with-overlap fallback keeps it robust on unstructured or oddly
  formatted text.

## Alternatives considered

- **Sequential refine** (carry a running explanation, update per chunk) — coherent
  single output, but N sequential passes with no parallelism and later chunks
  biasing or overwriting earlier content; harder to keep faithful across the running
  rewrite.
- **Truncate + warn** (explain only what fits, state the rest was not read) —
  simplest and fastest with no summary-of-summaries risk, but incomplete for long
  laws, which are precisely the documents the tool exists to make readable; rejected
  as the default, kept as an honest message when extraction itself fails.
- **Fixed-size chunking only** — simple and text-agnostic, but cuts mid-article and
  separates a rule from its context, hurting faithfulness and citation; kept only as
  the fallback inside structure-aware splitting.
- **Retrieval / embeddings over chunks** — powerful for Q&A against a law, but there
  is no query in the explain task, and it pulls in the embedding stack deferred from
  v1 (ROADMAP); out of scope.

This builds on ADR 0007 (output contract), 0008 (anti-invention), 0014
(traceability), and 0015 (fragment processing on the CPU floor). It supersedes none.
