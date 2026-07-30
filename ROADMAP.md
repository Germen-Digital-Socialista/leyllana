# ROADMAP — leyllana

Phase-based, not calendar-dated. Status values: **Not Started** / **In Progress**
/ **Blocked** / **Done**. Each phase links the ADRs that shaped it.

## Contributors

- **Felipe Carvajal Brown** — sole author and developer. Every decision recorded in
  `docs/adr/` is his; he is the `Deciders:` line on all of them.

Add a line per person as the list grows, naming what they actually did rather than
a generic role.

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
  articulos) via 13 fragmentos: **50 min**, sin inventar nada. (Decia "GPU"; el
  2026-07-29 se comprobo que el binario de `backend/bin` no tiene ningun backend de
  GPU, asi que esta corrida fue en CPU como todas las anteriores. Ver el hallazgo
  del build mas abajo.) Las
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

## Agreed but not yet built — open queue as of 2026-07-29
**Status: In Progress**

Recorded here rather than left in a conversation. Each of these was asked for and
agreed; none is built. Ordered roughly by dependency.

1. **Export to PDF and Word, keeping Markdown.** Agreed: PDF is what you send, Word
   is what someone edits. Qt writes PDF natively (`QPdfWriter`); `.docx` needs
   `python-docx`. Changes PRD FR-8 ("Save the explanation as Markdown"), so it
   needs its own ADR. The existing GUI/CLI byte-parity test must keep passing on
   the Markdown path.
2. **Per-`nivel` output templates.** The `nivel` fix (commit `afac933`; **its ADR is
   not written yet**) moved the register into the prompt, but a prompt only asks. Consistency should be enforced by a
   render template per level rather than by the model's cooperation — which is
   exactly what failed before. Design not settled: a per-level Markdown render
   template is inside ADR 0007; extending the output contract with extra fields
   for `tecnico` supersedes it. **Needs a decision before code.**
3. **Live token indicator for the local model.** Show that generation is actually
   moving, not hung. The seam already exists: `on_token` in
   `chat_completion` (ADR 0020) is called per SSE frame and is currently unused by
   the GUI. Wire it to a token counter and rate in the Estado box.
4. **Slow-run escalation.** After ~10 minutes still running, offer to keep waiting
   or to switch to a smaller model. **Blocked on a real conflict:** the smaller
   model we ship (Qwen3-1.7B) is the one Phase 1 measured emitting complete
   fiction on a long norm, twice, exiting 0. Offering that switch would deliver
   invention faster, against the project's central promise. Either the fallback is
   replaced with something tested first (see the model findings below), or the
   offer is limited to wait/cancel until then. **Item 6 is now measured, and it
   halves this item rather than deleting it.** On a GPU-capable build at
   `ctx 16384` the run is 4,8 min, so the ten-minute threshold is never reached and
   no escalation is needed on that path. On CPU no configuration gets under ten
   minutes, so the item survives there in full — and the conflict above survives
   with it, because the only smaller model we ship is the one that emitted fiction
   twice. What changed is the scope: this is a CPU-path feature, not a general one.
5. **Preview the loaded document before running.** The Archivo tab shows only a
   path, so the user cannot tell whether extraction actually worked — which
   matters most exactly when it silently did not, i.e. a scanned PDF that went
   through OCR (FR-1.1). Show the first extracted characters so the input can be
   eyeballed before a 30-minute run starts.
6. **Raise `ctx` and re-measure. Done, and the answer depends entirely on the
   backend build.** Same law, same model, same document bytes, `nivel publico`,
   end to end through `explain()`:

   | build | `ctx` | model calls | total |
   |---|---|---|---|
   | GPU (Vulkan) | 4096 | 25 | **22,9 min** |
   | GPU (Vulkan), `q8_0` KV | 16384 | 3 | **4,8 min** |

   **A 4,8x cut, and the mechanism is not the one this list assumed.** The cost is
   generation, not prompt processing: every map call runs to the `max_tokens = 1024`
   ceiling, so the run costs roughly `calls x 1024 tokens`. What `ctx` controls is
   the number of calls. At 4096 the pooled key points do not fit either, so the
   hierarchical reduction of ADR 0017 fires three times (13 -> 6 -> 3 -> 2) for 25
   calls; at 16384 there are 2 fragments and no reduction at all, for 3.
   - **`ctx 16384` needs `q8_0` KV to exist on a 4 GiB card.** With f16 KV it dies
     at startup: `ErrorOutOfDeviceMemory` allocating the 1 GiB KV buffer. Quantized
     K and V halve that and the same run fits in 3498 MiB.
   - **On CPU the lever is dead, and this was tested rather than assumed.** Prompt
     throughput falls 84,7 -> 41,5 -> 25,9 tok/s and generation 11,4 -> 2,2 -> 1,0
     tok/s as the context deepens, so a single pass over the whole law costs 961 s
     of prompt processing before it emits a token. A larger physical batch, the
     documented remedy, makes it *worse* here (`-ub 2048`: 76,1 and 34,9 tok/s),
     and forcing `-fa on` changes nothing useful.
   - **The reading got better, not just faster.** At 16384 the output cites six
     articles against four, and recovers exactly what Phase 1 recorded the local
     path as missing: the reporting deadlines of Articulo 9. All four were checked
     against the source and are real (`tres horas`, `setenta y dos horas`,
     `veinticuatro horas`, `quince dias corridos`). Nothing invented in either run,
     and the lost-identifier artefact did not recur in either.
   - **Countable progress survives**, which FR-10 needs: 2 fragments is still a
     countable map loop, not a single opaque pass.
   - Adopting any of this changes ADR 0012 (GPU), ADR 0015 (model/ctx) and ADR 0016
     (server binary), so **nothing has been changed in the repo or the config.**

