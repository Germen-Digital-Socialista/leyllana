# leyllana — session handoff, 2026-07-31 (second session of the day)

Read first: the **Correccion** section at the top of `ROADMAP.md`. It supersedes the
"First real validation" section directly below it, which is still true and still
about a single document. Then
`docs/superpowers/plans/2026-07-31-reranker-validation-protocol.md` for the protocol
and `mediciones/validacion-20260731-resultados.md` for every fabrication quoted
against source (local only, `mediciones/` is gitignored).

Commits this session: `5846aed`, `a1ca5e4`, `4bf69a8` on `main`.

## Done

- Ran the 9-run validation protocol the previous handoff called for: 3 documents,
  3 independent full-pipeline runs each, fresh condense every time, criterion
  written down before the first run so it could not drift.
- **Result: 5 faithful / 4 fabricated / 0 parse failures.** The control (Ley 21.663)
  reproduced its hand-verified article set 3/3. Ley 19.628 went 2/3. Ley 21.719
  went 0/3.
- **Found the cause, and it is upstream of the reranker.** `_STRUCTURE_RE`
  (`engine/chunking.py:23`) anchors to line start under `re.MULTILINE`; BCN hard-wraps
  its text at ~55 characters. A cross-reference that wraps onto a new line matches as
  an article opening, and `chunking.py:69` takes that whole wrapped line as the chunk
  label. So `articulo 30 bis, y las que establece el articulo 30 ter,` becomes an
  addressable "article" that BM25 and the cross-encoder will happily rank and cite.
- Built `tools/audit_segmentation.py` — measures this with no model and no network.
  Validated against the three laws where ground truth was established by hand: Ley
  21.663 0.0% noise, Ley 19.628 3.6%, Ley 21.719 12.8%. That ordering reproduces the
  per-document run outcomes without being told them.
- Answered the corpus question: **BCN does publish an enumerable index.** SPARQL
  endpoint `https://datos.bcn.cl/sparql`, 359,720 norms, of which **16,064 are leyes**.
  URIs encode type, ministry, date and law number, so a stratified random sample is
  possible in principle.

## Genuinely open

1. **The regex fix is not made.** The defect is identified and evidenced but not
   repaired. The shape of the fix: require the article marker to open a paragraph
   rather than merely a line. Re-running the 9-run protocol afterward gives a
   directly comparable before/after, since the before number is now recorded.
2. **The idNorma bridge.** SPARQL enumerates leyes by number; the fetcher needs
   `idNorma`; `obtxml?opt=7&idLey=21719` returns HTML, not XML. Without a mapping
   from law number to `idNorma`, the 16,064-law sweep cannot start. This is the one
   thing blocking a population-level answer.
3. **Two real norms the input layer cannot read.** `idNorma` 1138479 (Ley 21.180) and
   1224631 (Ley 21.821) both fail in `_fetch_bcn_norma` with "BCN devolvio HTML en vez
   del XML", reproducibly, while 1209272 and 141599 succeed. User-facing: someone
   pastes a valid BCN link and gets an error. Cause unknown, roughly half of the ids
   tried today.
4. **ADR 0025 (the Gemma swap) is further from answerable, not closer.** Swapping the
   fallback model does not touch a segmentation defect.
5. Retrieval-layer (`dirigente` / `autoridad comunal`) spec review — untouched again,
   still needs Felipe's read-through before it becomes an ADR.

## Two corrections to the previous handoff

- `b9929` and `b10184` in `mediciones/` are **llama.cpp build numbers, not boletin
  numbers**. Both of those runs used `ley21663.txt`. Before today, leyllana had been
  validated on exactly one document ever.
- The three bug fixes from 2026-07-30/31 are real and hold — the control run confirms
  it. They were just not the whole problem, and one document could never have shown
  that.

## Coverage gap, stated rather than glossed

The 9 runs cover law-shaped documents from leychile only. No table-heavy document (not
reachable through leychile's XML, which returns `<Texto>` elements) and no short
`boletin` (needs the Camara/Senado route, never exercised in this project). No
conclusion from this session extends to either.

Working tree clean apart from `.claude/settings.json`, which is deliberately untracked.
