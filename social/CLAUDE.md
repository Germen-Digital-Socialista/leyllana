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

Before rendering: verify a one-pager is actually one page (count the PDF's
page objects, or check the rendered image height) before calling it done.
"One-pager" means one page, not approximately one page.

## Voice pass order

**For any prose written for this folder: run a humanizer pass first (the
`article-humanizer` or `linkedin-humanizer` skill, whichever fits the content
type), then `voz-de-felipe` as the final pass.** Humanizer first strips
generic AI-writing patterns from the draft; `voz-de-felipe` then layers
Felipe's actual voice on top as the last step before rendering.

## PNG export rule (Instagram / WhatsApp), researched 2026-07-30

**A screenshot-dimension PNG is effectively unsendable — it looks broken or
gets silently wrecked by the platform before anyone reads it.** Verified via
web research, not assumed:

- **Width must be 1080px, full stop.** Instagram's 2026 standard is 1080px
  wide; anything narrower gets upscaled and reads as blurry/pixelated.
  Recommended canvas: **1080x1350 (4:5 portrait)** for a normal feed post, or
  **1080x1080 (square)** when the content itself is naturally square-ish
  rather than tall — don't force a tall crop onto content that isn't tall,
  pad the canvas with the brand background instead of stretching or
  letterboxing the design.
- **Keep anything essential (logo, headline, credit line) inside the center
  3:4 area.** Instagram's feed can show up to 4:5, but the profile-grid
  preview crops to 3:4 — content only safe in the outer strip of a 4:5 image
  disappears from the grid view.
- **PNG is the right format for this content (text, flat color, sharp
  lines) — but only WhatsApp's "Document" send path preserves that.**
  WhatsApp's normal photo-picker send re-encodes *any* image (PNG included)
  to lossy JPEG at ~70-100KB and resizes the long edge to ~1600px,
  regardless of the source format — exactly the kind of compression that
  turns crisp text fuzzy. **Always tell whoever is sending this to use
  WhatsApp's "Document" attachment, not "Photo," to send the actual PNG
  bytes.** Sent as a photo, the text-crispness reason for choosing PNG over
  JPEG is moot — the platform throws it away anyway.
- **Export in sRGB.** Instagram auto-converts to sRGB and discards anything
  else (ProPhoto/Adobe RGB); don't rely on an embedded wide-gamut profile
  surviving upload. A PNG with no embedded ICC profile at all is read as
  sRGB by convention and is the safest default — don't attach one.
- **File size:** Instagram's hard cap is 30MB, but that's not the real
  constraint — a well-built PNG of this kind of content should land well
  under 1MB. If it's larger, something is wrong with the export (uncompressed
  layers, an embedded profile, unnecessary alpha channel), not the platform.

Sources: [Instagram Post Size Guide 2026 — Buffer](https://buffer.com/resources/instagram-image-size/), [Instagram media specs & best practices 2026 — HeyOrca](https://www.heyorca.com/blog/instagram-media-specs-best-practices-2026), [WhatsApp image compression — DEV Community](https://dev.to/samma1997/whatsapp-image-quality-loss-fix-it-before-sending-2026-223), [How to send photos as Document on WhatsApp — Mobitrix](https://www.mobitrix.com/whatsapp/how-to-send-photos-as-document-in-whatsapp.html), [PNG vs JPEG for text/screenshots — Reformatly](https://reformatly.com/resources/png-vs-jpeg-quality), [Instagram sRGB/color profile requirements — colormanagement.guide](https://colormanagement.guide/en/troubleshooting/instagram-colors-changed/)