## Corpus retrieval and token cost — research findings, 2026-07-29
**Status: recorded, nothing decided**

Felipe's question: feed a local model via RAG or keywords so tokenization is faster,
without handing it the whole corpus of Chilean law (his estimate, ~21.000 normas),
"training it to find patterns that save tokens". Researched the same day. **Nothing
here is adopted and none of it changes an ADR.**

### Retrieval cuts tokens enormously, for a task we do not currently perform

Measured in a published comparison: long-context prompting processed ~247.754 input
tokens where keyword RAG used 8.569 and semantic RAG 8.399, roughly **29x fewer**.
Another reports 93% fewer tokens and 92% lower latency. The 2026 consensus is not
"RAG instead of long context" but hybrid: retrieve, then reason over what came back.

**But retrieval does not speed up what leyllana does today.** It wins when most
queries are answerable from a few thousand relevant tokens. "Explain this entire law
in four sections" needs the whole law; there is nothing to retrieve away. So a
retrieval layer is a **new capability** — asking questions across the corpus — and
not an optimization of the pipeline that took 59,6 min. Worth keeping straight,
because the two get conflated easily and only one of them is on the critical path.

### The real levers on the current pipeline, in order of size

1. **Fewer calls.** Item 6: `ctx 16384` turns 28 calls into 3, measured 4,8 min.
2. ~~**Prompt caching.**~~ **Checked and discarded the same day.** This was first
   written down as a free win we were ignoring. It is not: `--cache-prompt` is
   **enabled by default** in the build we ship, and the log of the 59,6 min run proves
   it was already working, reusing a mean of **12,6%** of each prompt (up to 80% on
   one call). The reuse is small for a structural reason, not a fixable one: the only
   shared prefix is the system prompt, because every fragment's user text differs.
   And prompt processing is only ~27 s of a ~134 s call, so even eliminating it
   entirely caps the gain near 20%. Recorded so nobody spends a session on it twice.
3. **Prompt compression.** Felipe's instinct already exists as a technique:
   **LLMLingua-2** is a small trained model that classifies which tokens to drop, at
   2-5x compression and up to 2,9x lower latency; the original LLMLingua reports up
   to 20x with minimal degradation.

Caveat that reorders the list: our cost is **generation**, not prompt. Prompt work
attacks the ~27 s of a call, not the ~107 s. Compression is third for that reason.

### Two findings that touch decisions already made

- **ADR 0017's structure-aware chunking is vindicated by outside work.** A study
  chunking the German Civil Code compared structural units against fixed windows,
  semantic clustering and RAPTOR: chunking aligned with the legal structure gives the
  **highest recall**, and cleverer schemes that override it do worse, because those
  boundaries were drawn by the lawmaker to delimit regulatory matter. That is the
  argument ADR 0017 made from first principles.
- **Retrieval would import a hallucination class we do not have.** Stanford's
  empirical study found Lexis+ AI and Westlaw's AI research tools hallucinate
  **17-33%** of the time; citation accuracy is the worst-performing task family across
  frontier models at 12,4%. Grounding cuts hallucination 75-90% and is explicitly not
  a cure. Today leyllana **cannot** invent a norm, because it only ever sees the one
  it was given (ADR 0008). A corpus and an index spend that property. This is the same
  objection already recorded under *Deliberately deferred*, now with numbers.

### Feasibility, if it is ever built

- Fully offline is realistic: `sqlite-vec` gives vector search in one file with no
  server, embeddings can come from llama.cpp's own endpoint, and `bge-m3`,
  `multilingual-e5` and `jina-v3` all cover Spanish.
- **Keywords alone may be enough for a v1.** In a controlled ablation on legal passage
  retrieval, dense retrieval beat BM25 by **0,3 percentage points**; hybrid beats
  either by 10-30%. BM25 needs no embedding model and no second GGUF.
- The corpus is published: `datos.bcn.cl` serves Ley Chile as open linked data with a
  SPARQL endpoint and a *normas* dataset. **The ~21.000 figure is unverified** — the
  total was not confirmed, and it should be counted before being quoted.
