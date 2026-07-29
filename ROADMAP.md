# ROADMAP — leyllana

Phase-based, not calendar-dated. Status values: **Not Started** / **In Progress**
/ **Blocked** / **Done**. Each phase links the ADRs that shaped it.

---

## Phase 0 — Foundation and decisions
**Status: Done**

Repository, license, brand, and the decision record that fixes the architecture
before any code.

- Repo created (public) under `Germen-Digital-Socialista`, AGPL-3.0.
- PRD, ROADMAP, and the initial ADR set written.
- README, logo, `.gitignore`, `CLAUDE.md`.
- Shaped by: ADR 0001, 0002, 0003, 0004, 0005, 0009, 0010.

## Phase 1 — Core engine (headless)
**Status: Done**

The `explain(text, nivel)` pipeline works end to end with the default local
engine, no GUI, provable from the CLI. Validated on a real BCN law (fetch ->
source-id -> local Qwen3 -> four sections), both single-pass and chunked.

- `input` layer: file (`.txt`/`.pdf` via PyMuPDF), paste/stdin, URL fetch
  (BCN/leychile XML, Senado/Camara HTML, PDF-over-URL), plus document validation
  and a Tesseract OCR fallback for scanned / empty / protected PDFs (FR-1.1,
  ADR 0011).
- `prompt` layer: Spanish structured prompt, `nivel` switch, anti-invention
  guardrail, scoped verbatim-citation of identifiers so every named article,
  date, or figure can be spot-checked against the source (FR-6.1, ADR 0014),
  disclaimer footer.
- `engine` layer: local provider driving the `llama-server` binary as a subprocess
  (ADR 0016), producing the four structured sections with Qwen3-4B (default) /
  Qwen3-1.7B (low-RAM), on a CPU baseline with optional GPU (ADR 0012, 0015).
- Long documents that exceed the model context are processed with a structure-
  aware map-reduce (extract grounded key points per fragment, then synthesize),
  keeping faithfulness front and center (ADR 0017).
- Output carries source identification (title, norm type, issuing body, date,
  URL, consultation date) when extractable, never invented (FR-7.1); captured in
  the same fetch that reads the text.
- **Map-reduce on the 4B default: measured.** Ley 21.663 (99.468 caracteres, 55
  articulos) via 13 fragmentos, GPU: **50 min**, sin inventar nada. Las
  comprobaciones puntuales contra la fuente pasan (articulo 53, articulo 4 y la
  facultad de la Agencia, el tramo de 5.000 a 40.000 UTM). Dos hallazgos:
  - La lectura es mas delgada que la de un proveedor de nube en una sola pasada:
    cita 4 articulos en vez de 6 y deja fuera los plazos de reporte y el control
    judicial sobre el acceso de la Agencia.
  - **Se perdio un identificador**: la sintesis escribio "el articulo sobre
    infracciones" en vez del numero, que ADR 0014 exige citar tal como aparece.
    El prompt de extraccion ya lo pide, asi que se pierde en la reduccion. Un
    solo caso; sin corregir a proposito, para no ajustar contra una muestra.
- **El fallback de baja RAM (Qwen3-1.7B) inventa en normas largas. Medido, sin
  decidir aun.** Misma ley, mismos 13 fragmentos, mismo ctx: 3 min, salida bien
  formada, y **completamente falsa** las dos veces. Primera corrida: explico una
  ley inexistente sobre los deberes de una junta de vecinos. Segunda: la explico
  como una ley de impuestos, con "domicilio fiscal" y "recaudacion", palabras que
  no estan en la fuente; se agarro de "unidades tributarias mensuales" y "a
  beneficio fiscal" (las multas) y construyo un estatuto tributario alrededor.
  Tambien ignoro el tope de articulos (11 en vez de cinco o seis). Las dos
  corridas terminaron en codigo 0, con las cuatro secciones y el disclaimer: el
  pipeline informo exito mientras emitia ficcion.
  - Queda medido en una norma larga, no en una corta. ADR 0015 designa este modelo
    como fallback y sigue vigente: la decision de cambiarlo necesita su propio ADR
    y el cuadro completo, incluido el comportamiento en un boletin breve, que es
    la mayor parte del corpus del piloto.
- **Deferred follow-ups (minor, not blockers):** RAM-based auto-switch between the
  default and low-RAM model; a richer GPU auto-detect than the current
  `nvidia-smi` probe; and a persistent provider for the Phase 3 GUI (done in
  Phase 3, ADR 0019).
