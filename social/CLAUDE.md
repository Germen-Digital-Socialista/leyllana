# CLAUDE.md — social/

Guidance specific to this folder, in addition to the root `CLAUDE.md`.

## Format rule

**One-pagers and other informational hand-outs in this folder are PDF or PNG,
never HTML.** These are meant to be opened, printed, or forwarded as a single
file by people who are not going to run a local server or trust an attachment
that executes anything. An `.html` file invites exactly that friction and
looks like a dev artifact, not a finished document. Render to PDF (a document
meant to be read/printed) or PNG (a single image, e.g. for a social post) and
commit only that output. Do not leave the HTML source in this folder; if a
build step needs one, keep it outside `social/` (scratchpad or a private
build folder) and commit only the rendered result here.