- For the low-RAM slot that emitted fiction twice: **LegalDrill** distills legal
  reasoning into small models and reports Qwen3-1.7B reaching near-teacher performance
  against a Qwen3-30B teacher. A lead, not a plan.

### Still to research: progressive display

The second half of the question, not yet done: how to show something readable while a
long run is still going, given that the map calls produce grounded bullet notes rather
than the four sections. The seam exists (`on_token`, ADR 0020, unused by the GUI). The
hazard is that a partial list reads as the answer — someone seeing notes from fragment
3 of 14 has no way to know the sanctions appear in fragment 13.

## Found while measuring item 6, 2026-07-29
**Status: recorded, nothing fixed, no decision taken**

Three findings that were not the object of the measurement. None is fixed; each
would need its own decision.

- **A plausible BCN URL silently fetches an error page instead of the law.**
  `_bcn_id_norma` (`input/url.py`) only recognises an `idNorma` query key, but BCN
  itself also serves `?i=1202434`. That form misses the XML path, falls through to
  the generic HTML scraper, and yields **189 characters** of
  *"Este proceso demora demasiado, es probable que su conexion este muy lenta o que
  su navegador no sea compatible"* against 99.468 for the same law, with no title.
  `validate_text` passes it, because `_MIN_USABLE_CHARS = 20`. FR-1.1 promises to
  detect incomplete extraction and warn; this is that case and it is not detected.
  - **The guardrail catches what the input layer missed, and this was verified end
    to end.** Run on those 189 characters the tool answers *"No hay una norma o ley
    explicada en el texto proporcionado"* and puts the exact
    *"No se puede determinar a partir del texto entregado."* string in two sections.
    It invents nothing. So the consequence is a confusing run, not a false
    explanation — ADR 0008 doing its job on a degenerate input.
- **Digits-for-words weakens the traceability of FR-6.1 / ADR 0014.** The source
  writes `tres horas` and `setenta y dos horas`; the output writes `3 horas` and
  `72 horas`. Both are faithful in substance, but ADR 0014 requires the identifier
  *as it appears* precisely so a reader can text-match it against the source, and a
  reader searching the law for "3 horas" finds nothing. Found by trying to verify
  the citations by text match and failing on the first attempt.
- **An oversized prompt fails loudly, which is better than feared.** At
  `_MAX_REDUCE_DEPTH` (`engine/__init__.py`) `_condense` returns the pooled points
  without re-checking that they fit. That looked like a silent-truncation risk, but
  `llama-server` rejects an oversized request with HTTP 400
  (`exceed_context_size_error`, `truncated = 0`) rather than quietly cutting it, so
  the failure surfaces as a `ProviderError` instead of a plausible wrong answer.

## The binary in `backend/bin` is a CPU-only build. Found 2026-07-29
**Status: recorded, nothing changed**

**The GPU has never been used by this project, on any run.** `backend/bin` contains
no `ggml-cuda.dll`, no `ggml-vulkan.dll`, no GPU backend of any kind, and
`llama-server --list-devices` (build b9929) prints an empty list. Meanwhile
`engine.gpu = "auto"` resolves through `resolve_gpu_layers`, which probes for
`nvidia-smi`, finds it, and passes `-ngl 999` into a binary that cannot honour it.
No error, no warning: the config claims a GPU path that does not exist. ADR 0012's
optional-GPU promise is currently unimplementable with what we ship.

Every figure previously recorded in this file as "GPU" was produced on the CPU.

A GPU-capable build already exists on this machine, shipped by Docker Model Runner
(`~/.docker/bin/inference`, with `ggml-vulkan.dll`); it reports
`Vulkan0: NVIDIA GeForce RTX 2050 (3962 MiB, 3367 MiB free)`. Same model, same
prompt, same `ctx`:

| | shipped build (CPU-only) | Vulkan build |
|---|---|---|
| Prompt processing, 2152 tok | 84,7 tok/s | **1278,1 tok/s** |
| Generation | 11,4 tok/s | **35,3 tok/s** |

