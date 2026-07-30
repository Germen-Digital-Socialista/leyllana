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

## A dense one-pager is the wrong shape for Instagram/WhatsApp, researched 2026-07-30

**A single image carrying a whole one-pager's worth of text is not an
Instagram-native format — it is a PDF page shrunk into a square, and it reads
as a wall of text.** This was learned the hard way (a first attempt looked
fine on a laptop and was unreadable in an actual feed-sized preview).
Confirmed by broad research, not assumed:

- **One idea per slide.** Carousels (multiple 1080x1350 slides swiped
  through) are the right format for anything with more than one point.
  "Highlight a single message... if it needs a paragraph, split it across two
  slides" is the recurring rule. A one-pager's worth of content is a
  **carousel of slides**, not one dense image, full stop.
- **Carousels measurably outperform single images for exactly this kind of
  content** — reported engagement gains up to ~50% over single posts, more
  saves, more reach, and the algorithm favors and re-serves high swipe-through
  carousels. Educational/explainer content specifically performs best at
  **5-12 slides**.
- **Font floor for a slide meant to be read, not just glanced at, is 24-30pt
  in the final exported pixels.** Body copy at anything close to a print
  one-pager's size (the ~12-13px-equivalent used in the first PDF-derived
  attempt) is unreadable at feed size — "if it looks small on your laptop,
  it's illegible on mobile" is the standard warning.
- **Canvas: 1080x1350 (4:5), not 1080x1080 square**, for both single posts and
  carousel slides as of 2026. Keep all text out of the outer ~250px (top) and
  ~340-400px (bottom) safe zones, and roughly 60-80px from the side edges.
- **Meta's own guidance caps text coverage around 20% of the frame** — the
  rest is visual breathing room, not empty space to fill with more copy.
  1-2 fonts per slide, bold sans-serif (Montserrat/Anton-class reads best at
  small mobile sizes), one clear visual hierarchy: headline, then a short
  supporting line, nothing else competing for attention.
- **A cover slide is its own job**, not just slide 1 of the content: a short
  hook (5-8 words), the single highest-contrast visual element on the whole
  set, and a swipe cue, all deciding in about a second whether anyone opens
  the rest.
- The PDF one-pager (a document meant to be read start to finish, at a
  reader's own pace) and an Instagram/WhatsApp PNG (glanced at for ~3 seconds
  in a moving feed) are **different documents with different content
  budgets**, not the same content resized. Don't derive one from the other by
  shrinking; write the carousel's per-slide copy separately, much shorter.

Sources: [Instagram Carousel Best Practices 2026 — Carouselli](https://carouselli.com/blog/instagram-carousel-best-practices), [Instagram Post Design Mistakes — The Divine Tech](https://www.thedivinetech.com/blog/instagram-post-design-mistakes-avoid), [Why Your Social Media Text Is Too Small](https://anddreamsdigital.com/why-your-social-media-text-is-too-small/), [Instagram Safe Zone Guide 2026 — Outfy](https://www.outfy.com/blog/instagram-safe-zone/), [One-idea-per-slide carousel principle — SlideGenius](https://www.slidegenius.com/blog/the-importance-of-having-one-point-per-slide-and-how-to-do-it), [Carousel vs single post engagement — postnitro.ai](https://postnitro.ai/blog/post/social-media-research-study-carousel-vs-single-post)
