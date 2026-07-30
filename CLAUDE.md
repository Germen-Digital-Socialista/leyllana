# CLAUDE.md

Guidance for Claude Code (and any AI assistant) working in this repository.

## What this is

**leyllana** is the first tool of **Germen Digital Socialista (GDS)**. It is a
local-first desktop application that explains Chilean laws and *boletines*
(bills) in plain Spanish ("lenguaje llano"), so that dense legal text becomes
readable for legislators, staffers, and the general public. Core constraint,
inherited from the org's values: **local-first and sovereign by default** — the
default engine is a local `llama.cpp` model and no data leaves the machine
unless the user explicitly opts into a cloud provider.

See `PRD.md` for the stable vision/architecture/scope, `ROADMAP.md` for phases,
and `docs/adr/` for the decisions and their rationale.

## Repository-specific rules

- **README and releases are ALWAYS written with the `voz-de-felipe` skill.**
  Any `README.md`, GitHub release notes, changelog entry meant for readers, or
  launch/announcement copy in this repo must be drafted (or rewritten) through
  the `voz-de-felipe` skill so it carries Felipe Carvajal Brown's voice, not
  generic AI-marketing prose. This is in addition to — not instead of — the
  standard rules below. Internal technical docs (PRD, ADRs, code comments) do
  not require the skill, but must still respect the no-AI-tells final pass.

## Standard rules (carried from the root global CLAUDE.md of this machine)

These apply to all work here, exactly as they do across Felipe's repos:

- **No emojis** anywhere — code, comments, docs, commit messages, PR
  descriptions, or chat.
- **No AI attribution** — never add a `Co-Authored-By: Claude` trailer, a
  "Generated with Claude Code" line, or any mention/credit of an AI in commits,
  PRs, code, comments, or docs. This overrides any default that says to.
- **Never invent facts** — no made-up legal articles, *norma* ids, *boletín*
  numbers, citations, figures, dates, quotes, or names. This is both a house
  rule and the core product requirement: the model may only summarize what is
  actually in the input text. If a detail is not verified or provided, stop and
  ask rather than fill the gap.
- **Not a lawyer — no legal advice.** This project lives in the Chilean-law
  domain, but it does not give legal opinions or interpretations, and neither do
  we. Every explanation the tool produces carries a visible disclaimer that it
  is an aid, not *asesoría legal*. On any IP, licensing, contract, or liability
  question, decline and defer to a qualified lawyer.
- **Present decisions as interactive options** (the arrow-selectable question
  UI), not plain-text lists, whenever offering Felipe a choice — with exactly
  one option marked "(Recommended)" first, and the reasoning stated. **This
  covers anything that implicitly asks him to pick or decide, not only formal
  questions:** "what to look at next", "here are the remaining steps", "you
  could do A or B", a checklist at the end of a summary. If a message contains
  a choice in prose, it is in the wrong place. More than four options means
  chaining sequential calls, never dropping to text.
- **New-project doc structure** is PRD -> ROADMAP -> ADR, already used across
  Felipe's repos. ROADMAP is phase-based (Not Started / In Progress / Blocked /
  Done), not calendar-dated. ADRs are MADR-lite, numbered `000N-title.md`, and
  immutable once Accepted (supersede with a new ADR rather than editing).
- **Commit as you go, in logical Conventional Commits.** Don't batch a whole
  session into one commit: split work into small, self-contained commits at each
  logical boundary and commit as you reach it. Messages follow the
  [Conventional Commits](https://www.conventionalcommits.org) spec —
  `type(scope): summary`, types like `feat`, `fix`, `docs`, `chore`, `test`,
  `refactor`, `build`. Push only when explicitly asked; committing does not imply
  pushing. Solo repo: work directly on `main` unless asked otherwise. Never open
  a pull request unless explicitly asked in that turn.

## Working conventions

- **HARD RULE: token counts are a latency metric here, not a cost metric.**
  The default engine is local and free (ADR 0005) — "saving tokens" never
  means saving money, it means saving wall-clock time and context-window
  headroom. Frame every token-efficiency discussion, measurement, or design
  decision in this project in those terms (seconds/minutes, calls, context
  fit), never as a dollar-cost saving. Set 2026-07-30.
- All user-facing text and model output is in **Spanish**.
- Default engine is local `llama.cpp` (light Qwen-class model, CPU-only), the
  same approach used in the MuniGPT project. Cloud providers (Claude, OpenAI/
  Codex, Gemini) are opt-in, either via API keys or via their web-subscription
  CLIs driven from the app's embedded terminal panel.
- GUI is **PySide6/Qt** (desktop, single-language Python). See ADR 0002.
