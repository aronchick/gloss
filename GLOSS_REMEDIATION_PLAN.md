# Gloss v1 — Detailed Remediation Plan

> **Historical and superseded.** This plan describes the retired April draft deck. The draft is
> recoverable from git history at `7f66d66`; it is intentionally absent from the release tree. The
> only current gold is `gloss-v1/benchmark/deck/gold/gloss-v1-gold.pptx`.

Goal: take `gloss-v1/Gloss_v1.pptx` (currently auto-failing) and produce a fully conformant Gloss v1 gold deck + benchmark package per `GLOSS_OPENSPEC.md`.

> **Key insight**: the spec treats the `.pptx` as only ~5% of the package — most of the work is the *surrounding* artifacts (prompts, checklist YAML, manifests, fixtures, baselines). Fixing the deck without fixing the package still leaves you ungradeable.
>
> "LibreOffice-authored" isn't aesthetic preference — it's because `docProps/app.xml` and per-slide serialization differ between PowerPoint and LibreOffice, which changes byte-exact image hashes, font runs, and auto-corrected XML. Re-saving in LO is not enough; the deck must be *rebuilt* there.

This plan is ordered so each phase unblocks the next. Do not skip ahead — several phases produce outputs later phases depend on (e.g., prompts must exist before authoring the gold; the gold must exist before exporting references; references must exist before writing checklist items).

---

## Current state (baseline)

From the conformance audit of `Gloss_v1.pptx`:

**Structural positives (~60–70% of §14 matrix present)**
- 20 slides, 16:9, valid OOXML
- Native charts on slides 4/13/20 (with embedded xlsx)
- Native tables on slides 3/13/20
- Real Arabic (RTL) + Japanese (CJK) runs, rotated text, 3 embedded images

**Auto-fail issues**
1. **Non-bundled fonts** — slides reference Arial, Courier New, Aptos. Spec §4.3 allows only Noto / Liberation / Carlito / Caladea. Auto-fail.
2. **Authored in PowerPoint, not LibreOffice Impress** — `docProps/app.xml` = "Microsoft Macintosh PowerPoint", revision 311. Violates §13.1.
3. **Notes slide present** (`ppt/notesSlides/notesSlide1.xml`) — §2.3/§13.3 forbid notes in v1.
4. **Placeholder discipline thin** — only 1 `<p:ph>` per slide (title); body content is freestanding text boxes, violating §5.2.
5. **Package is orphaned** — no `benchmark/deck/gold/gloss-v1-gold.pptx`, `benchmark/checklist/slides/` is empty, no `prompts/`, `assets/manifest.json`, `fonts/manifest.json`, `fixtures/`, or `baselines/`. The grader literally can't run against it.