The Vulkan build pays a one-time shader-pipeline compilation on its first run
(~27 s, measured cold then warm); after that it is warm. Official llama.cpp Windows
prebuilts have shipped CUDA, Vulkan, HIP and SYCL variants since b9196, so this is a
download rather than a compile, and llama.cpp issue #24744 records that `llama
update` on Windows can silently replace a CUDA build with a Vulkan or CPU one, which
is a plausible account of how `backend/bin` ended up this way.

**Nothing has been swapped.** Which backend leyllana ships is an ADR 0012 / ADR 0016
decision, and it reaches the Phase 4 installer.

## Local model options — research findings, 2026-07-29
**Status: recorded, nothing decided**

Written down because these findings kept getting lost across a long session. None
of this changes ADR 0015 yet; **no model has been swapped, and nothing here is
adopted.** Any change needs its own ADR and a faithfulness test on a real norm.

### Measured on this machine, not estimated

| | shipped CPU build | Vulkan build |
|---|---|---|
| One map fragment, Qwen3-4B Q4_K_M | **134 s** mean over 27 calls | **57 s** mean over 25 calls |
| ~100k chars at `ctx = 4096` | **59,6 min** (measured end to end) | **22,9 min** (measured end to end) |
| ~100k chars at `ctx = 16384`, `q8_0` KV | not run (needs a config key for `-ctk`) | **4,8 min** (measured end to end) |

The CPU figure is the **as-shipped baseline**, measured 2026-07-29 in the GUI with
nothing changed, on Ley 21.663 as a PDF from the desktop (103.666 caracteres after
extraction, slightly more than the 99.468 the BCN XML gives): **59,6 min in 28 model
calls**, with rounds of `14 -> 7 -> 4 -> 2` fragments. It used all three levels of
reduction that `_MAX_REDUCE_DEPTH` allows. This is what a user gets today, and it is
the number that replaces the previously mislabelled one.

Note how little the reduction reduces: 14 fragments condense to 7, then to 4, then to
2. Each round costs nearly as much as the one before, which is how a single law
becomes 28 calls. The rounds, not the law, are the cost.

Cold start adds ~3 s over a warm call, so the cost is almost entirely generation and
is roughly linear in `calls × max_tokens`. **A laptop without a GPU is the real
target** and, on the numbers above, has no configuration that brings a long norm
under ten minutes.

An earlier `~2 min` figure appeared in this table attributed to this law. **Explained
2026-07-29 by the first run through the new diagnostics** (`leyllana.diagnostics`):
it was a different norm. Ley 21.828 as a PDF is **3.239 caracteres**, thirty times
smaller, so it fits `ctx 4096` in a single pass with **zero map calls** and finishes
in **50,3 s** on the CPU build. Nothing was wrong with either number; they are
different documents.

Which is the whole lesson of this section: **the cost of a run is the number of model
calls, not the size of the document**, and a figure recorded without the document
size and call count beside it cannot be compared to anything. That is why the run
record now writes both.

### The cheapest lever is our own config, not a new model

`ctx = 4096` in `leyllana.toml` is what splits a 99k-character law into 13
sequential passes, and then into 25 model calls once hierarchical reduction fires.
The default model is **Qwen3-4B-Instruct-2507, whose native context is 262.144
tokens**, so 4096 is 1/64 of what it supports and is not a property of the model.
**Now measured, see item 6 of the queue:** on the Vulkan build, `ctx 16384` with
`q8_0` KV cuts the run 4,8x and improves the reading; on CPU the lever is dead. The
whole law is 24.905 real tokens, so a single pass needs `ctx >= 26k`, which does not
fit a 4 GiB card at any KV quantization — and the research below argues against
wanting it anyway.

### Against chasing a single pass, on faithfulness grounds

This file previously assumed that fewer fragments would mean fewer artefacts, so a
single pass over the whole law would be the faithful ideal. **The published evidence
points the other way**, which matters more here than the timing does.

Long-context models show a U-shaped positional bias — the "lost in the middle"
effect — where accuracy is highest for material at the start and end of the context
and degrades by more than 30% for material in the middle, driven by RoPE long-term
decay reducing attention to distant token pairs. A comparative study of chunked
map-reduce against stuffing the whole document found the map approach **at least as
accurate**, and specifically better at retaining facts from the beginning and middle
of the text.

For a 55-article law that is the whole ballgame: a single pass puts the middle of the
articulado exactly where models drop things. **So ADR 0017's chunking is defensible
on faithfulness grounds and not merely a workaround for a small context**, and the
lost article identifier of Phase 1 is a reduce-prompt problem to fix in the prompt,
not an argument for abandoning chunking. The measured runs are consistent with the
positional story: at `ctx 4096` (25 calls, three reduction levels) the output cited
Articulos 4, 5, 39 and 40 — the two ends — while at `ctx 16384` (2 calls, no
reduction) it cited 4, 7, 8, 9, 10 and 24, a contiguous run through the obligations
block, and dropped the sanctions at the end. Fewer calls read more deeply but not
more widely.

### Latin-America-centric candidates

- **Latam-GPT** — CENIA (Chile), launched Feb 2026, 15 countries and 60+
  institutions, ~8 TB Spanish/Portuguese, Llama 3.1 architecture so llama.cpp
  compatible, built for about USD 550.000. The obvious fit for this project's
  politics. **Not verified: whether weights or a GGUF are actually published**, or
  at what parameter count. That check is step one.
- **Salamandra** (BSC-LT, Barcelona) — 2B / 7B / 40B, Apache 2.0, **official GGUF
  published by BSC-LT**. Reported best QA accuracy across all languages in one
  comparative study of Iberian-language tasks. Spain-centric, not Chilean.
- **ALIA-es-legal-7B-Instruct** (SINAI) — Salamandra-7B continued-pretrained on
  Spain's BOE and Congreso, then instruction-tuned. The only candidate trained on
  this register; its instincts are Spanish, not Chilean.
- **MEL** (UPM) — legal-Spanish model built on XLM-RoBERTa. Encoder-only, so it
  cannot produce our four sections. Ruled out for this task.

### Small / low-RAM candidates

The slot matters because Phase 1 measured the shipped fallback (Qwen3-1.7B)
producing **confident fiction** on a long norm, twice, exiting 0 both times.

- **LFM2 / LFM2.5-1.2B-Instruct** (Liquid AI) — official GGUF, built for
  on-device, reported higher CPU throughput than Gemma-3-4B, Granite Micro,
  SmolLM3-3B and Llama-3.2-3B. Spanish is a supported language, but the
  pre-training mix is ~75% English.
- **Gemma 3 1B / 4B** — official `ggml-org` GGUF, 140+ languages, **32k context on
  the 1B and 128k on the others**. The long context is the interesting part here,
  not the speed.
- **Phi-4 Mini 3.8B** (~12 tok/s on a modern i7, CPU-only) and **Llama 3.2 3B**
  (25-45 tok/s on an 8-core laptop CPU) as reference points.

### How to choose instead of guessing

- **La Leaderboard** (BSC + UPM + HuggingFace) — 66 datasets over Spanish
  varieties **including Chilean**, 50 models scored, Apache 2.0.
- **BOE-XSUM** — 3.648 extreme summaries in clear language of Spanish official
  decrees. The closest published analogue to what leyllana does, usable as an eval
  set despite being Spain's BOE.

### What a Chilean technical reading contains (fed the `nivel` fix, `afac933`)

Research behind the `nivel` rework. BCN already publishes both of our registers:
**Ley Fácil** (since 2003, OECD-cited, RAE calls it pioneering in Hispanoamérica)
targets *requisitos para acceder a un beneficio, conductas tipificadas y sus
penas, obligaciones a las que se está sujeto*. **Asesoría Técnica Parlamentaria**
exists to *"reducir la asimetría de información con el Poder Ejecutivo"* and
leans on the *cuadro comparativo* (vigente vs. propuesto) plus *observaciones
sobre técnica legislativa*.

Elements a technical reading surfaces, all verified: tipo de ley y quórum (LOC
4/7, calificado, simple); ámbito de aplicación y definiciones (usually Artículo
1°); sujetos obligados and from when they are bound (Ley 21.663's OIV only on an
*ejecutoriada* calificación); plazos in días hábiles per Ley 19.880 (cómputo from
the following day, prórroga to the next business day); multas in UTM by tier;
the fiscalising organ and its facultades; reclamación de ilegalidad and its
plazo; remisión normativa to a reglamento de ejecución; entrada en vigencia and
disposiciones transitorias (Código Civil arts. 6-7); and what the norm modifica,
sustituye, intercala or deroga, referenced against the base text.

## Retrieval layer scope — verified corpus size and architecture research, 2026-07-30
**Status: recorded, nothing decided**

Follow-up to the corpus retrieval section above. A brainstorming session narrowed
the retrieval layer's actual purpose: not general Q&A over all of Chilean law, but
a new reader figure — *dirigente* (any kind: vecinal, sindical, partidario,
deportivo, of an NGO) and *autoridad comunal* (alcalde / municipal team) — asking
how a specific law affects them, which needs context the source law does not
contain (municipal competencies, who fiscalizes, obligations on their kind of
organization). That reframes the open question from "index the corpus" to
"how big is the slice that actually matters, and how should it be fetched."
**Nothing here is adopted and no ADR changes.**

### The corpus is verified, and much bigger than assumed

Queried BCN's own SPARQL endpoint directly (`bcnnorms:Norm`, grouped by
`bcnnorms:type`): **748.783** norms of every kind. Of those, **Ley** alone is
**35.574**; **Ley + Decreto Ley + Decreto con Fuerza de Ley** (the three types
that carry force of law) is **53.215**. Felipe's original estimate of ~21.000 was
off by 1,7x to 35x depending on where the cut is drawn. The remainder is mostly
`Decreto` (358.352) and `Resolución` (310.902) — administrative acts, not
statutes.

**BCN's own linked data has no *vigencia* (in-force / repealed) field at all.**
The `bcn-norms` ontology defines type, dates, numbering, and modification
relationships, but nothing marking a norm current or superseded. A paper in the
IFLA repository, from someone working with this same dataset, names this
directly: *"the coexistence between current and repealed norms... there are no
elements that clearly identify their status."* An attempt to get a real vigente
count by querying leychile.cl's own vigencia filter failed — it hit the same
189-character malformed-URL error page already documented above, so that number
stays unverified rather than guessed.

### What the field does instead of indexing everything, researched in English

- **Two-stage retrieval — cheap metadata filter first, fetch/embed only the
  shortlisted full text — is an established production pattern**, not a shortcut.
  It is explicitly recommended over re-embedding a whole corpus on every change,
  and metadata pre-filtering (date range, type) before similarity search is a
  named technique for narrowing the candidate set before the expensive step.
- **Bulk index-time RAG has a cost the field tracks by name: the staleness gap**,
  the time between a source changing and the reindex catching up. For corpora in
  the tens-of-thousands-to-millions-of-chunks range, embedding compute is called
  out as the dominant cost. Neither of those problems shows up if only a
  shortlisted handful of documents ever get embedded.
- **A curated legal corpus (constitution, codes, landmark rulings) is itself a
  real, used pattern in production legal-RAG systems**, not an ad hoc
  simplification — reported as a standard way to scope a legal knowledge base.
- **Sparse (keyword) retrieval is called out as mattering more than dense
  specifically for legal vocabulary and exact-phrase matching**, which lines up
  with the BM25-vs-dense gap already measured (0,3 percentage points, recorded
  above).
- **Temporal validity is a named hard problem in legal RAG, and the field's
  answer is date-bounded scoping as a hard constraint**: extract an as-of date
  and filter the corpus to that validity period, because "was this provision
  valid on this date" is treated as a first-class question, not an edge case.
  That is the same gap BCN's own data leaves open — no vigencia field — so
  filtering by date is not a workaround here, it is what the literature already
  does for exactly this absence.
- **CPU embedding is cheap at this scale.** Lightweight encoders (MiniLM-class)
  embed thousands of short documents per second on CPU; the cost that would
  actually bite is fetching and storing 53.215 full documents up front, not
  embedding their titles or metadata.

### Where this leaves the architecture question

Downloading and indexing all 53.215 (or 748.783) norms up front is not what
production legal-RAG systems do for this class of problem, on the evidence above.
The shape the research points to combines two things validated separately: a
two-stage design (a small local metadata index — title, type, organism, dates —
used to shortlist candidates with no data leaving the machine, then the actual
text of only those few fetched on demand through the `input` layer leyllana
already has) with date-bounded filtering standing in for the vigencia field BCN
does not provide. Still Felipe's decision, still needs its own ADR once decided;
recorded here so the numbers and the sources are not re-derived next session.

### Corpus scope corrected to Ley only, and measured, 2026-07-30

Felipe corrected the scope: leyllana explains **leyes**. Decreto Ley, Decreto
con Fuerza de Ley, and every other norma type are referenced, never indexed or
explained. Two things followed from that, both verified rather than estimated:

- **35.574 is version records, not distinct laws.** BCN re-publishes a new
  dated record of a Ley every time it is amended (`.../20848`,
  `.../20848/es@2015-01-01`, `.../20848/es@2222-02-02` are the same law, three
  versions). Counted distinct base identifiers via SPARQL: **16.064** current-
  form Leyes.
- **Measured document size on 34 real fetches** from `leychile.cl` (a
  randomized SPARQL sample, flagged because the distribution is extremely
  heavy-tailed — a 677 KB omnibus law and a cluster of ~1,2 KB reserved/stub
  laws turned up in the same sample): trimmed-mean **13,5 KB raw XML/law**
  (range across estimators: 4,2–48,6 KB). Extrapolated over 16.064 laws: **~0,22
  GB raw text** (range 0,07–0,78 GB). Measured the XML-to-plain-text ratio on
  one document (0,73) and applied the project's own 3,5 chars/token
  (`engine/chunking.py`): **~45 million tokens** total (range 14M–163M).

**This corrects the "multi-gigabyte" line in the section above** — that was
sized against the bigger Ley+DL+DFL/53.215 universe this section has since
narrowed away from. At Ley-only scope, the corpus is small enough that
bulk-indexing everything is no longer ruled out by size. What is still
unmeasured, and is the real reason the design spec keeps the two-stage
architecture rather than switching to bulk indexing on this data alone: actual
embedding throughput on this machine for full-length legal text (published
short-sentence-encoder throughput figures do not transfer), the ~2–4,5 hour
one-time ingestion cost against a public agency's service at a polite request
rate, and the staleness problem — no vigencia field means every refresh has to
re-check the whole set rather than only what changed.

Two ideas raised alongside this and explicitly deferred, not designed: a
corpus-storage compression algorithm (LLMLingua-2-style, already a lead in the
section above), and using retrieval to feed the low-RAM Qwen3-1.7B fallback
only the most relevant passages instead of the whole document. The second one
is not a small addition — it would apply to the base `explain()` path for every
reader, not just the new retrieval figures, and it reopens ADR 0017's
specific, reasoned call that there is no query in the explain task. Recorded
here so it is not lost, not folded into the current spec.

## Low-RAM, no-GPU target: first real measurement, 2026-07-30
**Status: recorded, nothing decided, contradicts a prior finding**

Felipe redirected priority: everything measured so far ran on the dev machine
(16 GB RAM, an unused GPU per ADR 0023). The PRD already names "a laptop
without a GPU" as the real target (section 6, non-functional requirements),
but nothing had actually been measured on that profile. This is the first
attempt, and it produced a result that needs to be flagged loudly rather than
quietly filed as good news.

### Test environment

A dedicated WSL2 Debian distro, installed alongside the existing WSL1 Kali
distro (untouched, not converted, not affected by any of this). `.wslconfig`
caps memory at 8 GB and processors at 4 (the core count was not specified by
Felipe — picked as a reasonable low-end assumption, flagged here rather than
silently baked in). `llama-server` built from source at the official tag
**b10184** (`GGML_CUDA=OFF`, `GGML_VULKAN=OFF`; `--list-devices` confirms
`(none)`) because llama.cpp does not publish a generic Linux prebuilt in
releases, only Windows/macOS. `nvidia-smi` is technically visible inside WSL2
(Windows injects GPU-passthrough infrastructure at the host level, not
something a distro can opt out of), but this does not compromise the test: the
binary has no GPU backend compiled in at all, so it cannot use a GPU regardless
of what `nvidia-smi` reports — the same shape of fact ADR 0023 already
established for the Windows CPU-only build.

### The measurement: full `explain()`, Qwen3-1.7B, same document as every other figure in this file

Ran the actual `tools/measure_run.py` against the same Ley 21.663 XML fetch
(99.468 characters) already used throughout this ROADMAP, through the real
`LocalProvider`/`explain()` code path (not a synthetic call) — same `--jinja`
and `enable_thinking: False` production behaviour, `ctx = 4096`,
`max_tokens = 1024`, `temperature = 0,2`, `gpu = "auto"`. Run twice, back to
back:

| run | total | map calls | faithful? |
|---|---|---|---|
| 1 | 586,3 s (9,8 min) | 13 (no reduction round needed) | yes, spot-checked |
| 2 | 594,6 s (9,9 min) | 13 (no reduction round needed) | yes, spot-checked |

Both runs stayed comfortably inside the 8 GB cap (idle+one-call RSS measured
separately at ~2,4 GB; neither run OOM'd or was killed). Both cited the same
claim — "la calificación... se revisa cada tres años" — and it is real,
verified against the source: `Artículo 6º` says exactly that ("Al menos cada
tres años, la Agencia deberá revisar y actualizar la calificación..."). Neither
run invented anything checked.

### This contradicts Phase 1's finding, and that gap is not resolved

Phase 1 (recorded above, "El fallback de baja RAM... inventa en normas
largas") ran this same model on this same law, also 13 fragments, also this
ctx, and got **complete fabrication twice** — an invented junta-de-vecinos law
once, an invented tax law the second time, both exiting cleanly. Two clean runs
here versus two fabricated runs there, on what should be a comparable setup, is
too large a gap to file as "the model is fine now." The most concrete lead:
**the Windows production binary is build b9929; this WSL2 binary is b10184** —
roughly 255 releases apart, plenty of room for a sampling, chat-template, or
quantization-kernel change that affects this exact model+quantization
combination. Not confirmed. Platform (Windows vs. Linux) and the RAM/CPU cap
are also unruled-out variables. **Do not treat the low-RAM model as
rehabilitated on this evidence** — Phase 1's finding stands until this
discrepancy is actually explained, not just noticed.

### A second, separate gap found in both runs: no article numbers at all

FR-6.1/ADR 0014 requires every named article to appear verbatim so a reader can
spot-check it. Both runs' "Artículos clave" section describes Artículo 6's
content accurately but **never writes "Artículo 6" or any article number** —
contrast the Windows Qwen3-4B CPU runs, which did cite specific articles (4,
5, 39, 40) even when sparse. This is a different failure shape than
fabrication: the content is faithful, but the traceability the section exists
to provide is missing. Not fixed, not designed here.

### Follow-up, same day: the build-version hypothesis does not survive testing

Tried to isolate the b9929-vs-b10184 lead directly. Building b9929 from source
inside WSL2 hit an unrelated, genuinely broken web-UI asset-bundling step in
that historical release (`llama-ui-embed` rejecting the HF-hosted UI bundle
for missing files, then rejecting hand-made placeholders for a different,
dynamically-hashed set) — abandoned as a dead end unconnected to this
question, not worth chasing further.

Switched to a cleaner test: run the **exact existing binaries natively on
Windows**, no WSL, no RAM cap, nothing else changed.

| binary | platform | result |
|---|---|---|
| b9929 (`backend/bin`, same one Phase 1 used) | Windows native | **vacuous** — well-formed sections, zero real content ("los sujetos mencionados en el texto"), 3,4 min, matching Phase 1's recorded ~3 min almost exactly |
| b10184 (official Windows CPU prebuilt, fresh download) | Windows native | **fabricated a different law entirely** — invented a data-protection/e-commerce statute with five fake article citations, 3,1 min |

Combined with the two faithful WSL2 runs on b10184 above, that is **four
outcomes across four attempts, no two alike, and they do not split cleanly by
build version or by platform**: the same b10184 binary was faithful twice on
WSL2 and fabricated once on native Windows. **The build-version hypothesis
does not hold up — something else is driving this, unidentified.** Candidates
not yet ruled out: genuine run-to-run variance (`temperature = 0,2`, not
deterministic), floating-point/quantization-kernel differences between the
Linux (GCC) and Windows (MSVC/Clang) builds, or something in how `threads = 0`
resolves differently per platform. This reframes the finding: it is not "the
low-RAM model needs a newer binary," it is **"the low-RAM model's
faithfulness is not currently predictable run to run, on any binary tested
so far."** That is a more serious problem than the one this thread started
investigating, not a smaller one.

### Not yet done

Only one model (Qwen3-1.7B), one ctx (4096), one document, and now four
inconsistent outcomes instead of an explained gap. Qwen3-4B under the same
8 GB cap, other ctx values, a larger batch of repeated runs to characterize
how often this model is faithful versus not (four runs is not enough to
quote a rate), and actually explaining the variance are all still open.
Felipe asked for this to become an ADR whose results steer the rest of the
ADRs; per the project's rule that no ADR gets written without his decision
first, the measurement is recorded here and the ADR itself waits on that
conversation — and on the evidence above, that ADR's central question may
now be "is Qwen3-1.7B usable as a fallback at all," not "which binary to
ship."

## Gemma 3 1B tried as a replacement for the low-RAM slot, 2026-07-30
**Status: recorded, first attempt failed, nothing decided**

Given the low-RAM model's faithfulness looked unpredictable rather than fixable
(section above), tried the candidate ROADMAP had already researched: Gemma 3 1B
(`ggml-org/gemma-3-1b-it-GGUF`, `Q4_K_M`), same document, same `ctx = 4096`,
b10184 native Windows.

**Failed outright, not on faithfulness — on output format.** The response never
produced the required "en una frase" section, so `explain()`'s own parser
correctly rejected it (`ParseError: La respuesta del modelo no trae las
secciones: en una frase`) rather than passing through malformed output. Also
needed 18 map calls (two hierarchical reduction rounds Qwen3-1.7B never
triggered) and took 6,9 min — slower than Qwen3-1.7B's ~3 min on the same
binary. One attempt, not repeated; the raw failed response was not captured
(`measure_run.py` only saves the parsed result, which does not exist on this
kind of failure). Nothing concluded about Gemma 3 1B from a single failed run
beyond "the current prompt/output contract does not reliably work with it
out of the box."

## Low-RAM fallback: decided, 2026-07-30 — Gemma 3 1B replaces Qwen3-1.7B
**Status: Decided (ADR 0024, ADR 0025), implementation not started**

Felipe reviewed the alternatives above (characterize further / retrieval-scoped
input for the existing model / replace the model / drop the slot) and chose to
replace the model. Between the small candidates, Gemma 3 1B was picked for its
verified Spanish/multilingual pretraining strength, over Phi-4 Mini (MIT-clean
license, but untested for Spanish or faithfulness) and LFM2 (a ~75% English
pretraining mix, and a USD 10M-revenue license cap that isn't strictly OSI
either). Gemma's license is not OSI-permissive and is remotely revocable by
Google — the same bar ADR 0015 rejected Gemma-2-4B on — so this needed its own
decision: **ADR 0024** waives that bar for the fallback slot only, scoped to
Felipe's own estimate of this tool's expected use (a small pilot, on the order
of ten users within the party); the default model (Qwen3-4B, Apache 2.0) keeps
the bar unchanged. **ADR 0025** records the model swap itself.

**This is a decision, not a validated fix.** Gemma 3 1B's only prior attempt
(recorded above, 2026-07-30) failed on the output contract before faithfulness
could even be assessed. Before this can ship: fix the output-contract failure,
then run the same faithfulness battery Qwen3-1.7B was subjected to. Qwen3-1.7B's
measured fabrication (Phase 1, and the four inconsistent 2026-07-30 runs above)
is not retracted by this decision — it is the reason a replacement was sought.

## Phase 4 — Packaging and pilot
**Status: Not Started**

Ship something a non-technical user can install and run, then test it on real
*boletines* with real readers.

- Windows installer bundling the app + default model.
- **Distribution site: `leyllana.cl`.** Landing/download page for the Windows installer
  once it exists above; redirects from there to a separate site Felipe is building for his
  own website/software-creation services (a distinct business, not part of leyllana or GDS).
  The download site needs a fake, non-functional demo of the Windows GUI — leyllana is a
  desktop app, not a web app, so it can't be tried live in a browser; visitors get a mocked
  walkthrough of what running it looks like before downloading. Not started; the installer
  above has to exist first for a download page to make sense.
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
