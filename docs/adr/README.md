# Architecture Decision Records — leyllana

This directory is the project's decision log. Each file records **one**
architecturally-significant decision: its context, the decision itself, and the
consequences. The records live in version control next to the code so the
"why" travels with the codebase.

If you are an agent (or a human) about to touch these files, read the rules
below first. They are not optional house style — they are what an ADR *is*.

## What an ADR is

The Architecture Decision Record was popularized by Michael Nygard in his 2011
post "Documenting Architecture Decisions" and has been in the "Adopt" ring of
the ThoughtWorks Technology Radar since November 2017. The idea is deliberately
lightweight: a short, plain-text file per decision, stored with the code rather
than in a wiki, so the record stays in sync with what it describes.

This repo uses a **MADR-lite** format (Markdown Any Decision Records, trimmed).
Every ADR file carries these fields, in order:

- **Status** — see the lifecycle below.
- **Date** — when the decision was made (`YYYY-MM-DD`).
- **Deciders** — who made it (here: Felipe Carvajal Brown).
- **Context** — the forces and constraints that made a decision necessary.
- **Decision** — what was chosen, stated plainly.
- **Consequences** — what follows from it, good and bad.
- **Alternatives considered** — the options that were weighed and rejected.

Files are numbered and kebab-cased: `000N-short-title.md`.

## The core rule: an accepted ADR is immutable

**Once an ADR's status is `Accepted`, its body is never edited again.** The
collection is an *append-only log*. Its entire value is that you can open any
record months later and know exactly what was true, and why, at the moment it
was written. Editing an accepted decision in place destroys that guarantee: it
rewrites history and hides that the direction ever shifted.

The **only** part of an accepted ADR that may change over time is its
**`Status`** line. Trivial, meaning-preserving fixes (a typo, a broken link)
are also fine. Anything that changes the *meaning* of the decision does **not**
go into the existing file — it goes into a **new** ADR.

So, concretely:

| You want to...                                  | Do this                                  |
|-------------------------------------------------|------------------------------------------|
| Fix a typo / dead link (no meaning change)      | Edit in place.                           |
| Update the `Status` line                        | Edit the `Status` line only.             |
| Add new context, caveats, or consequences       | Write a **new** ADR.                      |
| Change, narrow, or reverse the decision         | Write a **new** ADR that supersedes it.  |
| Record a follow-on/related decision             | Write a **new** ADR.                      |

If you are ever unsure whether an edit "changes meaning," treat it as though it
does and write a new ADR. New ADRs are cheap; a corrupted log is not.

## How to change a past decision (supersede)

You do **not** rewrite the old decision. You add a new one and point the two at
each other:

1. Write a new ADR (`000M-...md`) that states the new decision in full. It must
   stand on its own — a reader should not need the old ADR to understand it.
2. In the **new** ADR's `Status`, mark it accepted and note what it replaces:
   `Accepted — supersedes [0003](0003-...md)`.
3. In the **old** ADR, change **only** the `Status` line to point forward:
   `Superseded by [0012](0012-...md)`. Leave its Context / Decision /
   Consequences / Alternatives exactly as they were.
4. Update the index table below so both statuses are current.

A single new ADR can supersede *part* of an old one. If ADR 0012 only overturns
one aspect of ADR 0003, say so in 0012's Context and Decision, and 0003's status
reflects that it has been superseded on that point while the rest still stands.

This is the standard Nygard/adr-tools convention: "Superseded by ADR-NNN" on the
old record, "Supersedes ADR-MMM" on the new one, linked both ways.

## Status lifecycle

- **Proposed** — under consideration, not yet agreed.
- **Accepted** — agreed and in force. From here the body is immutable.
- **Rejected** — considered and declined (kept for the record, not deleted).
- **Deprecated** — no longer relevant because the context changed, but not
  replaced by a specific new decision.
- **Superseded by 00NN** — replaced by a later ADR; that ADR carries the current
  decision.

## Index

Keep this table in sync whenever an ADR is added or a status changes.

| #    | Title                                                          | Status   |
|------|----------------------------------------------------------------|----------|
| 0001 | Product and scope: a plain-language Chilean law explainer       | Accepted |
| 0002 | GUI stack: PySide6/Qt desktop                                   | Accepted |
| 0003 | Swappable engine with a local llama.cpp default                | Accepted (CPU-only part superseded by 0012) |
| 0004 | Cloud providers via web-subscription CLIs in an embedded terminal | Accepted |
| 0005 | Local-first and data sovereignty by default                    | Accepted |
| 0006 | Input handling: file, paste, and URL                           | Accepted |
| 0007 | Output contract: structured Spanish sections and audience levels | Accepted |
| 0008 | Anti-invention and not-legal-advice guardrails                 | Accepted |
| 0009 | License: AGPL-3.0                                               | Accepted |
| 0010 | Public repository and naming                                   | Accepted |
| 0011 | Input validation and OCR fallback                              | Accepted |
| 0012 | CPU baseline with optional GPU acceleration                    | Accepted (supersedes CPU-only part of 0003) |

## Further reading

- Michael Nygard, "Documenting Architecture Decisions" (2011) — the original.
- adr.github.io — ADR organization, templates, and the MADR spec.
- ThoughtWorks Technology Radar, "Lightweight Architecture Decision Records."