**Smaller gaps**
- 5 slides (7, 8, 9, 11, 20) still titled literal "PowerPoint Presentation"
- Repeated brand marks likely per-slide instead of master-driven (fails slide 5's master-reuse test)

---

## Phase 0 — Environment freeze (do once, before touching anything)

Goal: a deterministic, bit-reproducible authoring + grading environment. §9.4, §9.7.

1. **Build the canonical Docker image** from `gloss-v1/Dockerfile` (verify it matches §9.7 exactly: `ubuntu:22.04`, `libreoffice-impress`, `libreoffice-core`, `fonts-liberation`, `fonts-noto`, `fonts-noto-cjk`, `fonts-crosextra-carlito`, `fonts-crosextra-caladea`, and *nothing else font-wise*).
   ```bash
   docker build -t gloss-v1-env gloss-v1/
   ```
2. **Pin the LibreOffice build string**. Inside the container: `libreoffice --version` → record exact build (e.g., `LibreOffice 7.6.4.1 40(Build:1)`) into `gloss-v1/environment/libreoffice-version.md`.
3. **Pin the Docker image digest**:
   ```bash
   docker inspect --format='{{index .RepoDigests 0}}' gloss-v1-env
   ```
   Record in `environment/docker-image.md`.
4. **Set locale + timezone** in any authoring/grading shell: `LANG=en_US.UTF-8`, `TZ=UTC`. Reference datetime for fields is `2025-01-01T00:00:00Z` (§9.4).
5. **Authoring machine**: install **LibreOffice Impress** locally *and* the exact same four font packages. Nothing else. Remove (or at minimum, do not allow Impress to fall back to) Arial, Calibri, Aptos, Courier New, Helvetica, Times New Roman, system fonts. This is the single most common cause of the current auto-fail.
   - On macOS: LibreOffice will pick up system fonts from `/Library/Fonts` and `~/Library/Fonts`. Either author inside the Docker image (preferred) with a mounted volume, or use LibreOffice's `Tools → Options → LibreOffice → Fonts → Replacement Table` to force-map:
     - Arial → Liberation Sans
     - Calibri → Carlito
     - Cambria → Caladea
     - Times / Times New Roman → Liberation Serif
     - Courier New → Liberation Mono
     - Aptos → Carlito
   - Then check `Always → On`. Verify no non-bundled font name appears in any slide's font table when done.

**Checkpoint**: open a throwaway `.pptx` in LibreOffice on your authoring machine, type text in "Calibri", save, unzip, grep the XML. It should say `Carlito`, not `Calibri`. If it still says `Calibri`, stop — the font replacement isn't active, and the gold deck will auto-fail the same way the current one does.

---

## Phase 1 — Prompts first (§13.1 step 1–2)

The spec is explicit: prompts are the *primary artifact*, not the deck. You write prompts, validate them independently, *then* build the gold.

1. **Write `benchmark/prompts/deck.md`** — deck-level prompt. Must cover: global design system, color palette, typography hierarchy (using only Carlito / Caladea / Liberation / Noto), master/layout expectations, cross-slide consistency, 16:9, locale, reference datetime, asset policy.

2. **Write `benchmark/prompts/variants/canonical/slide-01.md` … `slide-20.md`** — one prompt per slide, each covering the constructs listed in §14 for that slide:
   - S1 cover stress test
   - S2 dense agenda
   - S3 native table
   - S4 native chart
   - S5 master reuse
   - S6 multilingual EN+AR RTL+JA
   - S7 image crop/mask
   - S8 overlap+shadow
   - S9 dense text overflow
   - S10 connectors
   - S11 theme vs local override
   - S12 native fields
   - S13 composite
   - S14 RTL-heavy
   - S15 rotated text
   - S16 off-canvas bleed
   - S17 deep grouping
   - S18 multi-column editorial
   - S19 repetition + internal-only hyperlinks
   - S20 final torture

   Each prompt must be **unambiguous, complete, no hidden constraints** (§8.1).

3. **Write paraphrases**: `variants/paraphrase-a/slide-NN.md` and `variants/paraphrase-b/slide-NN.md`. Same semantic content, different wording.

4. **Independent author convergence check** (§13.1 step 2): have 2–3 people (or 2–3 clean-context LLM runs) author each slide from prompt alone, in LibreOffice with bundled fonts only. Run the grader's structural comparator pairwise. Any slide where no pair hits ≥80% structural similarity → prompt is underspecified, revise and re-run. Archive results under `benchmark/prompts/validation/slide-NN.md`.

**Do not proceed to Phase 2 until every slide prompt has passed convergence.**

---

## Phase 2 — Asset and font manifests (§8.3, §7)

Before you author the deck, the allowed assets and fonts must be pinned.

1. `benchmark/assets/manifest.json` — one entry per allowed image:
   ```json
   {
     "assets": [
       {
         "asset_id": "hero-01",
         "source_url": "https://...",
         "local_path": "mirrored/hero-01.png",
         "sha256": "<sha256 of original file>",
         "accepted_recompression_hashes": [],
         "usage": "slide-01 hero image"
       }
     ]
   }
   ```
   Mirror each file to `benchmark/assets/mirrored/`. Compute SHA-256 with `shasum -a 256`.

2. `benchmark/fonts/manifest.json` — list Noto, Liberation, Carlito, Caladea with the exact Debian/Ubuntu package versions from the pinned Docker image. Copy the font files to `benchmark/fonts/files/` and the licenses to `benchmark/fonts/LICENSE`.

3. `benchmark/tiers/level-{1,2,3}/slides.json` — which slide numbers each tier includes:
   - L1: `[1,2,3,4,5]`
   - L2: L1 + `[6,7,8,9,10,11,12]`
   - L3: L2 + `[13,14,15,16,17,18,19,20]`

   Per §6.1.

---

## Phase 3 — Rebuild the gold deck in LibreOffice Impress (§13.1 step 3)

> **Do not re-save `Gloss_v1.pptx`. Do not edit it in LibreOffice and call it fixed.** Open-save round-trips in LO on a PowerPoint-authored file leave residue (notes parts, Aptos font references in theme, PowerPoint-specific extension lists, `app.xml` application name) that the grader will catch. Start a **new** Impress document.

Authoring rules (derived from §3, §4.3, §5.1, §5.2, §13.3, §14, §20, §21):

### 3.1 Document setup
- New Impress file, blank. `Slide → Slide Properties → Page Size`: 25.4 × 14.288 cm (16:9, matches 12192000 × 6858000 EMU). Landscape.
- `Tools → Options → Load/Save → General`: default format = *PowerPoint 2007–365 (.pptx)*. Always save as pptx, never ODP.
- `File → Properties`: set title, author, subject. **Remove any trailing "PowerPoint Presentation" default titles.**

### 3.2 Master and layouts (§20)
- Edit the **Slide Master** (`View → Master Slide`). Put everything that repeats deck-wide into the master: brand marks, footer, page-number field, base title placeholder, base body placeholder. If the current deck's "GLOSS" and slide numbers appear as per-slide text boxes, they will trigger the §4.3 auto-fail ("implementing required master/layout content directly on slides"). They MUST live on the master.
- Create **4 layouts** (title, content, two-column, blank-as-needed). Slide 5's whole purpose is to test that repeated elements inherit from master — verify by inserting a new slide with that layout and confirming the footer/brand appears without being pasted.
- Every slide that has a title must use the **title placeholder** (not a freestanding text box). Same for body content on slides where §14 calls for a "body placeholder" (slides 1, 2, 12, 19). §5.2 is explicit: a required placeholder replaced by a freestanding text box is *not* semantically equivalent — it fails.

### 3.3 Per-slide construction (§14)

For each slide, use native constructs only. No substitutions.

- **S1 cover**: title + subtitle placeholders (both must be `<p:ph>` bound), master background, 1 hero image from the asset manifest, decorative shapes with shadow + transparency, repeated footer from master.
- **S2 agenda**: body placeholder with bulleted list, grouped icon+text rows (each row grouped as one `<p:grpSp>`), strict alignment.
- **S3 table**: `Insert → Table`. Native `<a:tbl>`. Merged cells via Table menu (not drawn rectangles). Precise cell fills/borders. Side annotations as separate text boxes aligned to table rows. **Do not build tables out of grouped rectangles** — auto-fail.
- **S4 chart**: `Insert → Chart`. Native OOXML chart (`ppt/charts/chartN.xml` + embedded xlsx). Set exact type, title, legend, labels, axis formatting. Overlay callout shapes *on top*, not as part of the chart image.
- **S5 master reuse**: repeated elements must come from master/layout, not from copy-paste. The grader will diff slide XML against master XML to catch this.
- **S6 multilingual**: Arabic must have `<a:rPr lang="ar-SA">` or similar and trigger RTL paragraph direction; Japanese with `lang="ja-JP"`. Use **Noto Sans Arabic** and **Noto Sans JP** (the bundled fonts). Never use the system Arabic/JP fallback.
- **S7 crop/mask**: native image crop rectangle (`<a:srcRect>`), `picture → crop to shape` for masking.
- **S8 overlap/shadow/transparency**: native shape effects. Gradient fills via `<a:gradFill>`. No raster approximations.
- **S9 dense text**: disable autofit (do not use "shrink text on overflow" — the spec calls this an "illegal autofit trick"). Use explicit line spacing.
- **S10 connectors**: use `Insert → Connector`. Connectors must be native connector shapes, not drawn lines.
- **S11 theme vs override**: some shapes should reference theme colors (`<a:schemeClr val="accent1"/>`), some explicit RGB. Pick deliberately.
- **S12 fields**: `Insert → Header and Footer` for date/slide number. Must serialize as native fields (`<a:fld>`), not typed text. Reference datetime pinned to `2025-01-01T00:00:00Z`.
- **S13 composite**: chart + table + image + multilingual + annotations, all native.
- **S14 RTL-heavy**: mixed LTR/RTL paragraphs, mirrored alignment.
- **S15 rotated text**: text box rotation via `<p:xfrm rot="...">`, not via transformed paths.
- **S16 off-canvas bleed**: shapes intentionally extending beyond canvas. Document the intent in the prompt so it isn't flagged as the anti-cheat "hiding content off-canvas" rule.
- **S17 deep grouping**: nested `<p:grpSp>`. Verify grouping actually nests (select group, regroup child, ungroup parent to check).
- **S18 multi-column editorial**: grid alignment, pattern fills (`<a:pattFill>`), multilingual subcomponents.
- **S19 repetition + internal hyperlinks**: `Insert → Hyperlink → Document → Target in document`. Must produce `action="ppaction://hlinksldjump"` — **internal only**. Any `http://` / `https://` hyperlink on S19 will be rejected by quarantine.
- **S20 torture**: every construct from every prior slide in one slide.

### 3.4 Forbidden constructs (§2.3, §13.3)
Before saving, check: zero SmartArt, zero video, zero audio, zero comments, **zero notes slides**, zero hidden slides. In Impress: `View → Notes` — all notes panes must be empty. `Slide → Show Slide` — nothing hidden. After saving, the `.pptx` ZIP must contain **no** `ppt/notesSlides/` directory and **no** `notesSlide1.xml.rels`. Delete `ppt/notesMasters/` too if present.

---

## Phase 4 — Post-authoring scrub

After saving as `benchmark/deck/gold/gloss-v1-gold.pptx`, do the forensic cleanup the current deck is missing:

1. **Unzip and inspect**:
   ```bash
   mkdir -p /tmp/gold && unzip -o benchmark/deck/gold/gloss-v1-gold.pptx -d /tmp/gold
   ```

2. **Font audit**:
   ```bash
   grep -rhoE 'typeface="[^"]+"' /tmp/gold/ppt/ | sort -u
   ```
   The ONLY acceptable typeface names: `Carlito`, `Caladea`, `Liberation Sans`, `Liberation Serif`, `Liberation Mono`, `Noto Sans`, `Noto Sans Arabic`, `Noto Sans JP`, `Noto Serif`, and theme references `+mj-lt`, `+mn-lt`, `+mj-ea`, `+mn-ea`, `+mj-cs`, `+mn-cs`. **Anything else = auto-fail.** If `Arial`, `Calibri`, `Aptos`, `Courier New`, `Helvetica`, `Times`, `Cambria` appear: fix in Impress's font replacement table, re-save, re-check.

3. **Theme font audit**: open `/tmp/gold/ppt/theme/theme1.xml`, confirm `<a:majorFont>` and `<a:minorFont>` point to Carlito/Caladea/Noto, not Aptos or Calibri. The current deck's theme references Aptos — Impress built from scratch shouldn't, but verify.

4. **Notes purge** (if any leaked in):
   ```bash
   zip -d benchmark/deck/gold/gloss-v1-gold.pptx \
       'ppt/notesSlides/*' 'ppt/notesMasters/*' \
       'ppt/_rels/notesSlides*' 'ppt/_rels/notesMasters*'
   ```
   Then edit `[Content_Types].xml` and `ppt/_rels/presentation.xml.rels` to remove the corresponding `<Override>` and `<Relationship>` entries. After this, `docProps/app.xml` `Notes` count should be 0.

5. **docProps sanitize**: `docProps/app.xml` should not say `Microsoft Macintosh PowerPoint`. Since you authored in Impress, it will say `LibreOffice/7.6.x`. If not, you didn't actually author in Impress.

6. **Placeholder audit**:
   ```bash
   grep -c '<p:ph ' /tmp/gold/ppt/slides/slide*.xml
   ```
   Slides 1, 2, 12, 19 must have ≥ 2 placeholders each (title + body/subtitle). Every slide must have ≥ 1 (title). The current deck has exactly 1 per slide — that's the symptom of body content being freestanding text boxes.

7. **Anti-cheat audit** (§4.3 one-time pass before release):
   - No single raster > 40% slide area that isn't in `assets/manifest.json`.
   - No `<a:custGeom>` shapes replacing native text (text-as-outlines check).
   - No `<p:pic>` where the prompt demands a `<p:graphicFrame>` chart or table.

8. **ECMA-376 schema validation** (§13.1 step 4, §15 stage 0.5): run the RELAX NG validator from `schemas/ecma-376/relaxng-transitional/` against every part. Fix any schema violations. Until this is clean, the grader's stage 0.5 rejects the submission.

9. **Title sweep**: verify no slide has the literal title "PowerPoint Presentation". The current deck has this on 5 slides.

---

## Phase 5 — Export the reference renders (§9.5, §13.1 step 5)

Inside the pinned Docker container, not on your host:

```bash
docker run --rm -v "$PWD/benchmark:/bench" gloss-v1-env \
  libreoffice --headless --convert-to pdf \
  --outdir /bench/deck/exports /bench/deck/gold/gloss-v1-gold.pptx
# split PDF to 1920×1080 PNGs per §9.5
```

Output: `benchmark/deck/exports/slide-01.png … slide-20.png`, each exactly 1920×1080. These are the gold reference images.

---

## Phase 6 — Checklist authoring (§12, §10.5, §13.1 step 6)

One YAML file per slide, plus deck-level items.

1. `benchmark/checklist/deck.yaml` — 15–30 deck-level items (master reuse consistency, theme coherence, font policy, asset policy, tier membership, cross-slide consistency).

2. `benchmark/checklist/slides/slide-NN.yaml` — 12–18 items per slide, distributed ~30% critical / ~40% major / ~30% minor per §10.5.

Each item must exactly match the schema in §12:
```yaml
schema_version: "1.0"
id: slide-03.native-table-required
scope: slide
slide: 3
tier: 1
title: Native table required
description: Slide 3 must contain exactly one native OOXML table (<a:tbl>).
kind: structure
severity: critical
source_of_truth: ooxml
verification:
  method: object_compare
  selector: table
  expectation:
    exact_count: 1
    required: true
  tolerance:
    bbox_px: 2
    units: pixels_at_1920x1080
failure_mode:
  automatic_fail_if:
    - grouped_lines_and_text_used_as_table
    - raster_image_used_as_table
  propagation: zero_slide
```

Validate every file against `schemas/checklist-item.schema.json`. For renderer-limited features (charts, gradients, shadows, autofit, complex text), **split into two items** per §9.3.1: one `source_of_truth: ooxml` weighted `critical`, one `source_of_truth: render` weighted `minor`.

Target: 255–390 total scored items (20 × ~14 + ~22 deck-level).

---

## Phase 7 — Fixtures (§7)

For every slide, generate the expected scene graph by running the grader's extractor on the gold deck:

```bash
gloss extract --deck benchmark/deck/gold/gloss-v1-gold.pptx \
  --out benchmark/fixtures/expected-scenegraphs/
gloss extract --deck benchmark/deck/gold/gloss-v1-gold.pptx \
  --deck-level --out benchmark/fixtures/expected-deck.json
```

These are the ground truth the grader diffs submissions against.

---

## Phase 8 — Baselines (§13.4)

Three runs, in this order, each producing `benchmark/baselines/*.json`:

1. **Programmatic copy**: python-pptx script reads gold OOXML and reconstructs it. Expected score **0.90–1.00**. If below 0.90, your checklist is over-specified or your extractor is wrong — fix before public release.
2. **Human expert**: skilled author recreating from prompts + reference images + manifest. Expected **0.85–0.98**.
3. **Naive LLM**: frontier model, no tuning, canonical prompts. Expected **0.20–0.60**.

If any baseline falls outside its band (§13.4), revise the checklist/thresholds before freezing.

---

## Phase 9 — Acceptance gate (§29)

Before declaring the gold deck done, all of these must be true. Treat as a literal checklist:

- [ ] Authored in LibreOffice Impress; `docProps/app.xml` Application starts with `LibreOffice`.
- [ ] Font audit shows only Carlito/Caladea/Liberation/Noto.
- [ ] Zero notes slides, zero hidden slides, zero comments, zero SmartArt, zero video/audio.
- [ ] Every required placeholder is bound (`<p:ph>`); slides 1/2/12/19 have title + body placeholders.
- [ ] Slides 3/13/20 contain `<a:tbl>`; slides 4/13/20 contain `<c:chart>` with embedded xlsx.
- [ ] Slide 5 passes the master-reuse diff (repeated elements come from master, not per-slide shapes).
- [ ] Slide 6 has Arabic + Japanese runs with correct `lang` attributes and Noto Sans Arabic / JP fonts.
- [ ] Slide 19 internal hyperlinks only (`ppaction://hlinksldjump`).
- [ ] No slide title reads "PowerPoint Presentation".
- [ ] ECMA-376 RELAX NG validation passes with zero errors.
- [ ] `benchmark/deck/exports/slide-01..20.png` all exist at 1920×1080.
- [ ] `prompts/`, `assets/manifest.json`, `fonts/manifest.json`, `checklist/deck.yaml` + 20 slide YAMLs, `fixtures/expected-scenegraphs/slide-01..20.json`, `baselines/*.json` all populated.
- [ ] Programmatic-copy baseline ≥ 0.90; human-expert ≥ 0.85; naive-LLM within 0.20–0.60.
- [ ] `schema_valid: true` from stage 0.5.

---

## About the existing `Gloss_v1.pptx`

Keep it as a *drafting reference* — it has the right slide matrix shape and is useful to mine for layout ideas. But **do not** try to convert it in place. The authoring tool, notes slide, font table, title defaults, and placeholder usage are baked in at serialization time, and a resave will not clean them. Treat it as v0.5 scaffolding; rebuild in Impress per Phase 3.

---

## Critical path

**Order**: Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Don't interleave.

The two most common failure modes for this kind of benchmark package are:
1. Authoring the deck before the prompts are validated, which locks in ambiguity.
2. Skipping the font replacement setup, which silently poisons every subsequent phase because every render and extraction will carry the wrong font names.
