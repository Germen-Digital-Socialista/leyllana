# Validation protocol — BM25 + reranker article selection

Status: **Approved 2026-07-31.** Document set and N revised from the draft after
fetching candidates; see "Documents" and "N" below for what changed and why.

Written before any run, deliberately. The point of fixing N and the faithfulness
criterion in advance is that neither can drift toward whatever the model happens to
produce. A criterion decided after reading the output is not a criterion.

## What this measures

The mechanism implemented on 2026-07-30 and first validated on 2026-07-31: BM25
shortlist plus `Qwen3-Reranker-0.6B-Q8_0` cross-encoder pre-selecting key articles,
wired into `explain()` for `nivel publico` on the local provider only.

The 2026-07-31 result (5/5 faithful on Ley 21.663) is one document and one condense
pass. This protocol exists to turn that into something quotable.

## Configuration, fixed for every run

A dedicated config, not `leyllana.toml`. The active `leyllana.toml` has **no**
`[engine.models.reranker]` section, and `_reranker_for()` returns `None` without a
path (`engine/__init__.py:119`) — `select_key_articles` then degrades to BM25-only
without raising. Running the protocol against the default config would silently
measure the wrong mechanism.

```toml
# mediciones/reranker-validacion.toml
[engine]
provider = "local"
server_path = "C:/Projects/leyllana/backend/bin/llama-server.exe"
gpu = "auto"
temperature = 0.2
max_tokens = 1024
threads = 0

[engine.models.default]
path = "C:/Projects/leyllana/backend/models/Qwen3-1.7B-Q4_K_M.gguf"
ctx = 4096

[engine.models.reranker]
path = "C:/Projects/leyllana/backend/models/Qwen3-Reranker-0.6B-Q8_0.gguf"
ctx = 2048
```

Model is Qwen3-1.7B, matching the 2026-07-31 validation so the numbers compose
rather than sit side by side. Qwen3-4B is a separate question, out of scope here.

Every run: `nivel publico`, fresh process, fresh condense. No reuse of a condense
pass between runs — that is the flaw that made the 5/5 confirm the bug fix rather
than the pipeline.

## Documents

Three shapes, because Ley 21.663 is one profile and repeating it only measures that
profile harder. Target shapes:

1. **Long law, many articles** — the Ley 21.663 profile, a different law. Stresses
   selection: many plausible candidates competing for a small budget.
2. **Short boletín** — few articles, little to choose between. Stresses the opposite
   failure: does the mechanism pad, or invent importance that is not there?
3. **Structural oddity** — a document with lists, tables, or long enumerated
   subsections. Most likely to break `ArticleChunk` segmentation, which is upstream
   of everything the reranker does.

**Fetched and verified 2026-07-31.** Every id below was confirmed to resolve to real
text through `tools/fetch_norm.py`; none was written from memory.

| Document | idNorma | chars | tokens | articles | lettered lists | profile |
|---|---|---|---|---|---|---|
| Ley 21.663 (control) | — (already pinned) | 99,468 | 28,419 | 55 | 107 | long, dense, answer known |
| Ley 21.719 datos personales | 1209272 | 75,576 | 21,593 | 35 | 105 | long, list-heavy |
| Ley 19.628 vida privada | 141599 | 29,656 | 8,473 | 28 | 26 | short, simple |

**Stated coverage gap, not silently dropped.** Shape 3 of the draft (tables, heavy
structural oddity) is not represented. leychile's XML API returns `<Texto>` elements
and none of the three documents contains a single table row, so the shape is not
reachable through this source. A short `boletín` is likewise absent: that requires
the Cámara/Senado route, which this project has never exercised. Any conclusion from
these 9 runs is therefore about *law-shaped documents from leychile*, and must not be
stated more broadly than that.

**Correction to an earlier reading of `mediciones/`:** `b9929` and `b10184` are
llama.cpp build numbers, not boletín numbers. Both of those runs used
`ley21663.txt`. Before today, leyllana had been validated on exactly one document.

**Separate finding, out of scope here but recorded so it is not lost:** `idNorma`
1138479 (Ley 21.180) and 1224631 (Ley 21.821) both fail in `_fetch_bcn_norma` with
"BCN devolvio HTML en vez del XML", consistently and reproducibly, while 1209272 and
141599 succeed. Real norms that the input layer cannot currently read.

## N

**3 independent full-pipeline runs per document, 3 documents = 9 runs.** Fixed now.
Not "until it looks good", not "until one fails".

Revised down from the draft's 12 after the 4th document shape turned out to be
unreachable through leychile (see Documents). 9 real runs on 3 genuinely different
profiles beats 12 runs where the 4th document is a near-duplicate of one already in
the set.

At ~4.1 min per run this is roughly 37 minutes of compute, mostly unattended. The
scarce resource is the read-through, not the machine.

If a document fails to process for an engineering reason (crash, parse failure,
server rejection), that is recorded and diagnosed but does **not** count toward its
3 runs — the same distinction that kept the label-duplication bug from being
misread as fabrication.

## Criterion, fixed before the first run

Each run is classified as exactly one of three outcomes.

**FAITHFUL** — all four of these hold:
- Every article number cited exists in the source document.
- Each cited article's description matches what that article actually says.
- No legal term, figure, percentage, date, deadline, or entity name appears in the
  output that is not in the source. Verified word-for-word, the way "mérito
  ejecutivo" and the 25% pronto-pago discount were checked on 2026-07-31.
- The "En una frase" section asserts nothing beyond what the cited articles support.

**FABRICATED** — any one of the above fails. A single invented article number,
figure, or legal term is enough. There is no partial credit and no "close enough":
the product promise is that the tool does not invent legal content.

**PARSE FAIL** — the output does not contain all four expected sections. Recorded
separately, diagnosed, and not counted as fabrication. This category exists because
2 of 3 runs failed this way on 2026-07-31 for a prompt-construction reason that had
nothing to do with the model inventing anything.

Selecting a *defensible but different* set of articles than a human would is **not**
fabrication. Article importance is a judgement call; inventing content is not. This
distinction is written down now so it is not relitigated while reading run 7.

## What gets recorded

Per run, into `mediciones/` (gitignored, local only, per this repo's
data-sovereignty convention): the output Markdown, the `measure_run.py` timing JSON,
and the `llama-server` log. Document text is never saved beyond the pinned fetch.

Plus one summary table across all runs: document, run number, outcome, wall-clock,
articles selected, and for any FABRICATED run the exact invented content quoted next
to what the source actually says.

## What this can and cannot conclude

12 runs can support a statement like "no fabrication observed in 12 independent runs
across 4 documents". It cannot support a percentage with a meaningful confidence
interval, and the write-up will not imply one. If a fabrication does appear, the run
count stops being the story and the specific failure becomes the story.

Only after this exists does ADR 0025 (the Gemma swap) become answerable, per the
Next-real-step note in `ROADMAP.md`.
