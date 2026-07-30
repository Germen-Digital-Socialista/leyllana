# Retrieval layer — design spec

**Date:** 2026-07-30
**Status:** Approved by Felipe Carvajal Brown (design level). Not yet an ADR, not
yet implemented.
**Related:** ROADMAP.md ("Corpus retrieval and token cost", "Retrieval layer
scope"), ADR 0007 (output contract), ADR 0008 (anti-invention / not legal
advice), ADR 0014 (traceability), ADR 0017 (map-reduce, which already ruled
retrieval out of scope for the *explain* task itself).

## 1. Purpose

Today `nivel` has two values, `publico` and `tecnico`, which change register and
depth but not facts (ADR 0007). This spec adds two new reader figures that need
something the loaded document cannot supply on its own: whether a law obligates
or is enforced against *them specifically*.

- **`ciudadano`** — renamed from `publico`. Vocabulary change only, no behavior
  change.
- **`legislador`** — renamed from `tecnico`. Vocabulary change only, no behavior
  change.
- **`dirigente`** (new) — the leader of an organization: vecinal, sindical,
  partidario, deportivo, or an NGO. Different organization types are governed by
  different laws (Ley 19.418 for juntas de vecinos, the Código del Trabajo for
  sindicatos, Ley 18.603 for partidos, and so on), so `dirigente` carries a
  second, required field naming the organization type.
- **`autoridad comunal`** (new) — an alcalde or municipal team, asking how a law
  touches municipal competencies, who fiscalizes, or the municipal budget.

`ciudadano` and `legislador` behave exactly as `publico`/`tecnico` do today: no
retrieval, no new section, same four-section output. Retrieval and the fifth
section (section 5 below) apply only to `dirigente` and `autoridad comunal`.

## 2. Why this is a new capability, not a pipeline change

ADR 0017 already considered and rejected "retrieval / embeddings over chunks"
for the *explain* task itself, on the grounds that there is no query in that
task. That reasoning still holds for `ciudadano`/`legislador`. `dirigente` and
`autoridad comunal` introduce an actual query — "does this obligate/fiscalize
me" — that the loaded document alone cannot answer. This spec is scoped to that
query only; it does not reopen ADR 0017's decision for the base explain path.

## 3. Corpus and architecture: two-stage retrieval

### 3.1 Why not bulk-index everything

Verified 2026-07-30 against BCN's own SPARQL endpoint (recorded in ROADMAP.md):
the Ley+DL+DFL universe is **53.215** documents, not the ~21.000 originally
assumed, and BCN's own linked data has no field marking a norm in force or
repealed (confirmed against the `bcn-norms` ontology and an IFLA paper naming
this an open, unresolved problem in the same dataset). Downloading and indexing
all 53.215 full documents up front would mean: a large one-time ingestion job
against a public agency's service, a multi-gigabyte local store with no natural
place to stop, and a staleness problem with no way to know what changed, because
the vigencia signal does not exist. Research recorded in ROADMAP.md found this
is not the pattern production legal-RAG systems use for this class of problem.

### 3.2 The two stages

**Stage 1 — local metadata index, no network at query time.** Built once from
BCN's SPARQL endpoint (the refresh mechanism is left to plan/implementation
time — see section 9):
id, title, type, `createdBy` (issuing organism), publish date, promulgation
date, for the Ley+DL+DFL universe. No full text. Small enough that indexing cost
is not a real constraint (short-text embedding/indexing at this row count is
fast on CPU, per the research in ROADMAP.md).

**Stage 2 — full text on demand, for the shortlisted candidates only.** At query
time:

1. Filter stage-1 candidates by organism/type relevant to the figure — municipal
   organisms for `autoridad comunal`; the sectoral law matching the chosen
   organization type for `dirigente` (e.g. `createdBy` filtered toward the
   labor/union space for a sindicato leader).
2. Filter further by a date window, standing in for the vigencia field BCN does
   not provide. This is not a workaround improvised for this project — legal-RAG
   research treats "was this provision valid as of this date" as a hard
   constraint precisely because corpora like this one lack a reliable status
   field.
3. Fetch full text for the shortlisted handful only, through the existing
   `input` layer (the same fetch path already used for URL sources — no new
   bulk-fetch machinery).
4. Run keyword/BM25 matching over that small fetched set to find the passages
   that actually answer the query, per the earlier BM25-vs-dense finding (0,3
   percentage point gap, recorded in ROADMAP.md) — no second GGUF or embedding
   model needed for this step.

### 3.3 Deferred, not built now

