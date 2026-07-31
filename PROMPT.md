# leyllana — session handoff, 2026-07-31

Read first: `ROADMAP.md` top section ("First real validation: faithful, 2026-07-31") for
the full honest result. Then `docs/superpowers/specs/2026-07-30-fallback-article-selection-design.md`
and `docs/superpowers/plans/2026-07-30-fallback-article-selection.md` (marked Implemented)
if touching the code.

Commits this session: `ac51c31`..`2386da5` (~50 commits), all pushed to `main` on GitHub.

## Done

- Diagnosed Gemma 3 1B's article-selection failure as a capacity limit, not a
  prompt-wording problem (couldn't cap "Articulos clave" at 5-6 even with a one-shot
  example).
- Designed, planned, and fully implemented a BM25 + Qwen3-Reranker-0.6B cross-encoder
  mechanism that pre-selects key articles instead of asking the fallback model to judge
  importance itself. New module `engine/ranking.py`, wired into `explain()` for
  `nivel publico` + local provider only.
- Downloaded a real `Qwen3-Reranker-0.6B-Q8_0` GGUF and validated the mechanism end to
  end against **Qwen3-1.7B** on Ley 21.663. Found and fixed **3 real bugs** along the
  way (llama-server's 512-token reranking batch cap, a token-count-vs-token-budget
  selection bug, and a label/text duplication bug in the final prompt) — all only
  surfaced by actually running it, not by unit tests.
- **Final state: 5/5 faithful after all fixes**, zero fabricated content across every
  run today. Not yet enough independent full-pipeline samples (fresh condense each
  time) to claim a real faithfulness rate — that's the honest, explicit next step at
  the top of ROADMAP.md.
- Side thread: built GDS party-facing materials in `social/` (one-pager PDF,
  Instagram/WhatsApp-ready PNG, `brand-profile.md`, several researched design rules
  recorded in `social/CLAUDE.md`). Added a `leyllana.cl` distribution-site note to
  Phase 4 in ROADMAP.md.

## Genuinely open, nothing blocked externally

1. More independent full-pipeline validation runs (different documents, fresh condense
   each time) before trusting the BM25/reranker mechanism broadly.
2. Once that exists: revisit what ADR 0025 (the Gemma swap) actually needs to decide,
   since Qwen3-1.7B + this mechanism may no longer need Gemma at all.
3. Retrieval-layer (`dirigente`/`autoridad comunal`) spec review — still sitting since
   before tonight's benchmark thread took over, needs Felipe's read-through before it
   becomes an ADR.
4. ADR 0023 (Vulkan build) implementation — already decided, zero new decisions, easy
   win, never picked up.

No pending questions, no uncommitted work, working tree clean.