- Shaped by: ADR 0003, 0005, 0006, 0007, 0008, 0011, 0012, 0014, 0015, 0016, 0017.

## Phase 2 — Cloud via a subscription CLI
**Status: Done**

The cloud path works without an API key: leyllana drives an agent CLI as a
subprocess and rides the user's existing subscription. Validated end to end on a
real BCN norm with both shipped presets, in both audience levels.

- Generic `cli` provider (ADR 0018): argv from config, document on stdin, system
  prompt by file. Any other agent CLI is a config line, not new code.
- Verified presets: `claude` (Claude Code) and `kimi`. Codex and Gemini work
  through an explicit `command` but ship no preset, because an untested preset is
  a claim we cannot make.
- Explicit consent gate before any content leaves the machine (FR-5.1,
  ADR 0013), surfaced headless as `--acepto-nube`. The run aborts before the
  first subprocess, so the map-reduce cannot leak a first fragment either.
- The chunking budget now comes from the provider's own context, so a document
  that fits in one cloud call is no longer split (ADR 0017).
- `leyllana.example.toml` documents the options.
- **Found while verifying, both silent (exit 0, plausible wrong Spanish):** a
  multi-line system prompt in argv is truncated at the first newline by a Windows
  `.cmd` shim, stripping the anti-invention guardrail; and a Python-based CLI
  mangles accented Spanish on its pipes unless UTF-8 is forced. Both are fixed and
  recorded as constraints in ADR 0018.
- **Deliberately excluded:** API-key providers (now Phase 5) and the `pywinpty`
  terminal panel (now Phase 3, with the GUI it belongs to).
- Shaped by: ADR 0003, 0004, 0013, 0017, 0018.

## Phase 3 — GUI
**Status: Done**

The PySide6 desktop app: source panel, result panel, embedded terminal, export.
Installed as the `gui` extra (`uv sync --extra gui`), run with `leyllana-gui` or
`python -m leyllana.gui`.

- Source on the left, result on the right in a draggable splitter, terminal in a
  collapsible bottom dock. The split is deliberate: checking an explanation
  against its source (FR-6.1) means seeing both at once.
- Three input paths (file / paste / URL) handed to the same
  `resolve_with_source` the CLI uses; `nivel` picker; export to Markdown.
- **The GUI is a second front door, not a second implementation.** What it
  renders and exports is the same Markdown the CLI prints, composed from the
  same `SourceInfo.to_markdown()` + `Explanation.to_markdown()`, and its error
  messages are the same strings as `cli.py`.
- FR-10 in full: stage, fragment *n* of *N*, elapsed time, and a cancel control
  that reaches the running work. **The progress bar goes indeterminate when
  there is nothing countable rather than showing an invented percentage** — the
  fragment count comes from the map loop of ADR 0017 and nowhere else.
- **Cancel had to be made real first, and it is measured.** The local call was
  one blocking request with a 600s timeout, so a button on top of it would have
  been a lie; the response is now streamed and the token checked between frames
  (ADR 0020). Against the real Qwen3-4B on a 2-fragment run: **0.08 s** to
  return when the model was generating, **7.78 s** when the cancel landed during
  prompt processing, before the first token. That second number is the window
  ADR 0020 predicted and declines to hide.
- Visual accessibility: light / dark / follow-the-system themes and a type-size
  control, with the contrast ratios asserted in tests rather than assumed.
- Source identification block shown in the result panel when available
  (FR-7.1, display side).
- Settings write `leyllana.toml`, the same file the CLI reads (ADR 0021), so the
  window and the terminal never disagree about the configured provider.
- Consent gate (ADR 0013) as a modal before each cloud run, defaulting to *No
  enviar*, with no remember-me option, which would be the exact door ADR 0013
  closes.
- Embedded `pywinpty` terminal panel (Windows first, ADR 0004). Verified against
  pywinpty 3.0.5: spawns a shell, echoes, terminates. **It is a text view, not a
  VT emulator** — ANSI escapes are stripped rather than interpreted, so a
  full-screen program (vim, htop) will look wrong. Off Windows, or without
  pywinpty, it writes the reason into the view and keeps working for the job
  below.
