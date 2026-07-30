# Brand profile — leyllana

**Status:** lean, built from existing project context (2026-07-30), not a full interview.
Update it before major campaign work; fine as-is for one-off social pieces.

## Identity

leyllana explains Chilean laws and *boletines* in plain Spanish. It is the first tool of
**Germen Digital Socialista (GDS)**, a political digital-socialist movement/party project.
Local-first: the default engine runs on the user's own computer, no cloud unless explicitly
authorized per run. Free, AGPL-3.0, open source.

## Positioning & point of view

- "Sovereignty is not declared, it's programmed" (`la soberanía no se declara, se programa`) —
  the recurring refrain across leyllana content. Local-first is a position, not a feature.
- Anti-invention as the central guarantee: leyllana only explains what is actually in the
  source text; if something isn't there, it says so rather than filling the gap. This is
  tested and measured, not a marketing claim.
- Technically serious, not a toy — content should read as "real engineering happening," never
  generic AI-startup hype.

## Audience (for this folder's content specifically)

**Primary: GDS party colleagues** — politically engaged, computer-literate but not
programmers. They need to *understand and appreciate* the tool, not operate it technically.
Secondary (not yet targeted): the general public and municipal/community dirigentes leyllana
is ultimately built for.

## Voice

Governed by the **`voz-de-felipe`** skill — do not duplicate or restate its rules here. Every
piece of prose for this folder runs humanizer-pass-then-`voz-de-felipe`, per
`social/CLAUDE.md`.

## Proof

- Local-first, verified: default engine is `llama.cpp`, runs on-device (ADR 0005).
- Anti-invention guardrail is tested and its failures are recorded, not hidden (ROADMAP.md's
  own fabrication findings are kept on record even when embarrassing).
- Free and open source: AGPL-3.0, public repo.

## Guardrails

- Never invent a fact, figure, or feature. If a claim about status/roadmap isn't confirmed,
  don't publish it.
- **Do not disclose unannounced product direction.** As of 2026-07-30, a future web-app
  version is planned but not public — never state or imply this in any social/ piece. A
  generic "coming soon" is fine; naming *what* is coming is not, until Felipe says otherwise.
- No emojis. No em-dash as punctuation. Spanish for anything GDS-facing (per the root
  CLAUDE.md's English/Spanish rule).
- Not a lawyer: never let content imply leyllana gives legal advice.

## Visual identity

Owned by **`design-and-templates`**, not duplicated here — see
`social/design-templates.md` once written. Quick pointer: GDS palette is
`#7a1518` / `#c1121f` / `#d62828` / `#ffe0e0`; the mark is the GDS "germen" sprout (kept
identical across GDS tools) with an open book in front for leyllana specifically.

## Example posts

- `social/leyllana-post.png` — single-image post explaining what leyllana is, why local-first
  matters, and the anti-invention guarantee. Being revised now for logo size/contrast.