A hybrid variant of stage 2 (e.g. adding semantic/dense search on top of the
keyword match) stays open for future research once a working v1 exists to
measure against. Not designed further here; not a commitment.

A small hand-picked list of foundational laws (Ley 18.695, Ley 19.418, etc.)
was considered as a simpler alternative to the metadata index. Rejected as the
primary design because it is brittle — it misses any relevant law outside the
hand-picked set and needs manual upkeep — but noted here as a fallback if the
metadata-index approach runs into trouble at implementation time.

## 4. Grounding — extending, not weakening, ADR 0008

ADR 0008's anti-invention guarantee currently rests on the model seeing only the
text the user handed it. Retrieval breaks that premise, so the guarantee is
carried forward explicitly rather than assumed:

- Every claim in the new section must be traceable to a specific retrieved
  passage and its source (extending ADR 0014's verbatim-citation principle and
  FR-7.1's source-identification display to retrieved content, not just the
  primary document).
- If stage 2 finds no in-scope candidate, the new section says so explicitly —
  the same "no se puede determinar" behavior ADR 0008 already requires for the
  primary document, not a plausible-sounding guess assembled from whatever was
  retrieved.
- Retrieved norms are **never** themselves run through `explain()`. They are
  excerpted for grounding only. The one document that ever receives the
  four/five-section treatment is the *ley* the user loaded — this bounds the
  blast radius of retrieval to "supporting citations," not "a second thing being
  summarized."

## 5. Output contract

A fifth section, **"Cómo te afecta a ti"**, appears only when `nivel` is
`dirigente` or `autoridad comunal`. The existing four sections (Qué hace, A
quién afecta, Artículos clave, En una frase) are unchanged for every `nivel`
value, including the new ones. The GUI/CLI Markdown parity test continues to
pass without modification, because it exercises the four-section path.

This extends ADR 0007 and needs its own ADR before implementation — consistent
with how ADR 0023 followed directly from its ROADMAP research entries.

## 6. Data flow (dirigente / autoridad comunal path only)

```
loaded ley + nivel=dirigente(tipo) or autoridad_comunal
        |
        v
stage 1: local metadata index  -- filter by organism/type + date window
        |
        v
shortlist of candidate norma ids (no network so far)
        |
        v
stage 2: fetch full text for shortlist only (existing input/fetch layer)
        |
        v
keyword/BM25 match over the fetched set -> grounded passages + their source ids
        |
        v
section-5 prompt: synthesize "Cómo te afecta a ti" from grounded passages only,
                  under the same anti-invention guardrail as the rest of explain()
        |
        v
output: existing 4 sections (unchanged) + section 5 (new), each citation traced
        to its source, same as FR-7.1 does today
```

`ciudadano` and `legislador` skip this entire flow and behave exactly as
`publico`/`tecnico` do today.

## 7. Error handling

- **Stage-1 index unavailable or empty** (e.g. first run before the index is
  built): the figure-specific control is disabled or the fifth section says
  retrieval is not available, rather than silently falling back to `ciudadano`
  behavior without telling the user why.
- **Stage 2 fetch fails** for a shortlisted candidate (network error, BCN
  serving an error page — the same 189-character failure mode already
  documented in ROADMAP.md for malformed URLs): that candidate is dropped from
  the grounded set, not treated as if it had no relevant content. If the
  grounded set ends up empty, section 5 states that explicitly.
- **No candidate passes the organism/type/date filter**: section 5 says so
  explicitly. This is the expected, honest outcome for a `ley` genuinely
  unrelated to municipal or organizational obligations, not an error.

## 8. Testing

- Faithfulness spot-check for section 5, same discipline as the existing
  four-section check: every claim traced to a retrieved passage that actually
  contains it.
- A case where the filter legitimately finds nothing, asserting the explicit
  "no se puede determinar" output rather than a fabricated answer.
- GUI/CLI Markdown parity test for the existing four sections stays green
  untouched, proving the new path is additive.
- `dirigente` organization-type selector: each type maps to the expected
  narrowed organism/type filter (no cross-contamination, e.g. a sindicato
  leader's query never pulling municipal-only content).

## 9. Out of scope for this spec

- General Q&A over the full corpus without a loaded document (rejected earlier
  in the brainstorming session, recorded in the conversation this spec came
  from).
- Resolving in-document cross-references (`bcnnorms:modifiesTo` /
  `regulates`) for the primary *ley* itself — a related but separate idea, not
  designed here.
- Any change to the `ciudadano`/`legislador` (formerly `publico`/`tecnico`)
  behavior beyond the name change.
- The refresh mechanism for the stage-1 metadata index (cron, manual, on-demand)
  — left to plan/implementation time.