- **The terminal panel is also where you see what left the machine (ADR 0022).**
  ADR 0004 made it the cloud path; ADR 0018 replaced that with a headless
  subprocess and left the panel connected to nothing, so a consented send
  happened entirely out of sight. A cloud run now prints the exact argv, the
  payload size marked as leaving the machine, the response, and the exit code and
  elapsed time, and the dock opens by itself when consent is given. The document
  text is never printed; its size is. The response arrives when the process
  exits, not token by token, because `communicate()` is what keeps the cancel
  polling deadlock-free.
- **Visual pass done, and it caught a silent bug.** `setDefaultStyleSheet` has no
  effect on `setMarkdown` content — Qt only applies it to `setHtml` — so the
  first stylesheet was ignored without any error. Formatting is now applied over
  the document blocks: section headings above the body, the Fuente block below it
  and dim, and fragment-level formatting so the source URL keeps its link colour.
  Before the pass the provenance block filled the first third of the panel; three
  sections now fit above the fold. All presentation only, with a test pinning the
  export to what the CLI prints.
- **Closed from Phase 1's deferred list:** the persistent provider. One provider
  lives for the window's session, so only the first run pays the GGUF load.
- **Still deferred from Phase 1:** RAM-based auto-switch between the default and
  low-RAM model, and a richer GPU auto-detect than the `nvidia-smi` probe.
- Shaped by: ADR 0002, 0004, 0007, 0013, 0018, 0019, 0020, 0021, 0022.

## Phase 4 — Packaging and pilot
**Status: Not Started**

Ship something a non-technical user can install and run, then test it on real
*boletines* with real readers.

- Windows installer bundling the app + default model.
- Pilot with a small set of real laws/bills and target readers.
- Faithfulness spot-check pass (output invents nothing vs. source).
- **Decide here what to do about local speed on long norms.** Measured in Phase 1:
  50 minutes for a 55-article law on the 4B default. Most pilot documents are far
  shorter, and the mitigation is now built rather than promised: the Phase 3 GUI
  shows the stage and the fragment count as it goes, and Cancelar stops the run
  within a token (FR-10, ADR 0019, 0020). What the pilot has to answer is whether
  a visible, interruptible 50-minute wait is still an obstacle for real readers.
  If it is, the levers are a larger context (fewer fragments) or routing long
  documents to the subscription CLI path (ADR 0018).

## Phase 5 — Cloud providers by API key
**Status: Not Started**

The metered path, for users who have a key but no subscription. Deferred past the
pilot on purpose: the subscription path of Phase 2 already covers the cloud need,
so this should not hold up putting the tool in front of real readers.

- Claude / OpenAI / Gemini via a key the user pastes, stored locally only.
- Reuses the consent gate and the provider seam already built (ADR 0013, 0018);
  the names are already in the registry with a clear not-implemented error.
- Shaped by: ADR 0003, 0004, 0013.

---

## Deliberately deferred (candidate future GDS tools, not leyllana v1)

- **Audience-specific output beyond the two `nivel` values.** Today `publico` and
  `tecnico` change register (ADR 0007); the idea is to name the reader instead:
  the president of a *junta de vecinos*, an *alcalde* or municipal team, a
  legislator or their staff. Each wants a different thing from the same norm.
  Ley 21.663 is the case that surfaced it: the honest answer for a dirigenta is
  "esto no te obliga a ti", while a legislator wants the articulado and the
  fiscalization regime. Cheap to build (prompt and output contract only, no new
  dependency) but it changes ADR 0007, so it needs its own ADR and a design pass
  first. Not designed yet, on purpose.
- **A retrieval layer.** Tracked separately from the audience idea above, because
  the costs are not comparable: answering "how does this affect *your* comuna"
  needs context the source document does not contain (municipal competencies,
  budget, who fiscalizes), which means a corpus, an index, a dependency, and a
  much harder anti-invention problem than summarizing one text (ADR 0008). The
  audience framing needs none of that.
- Multi-law comparison / redline diffing.
- Q&A over a law with cited articles.
- Legislative tracking / scanning for new AI-related *boletines*.
- Cross-platform terminal backend (Linux/macOS) beyond `pywinpty`.
- RapidOCR cross-checking of the Tesseract output, and any vision-LLM OCR
  opt-in, beyond the Tesseract-only v1 path (ADR 0011).
- Full clickable span-linking of each cited mention to its exact source
  fragment, beyond the verbatim-citation traceability of v1 (ADR 0014).
