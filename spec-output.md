# SUPERSEDED SNAPSHOT — DO NOT IMPLEMENT OR RELEASE

This file is retained only as historical debate output. The canonical contract is
`GLOSS_OPENSPEC.md`, whose current status is Draft pending adversarial consensus. Regenerate this
snapshot only after the canonical document is freeze-ready and independently accepted.

# Gloss v1 OpenSpec

Status: Superseded — stale pre-remediation contract; not freeze-ready
Scope: Public benchmark, automated grading suite, and hosted evaluation service for slide generation fidelity  
Primary artifact: A fully public, machine-graded PowerPoint benchmark inspired by the ACID browser tests

## 1. Summary

`Gloss` is a benchmark for evaluating whether a model can generate a `.pptx` deck from natural-language prompt inputs while preserving both:

- rendered visual fidelity under a fixed reference renderer (LibreOffice Impress headless)
- user-visible structural fidelity inside the PowerPoint deck

The benchmark tests two capabilities in combination:

1. **Prompt interpretation**: can the model translate natural-language slide descriptions into correct PowerPoint constructs?
2. **Output fidelity**: does the generated deck match the gold standard visually and structurally?

Reference images are provided as supplementary guidance, not as the sole source of truth. The natural-language prompt/spec is the primary input; the reference image resolves visual ambiguity where the prompt is intentionally underspecified.

The benchmark is intentionally gameable in v1. The goal is not secrecy. The goal is to create a brutal, public, tunable target that forces frontier models to get meaningfully better at producing real slides instead of image-backed fakes.

`Gloss` ships in three difficulty tiers:

- **Level 1** (5 slides): basic constructs — placeholders, images, simple tables, master usage
- **Level 2** (12 slides): intermediate — multilingual text, charts, grouping, overlap, z-order
- **Level 3** (20 slides): full torture — all failure modes combined, deep nesting, composite stress

Each tier is scored independently. A submission targets a specific tier and is graded only on that tier's slides. The leaderboard tracks per-tier scores. A **full-deck perfect pass** requires submitting for Level 3 and achieving `deck_passed == true` (see §10.1 for the precise definition) — this is the ceiling achievement, not a prerequisite for leaderboard presence.

`Gloss` is available in two modes:

- **Local mode**: download the benchmark package, run the grader locally using Docker (Linux/macOS/Windows). Scores are self-reported and unverified.
- **Hosted mode**: submit via API to the Gloss service, which grades in a controlled Linux Docker environment and publishes verified scores to the leaderboard. Only hosted-mode scores appear on the official leaderboard.

Submissions are graded only from the final submitted `.pptx`. No tool traces, reasoning logs, or intermediate artifacts affect the score.

## 2. Product Principles

### 2.1 Core principles

- Public by default: gold deck, prompts/specs, assets, checklist items, and grader logic are all public in v1.
- Deterministic by design: rendering, fonts, assets, slide size, and grading environment are fixed.
- Native slides only: a visually correct screenshot hack is a failure.
- Machine-graded only: no human review path exists in the benchmark contract.
- User-visible equivalence: ignore unstable non-visible identifiers, but require equivalent visible and structural fidelity.
- Single benchmark deck first: keep v1 operationally simple and hard enough to matter.
- Progressive difficulty: Level 1/2/3 tiers track industry progress over time.
- Prompt-first evaluation: the natural-language prompt is the primary input; reference images are supplementary.
- Standards-based: targets ECMA-376 (Office Open XML), not any single renderer. Like the ACID browser tests targeted W3C standards, not one browser.
- Cross-platform by design: the entire benchmark runs on Linux in Docker. No Windows or Microsoft Office dependency.
- Prompts are designed artifacts: prompts are authored and validated independently before the gold deck, not reverse-engineered from it.

### 2.2 What this benchmark is testing

The benchmark tests whether a model can:

- interpret natural-language prompt/spec input as the primary directive
- use reference images as supplementary visual guidance where prompts are underspecified
- recreate the slide as native PowerPoint content
- preserve visual output within the defined fidelity threshold
- preserve required PowerPoint semantics such as masters, placeholders, charts, tables, and fields
- maintain deck-wide consistency across separate slide prompts
- generate efficient, well-formed output (tracked via efficiency metrics)

### 2.3 What this benchmark is not testing

- hidden slides
- comments
- speaker notes
- transitions, builds, animations
- video, audio
- SmartArt
- non-PowerPoint submission formats
- strict OOXML schema validity as a goal in itself
- whether the model is useful for ordinary business decks (see §2.4)

### 2.4 External validity disclaimer

Gloss v1 is a ceiling test using deliberately hostile torture slides, not a measure of general slide-generation utility. A model that fails Gloss may still be useful in production. A model that passes Gloss by overfitting to the public benchmark may still be poor at novel slide generation. Realistic multi-slide story decks are planned for v2.

## 3. Locked v1 Decisions

The following product decisions are fixed for v1:

- Benchmark form: single public deck with three difficulty tiers
- Slide count target: Level 1 = 5, Level 2 = 12, Level 3 = 20
- Slide style: torture-test slides, not a realistic story deck
- Slide content: static only
- Submission format: single `.pptx`
- Generation workflow: slide-by-slide generation is allowed, official scoring is deck-wide per tier
- Inputs: deck-level prompt, per-slide prompts/specs, slide reference images (supplementary), allowed external asset manifest
- Gold visibility: fully public
- Grader visibility: fully public
- Scoring model: weighted checklist items with severity tiers and an aggregate fidelity score
- Target standard: ECMA-376 5th Edition (Office Open XML) — the `.pptx` format is PresentationML as defined in ECMA-376 Part 1
- Structural grading: ECMA-376 schema validation (RELAX NG / XSD) plus semantic equivalence comparison against gold structure
- Visual grading: perceptual similarity check under a fixed reference renderer export, with exact pixel match as a reported stretch metric
- Reference renderer: LibreOffice Impress headless (pinned version, Docker image) for official scoring; PowerPoint fidelity reported as optional bonus score (not required); Aspose.Slides may be evaluated as a higher-fidelity alternative in future versions
- Runtime: Linux Docker container with pinned LibreOffice version — no Windows or Microsoft Office dependency
- Fonts: libre/open-source metric-compatible fonts only, bundled with benchmark (Noto family, Liberation, Carlito, Caladea)
- Font policy: bundled benchmark fonts only; no commercial fonts; metric-compatible substitutes for Calibri (Carlito) and Cambria (Caladea) are included
- Language coverage: English plus at least one RTL language and one CJK language
- Slide size: `16:9` only
- Repeated elements: some must come from masters/layouts, not copied slide content
- External images: only explicitly allowed assets may appear (strict hash match, no approved equivalents)
- Network access policy: irrelevant for local mode; disclosed via attestation for hosted-mode leaderboard submissions (v1 cannot enforce generation-time network restrictions; enforcement is planned for v2 Execution Mode — see §25.8)
- Visual cheats: screenshot-based fakery is automatic failure

## 4. Benchmark Contract

### 4.1 Task definition

For each slide, the model receives:

- a deck-level prompt describing global design system and cross-slide consistency expectations
- a per-slide natural-language prompt/spec (the primary input)
- a reference image exported from the gold deck (supplementary visual guidance)
- a list of allowed external assets, including mirrored local copies and fixed URLs

The model must produce a PowerPoint deck that:

- correctly interprets the natural-language prompt
- renders with high visual fidelity to the gold deck under the reference renderer (LibreOffice)
- uses native PowerPoint constructs where the prompt/spec requires them
- achieves semantic structural equivalence with the gold deck

### 4.2 Official success criterion

A **tier-scoped perfect pass** requires:

- every **scored** checklist item in that tier passes (informational items with weight 0 are excluded from pass/fail determination)
- every applicable scored deck-level checklist item passes
- no automatic-fail cheating rules are triggered on any slide in the tier
- fidelity_score for the tier is 1.0

A **full-deck perfect pass** additionally requires a Level 3 tier-scoped perfect pass (which includes all Level 1 and Level 2 slides).

### 4.3 Official failure conditions

The following are automatic failures. Propagation rules:

- An automatic-fail **zeroes every checklist item on the affected slide** (all items for that slide score 0).
- If the automatic-fail is deck-level (e.g., master reuse violation spanning multiple slides), **only the affected slides are zeroed**, not the entire deck.
- Automatic-fail submissions **are still published to the leaderboard** with their reduced scores and an `anti_cheat_flags` array in the report. They are not suppressed.
- `deck_passed` is false if any automatic-fail was triggered OR if fidelity_score < 1.0 OR if repair was triggered (consistent with §10.1).

The following are automatic failures for any affected slide:

- using images to fake native PowerPoint objects
- using a full-slide raster image as slide content
- using a large screenshot crop to fake native composition (defined as any single raster covering more than 40% of slide area that is not in the asset manifest)
- converting required editable text into outlines or shapes
- replacing required charts with non-chart approximations
- replacing required tables with non-table approximations when the prompt explicitly requires a table
- implementing required master/layout content directly on slides
- using fonts outside the bundled font set
- hiding overflow or incorrect content off-canvas or beneath opaque shapes to game the visual result
- tiling multiple raster images to approximate a screenshot composite
- overlaying thin editable text on raster backgrounds to simulate native text

### 4.4 Repair behavior

If LibreOffice repairs or silently corrects a malformed submission on open:

- **Visual scoring** (Stage 2) uses the rendered state (what LibreOffice actually renders after any auto-correction)
- **Structural scoring** (Stage 3) uses the original uploaded .pptx (what the model actually generated)
- **Schema validation** (Stage 0.5) catches structural issues before rendering

A submission that triggers LibreOffice document recovery is flagged with `repair_triggered: true`, and `deck_passed` is set to `false` (a repaired deck cannot achieve a perfect pass). The repair event is logged in the report.

## 5. Scope of Structural Fidelity

Structural fidelity in v1 means semantic equivalence in user-visible object structure, not literal isomorphism with the gold deck's internal representation.

### 5.1 Structural properties that must match (semantically)

- slide ordering
- slide count
- layout/master usage where required by the prompt
- placeholder usage and placeholder type where required by the prompt
- object type (a table must be a table, a chart must be a chart)
- grouping structure (objects that are grouped in gold must be grouped in submission, but internal group nesting depth may differ if the visual and logical result is equivalent)
- z-order (user-visible stacking order must match)
- object count (within a tolerance of ±0 for required objects; decorative objects may vary if visually equivalent)
- text content (exact Unicode match)
- text editability
- script and directionality behavior
- image usage and source legality (strict hash match against manifest)
- chart presence, chart object type, and visible data representation where required
- table presence and table object type where required
- native field usage where required by the prompt
- geometry and placement (within defined tolerance)
- crop behavior
- overlap relationships
- on-canvas and intentional off-canvas placement
- theme/master-driven versus per-slide override behavior where required by the prompt

### 5.2 Semantic equivalence rules

The comparator recognizes that multiple valid PowerPoint implementations can produce the same user-visible result. The following are treated as equivalent:

- Different internal group nesting that produces the same visual hierarchy and z-order
- Different XML serialization order that produces the same rendered output
- Different shape implementation (e.g., freeform vs. preset geometry) that produces visually identical geometry within tolerance
- Different color specification methods (theme reference vs. explicit RGB) that produce the same rendered color

The comparator does NOT treat the following as equivalent:

- A required native table replaced by grouped shapes
- A required native chart replaced by an image or shapes
- A required placeholder replaced by a freestanding text box
- Required master/layout inheritance replaced by slide-level duplication

### 5.3 Structural properties that do not matter

- PowerPoint-generated object IDs
- XML relationship IDs that are not user-visible
- internal serialization order that does not affect user-visible structure
- non-visible metadata not surfaced to users in normal editing/viewing workflows

## 6. Difficulty Tiers

### 6.1 Tier definitions

**Level 1 — Foundation (5 slides)**

Tests basic PowerPoint generation capabilities:

- Slide 1: Cover with title/subtitle placeholders, master background, one image
- Slide 2: Agenda with body placeholder, grouped items, alignment
- Slide 3: Simple native table with styling
- Slide 4: Basic native chart with labels
- Slide 5: Master reuse enforcement (repeated layout elements)

**Level 2 — Intermediate (12 slides)**

Includes Level 1 slides plus 7 additional slides testing:

- Multilingual text (English + Arabic RTL + Japanese CJK)
- Image cropping and masking
- Overlap, shadow, and transparency
- Dense text overflow
- Connector and alignment diagrams
- Theme versus local override behavior
- Slide number / date fields

**Level 3 — Full Torture (20 slides)**

Includes Level 2 slides plus 8 additional slides testing:

- RTL-heavy comparison layouts
- Rotated text alignment
- Intentional off-canvas bleed
- Deep nested grouping
- Multi-column editorial layout
- Repetition and deck-wide consistency
- Composite stress (chart + table + image + multilingual + rotation + overlap + grouping + master dependencies)

### 6.2 Tier scoring

Each tier is scored independently. A model's profile includes:

- Level 1 score (foundation)
- Level 2 score (intermediate)
- Level 3 score (full torture)
- Aggregate weighted score

A model may submit for any tier independently.

## 7. Proposed Benchmark Package

The public package ships as a versioned directory with a stable layout.

```text
gloss-v1/
  README.md
  SPEC.md
  VERSION
  CHANGELOG.md
  Dockerfile                    # canonical grading environment
  docker-compose.yaml
  environment/
    libreoffice-version.md
    docker-image.md
    font-install.md
    drift-canary.md
  schemas/
    ecma-376/                    # ECMA-376 5th Edition schemas
      relaxng-transitional/
      xsd-transitional/
    checklist-item.schema.json
    report.schema.json
  benchmark/
    tiers/
      level-1/
        slides.json          # which slides comprise this tier
      level-2/
        slides.json
      level-3/
        slides.json
    deck/
      gold/
        gloss-v1-gold.pptx
      exports/
        slide-01.png
        slide-02.png
        ...
    prompts/
      deck.md
      variants/
        canonical/
          slide-01.md
          slide-02.md
          ...
        paraphrase-a/
          slide-01.md
          ...
        paraphrase-b/
          slide-01.md
          ...
    assets/
      manifest.json
      mirrored/
        ...
    fonts/
      manifest.json
      LICENSE
      files/
        ...
    checklist/
      deck.yaml
      slides/
        slide-01.yaml
        slide-02.yaml
        ...
    fixtures/
      expected-scenegraphs/
        slide-01.json
        ...
      expected-deck.json
    baselines/
      human-expert.json
      programmatic-copy.json
      naive-llm.json
  grader/
    README.md
    pyproject.toml
    gloss/
      cli.py
      runtime/
      export/
      inspect/
      compare/
      checklist/
      report/
      quarantine/
      drift/
    tests/
      ...
  service/
    README.md
    api-spec.yaml
    docker-compose.yaml
  examples/
    passing/
    failing/
```

## 8. Input Model

### 8.1 Prompt model

V1 uses:

- one deck-level prompt
- one prompt/spec per slide (the primary input)
- optional paraphrased prompt variants that all target the same gold deck

Prompt design principles:

- no intentional ambiguity in canonical prompts
- no hidden constraints
- no attempt to trap the model on underspecified details
- prompts are derived from the gold deck but reviewed independently for completeness

The reference image is supplementary visual guidance. Where the prompt is specific, the prompt takes precedence. Where the prompt is intentionally underspecified (e.g., exact color shade), the reference image resolves the ambiguity.

### 8.2 Prompt robustness protocol

Paraphrased variants are scored as follows:

- The canonical prompt set is the official benchmark input
- Each paraphrased variant set is scored independently using the same gold deck and checklist
- A model's **robustness score** is computed **per tier**: for each tier, it is the minimum of each variant's best official score (across all submissions) for all standard variants (canonical + paraphrase-a + paraphrase-b)
- To claim an official robustness score for a tier, **all standard variants must be submitted for that tier**. Partial variant sets do not produce a robustness score.
- The leaderboard displays the canonical score (always) and the robustness score (only when all variants are submitted)
- Mean and standard deviation across variants are also displayed when available

### 8.3 Asset model

Each explicitly allowed external image must have:

- a fixed canonical URL if relevant
- a mirrored local copy in the benchmark package
- a stable asset ID
- content hash (SHA-256)
- usage constraints if needed

The grader verifies embedded media using a two-tier hash model:

- **Primary hash**: SHA-256 of the original asset file from the manifest. This is checked first.
- **Accepted recompression hashes**: PowerPoint may internally recompress images (e.g., JPEG re-encoding at its default quality). For each asset in the manifest, the benchmark package pre-computes and stores a set of known recompression hashes by opening the gold deck, extracting the media part, and hashing it. These are published alongside the primary hash.

An embedded media part passes the asset check if its hash matches either the primary hash or any accepted recompression hash for that asset. No other variants are accepted.

## 9. Canonical Runtime

### 9.1 Runtime requirement

V1 requires a pinned Linux Docker environment with LibreOffice Impress headless installed. No Windows or Microsoft Office dependency exists.

### 9.2 Why ECMA-376 + LibreOffice

The benchmark targets the ECMA-376 standard (Office Open XML), not any single renderer. This mirrors how the ACID browser tests targeted W3C standards rather than one browser.

LibreOffice Impress headless is the reference renderer because:

- it is free and open-source (no licensing cost at any scale)
- it runs on Linux in Docker (cross-platform, CI/CD friendly)
- it is deterministic within a pinned version + pinned font set
- it natively reads ECMA-376 PresentationML (`.pptx`)
- it supports headless batch export to PNG
- it has no COM automation fragility, no modal dialogs, no GUI dependency

ECMA-376 schema validation (using the RELAX NG and XSD schemas from the standard) provides structural validation that is independent of any renderer.

### 9.3 Rendering fidelity expectations

LibreOffice rendering differs from PowerPoint in known ways:

| Feature | LibreOffice Fidelity | Notes |
|---------|---------------------|-------|
| Text and shapes | ~90%+ | With metric-compatible fonts installed |
| Standard charts | ~80-85% | Minor layout differences |
| Tables | ~85-90% | Minor spacing differences |
| Images/media | ~95%+ | Embedded images render correctly |
| SmartArt | Poor | Intentionally excluded from v1 benchmark (§2.3) |

The v1 benchmark deliberately avoids features where LibreOffice fidelity is poor (SmartArt, animations, 3D effects).

### 9.3.1 Renderer-limited features

Some v1 slide features (charts, gradients, shadows, autofit, complex text layout) may render differently in LibreOffice than in PowerPoint. For these features, checklist items are **split into structural and visual checks**:

- **Structural checks** (source_of_truth: `ooxml`): verify the correct OOXML construct exists in the XML (e.g., a native chart element, correct gradient definition). These pass/fail based on XML inspection, independent of rendering.
- **Visual checks** (source_of_truth: `render`): verify the rendered output matches the gold export. These may have lower SSIM scores due to renderer differences, not model errors.

This split ensures models get credit for producing correct OOXML structures even when the reference renderer's visual output differs from PowerPoint. Structural checks are weighted as `critical`; visual checks for renderer-limited features are weighted as `minor`.

### 9.4 Environment freeze requirements

Before grading is enabled, the benchmark must freeze:

- Docker base image (e.g., `ubuntu:22.04`)
- LibreOffice version (exact build string, e.g., `libreoffice-7.6.4.1`)
- export resolution
- slide size
- font installation set (libre metric-compatible fonts)
- locale settings (`en-US.UTF-8`)
- timezone (`UTC`)
- reference datetime for date/time fields: `2025-01-01T00:00:00Z`

### 9.5 Export contract

The official export path:

- open presentation in LibreOffice Impress headless
- export all slides to PNG at **1920 × 1080 pixels** (16:9)
- compare exported PNGs against gold exports using perceptual similarity (see §22)
- the reference datetime for date/time fields is pinned to `2025-01-01T00:00:00Z`

Export command (reference):
```bash
libreoffice --headless --convert-to png \
  --outdir /output /input/submission.pptx
```

If individual slide export is not supported in the pinned version, the two-step path is used:
```bash
libreoffice --headless --convert-to pdf /input/submission.pptx
# Then split PDF to per-page PNGs at 1920×1080
```

### 9.6 Environment drift detection

The grading environment includes an automated drift canary:

- re-grades the gold deck on a weekly schedule
- compares pixel output and structural extraction against stored baselines
- alerts if any slide's perceptual similarity drops below the fidelity threshold
- alerts if any structural extraction result changes
- blocks new grading runs until drift is investigated and resolved
- logs all canary results with timestamps for audit

### 9.7 Docker reference image

The benchmark ships a Dockerfile that produces the canonical grading environment:

```dockerfile
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-core \
    fonts-liberation fonts-noto fonts-noto-cjk \
    fonts-crosextra-carlito fonts-crosextra-caladea \
    python3 python3-pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Font policy: ONLY the packages above are installed.
# No system default fonts (dejavu, etc.) beyond what these packages pull in.
# Carlito = metric-compatible Calibri; Caladea = metric-compatible Cambria.
RUN useradd -m -s /bin/bash grader
USER grader
WORKDIR /benchmark
```

This image is the canonical grading environment. Third-party implementations must match its output on the published test fixtures.

### 9.8 Optional PowerPoint fidelity score

For models targeting PowerPoint-specific rendering, an optional **PowerPoint fidelity score** may be computed by running the grader on a Windows machine with PowerPoint installed. This score:

- is reported separately on the leaderboard (not part of the official fidelity_score)
- is not required for leaderboard participation
- uses the same checklist and SSIM threshold
- is only available for on-premise or self-hosted grading (not the hosted service)

This allows teams with PowerPoint access to measure PowerPoint-specific fidelity while keeping the official benchmark cross-platform.

## 10. Scoring Model

### 10.1 Score representation

The benchmark score is represented as:

- `fidelity_score`: weighted aggregate (0.0 to 1.0)
- `passed_items`: count of passed checklist items
- `total_items`: count of total checklist items
- `deck_passed`: boolean (true only if fidelity_score == 1.0 AND no anti-cheat flags AND no repair events)
- `eligible`: boolean (true if the submission is eligible for the leaderboard — not rejected by quarantine, not timed out)
- per-slide item pass/fail breakdown with severity
- deck-level item pass/fail breakdown with severity
- per-tier scores (Level 1, Level 2, Level 3) — non-targeted tiers are serialized as `null` in JSON output; they are not omitted
- efficiency metrics (see §10.4)
- `anti_cheat_flags`: array of triggered anti-cheat rules (empty if clean)
- `repair_triggered`: boolean

### 10.2 Severity tiers

Each checklist item has a severity tier that determines its weight in the aggregate score:

- **critical** (weight 3): native object type requirements, anti-cheat rules, master/layout enforcement, text content correctness
- **major** (weight 2): visual fidelity, z-order, grouping structure, field semantics, chart/table data accuracy
- **minor** (weight 1): geometry tolerance, shadow/transparency precision, spacing precision, decorative element details
- **informational** (weight 0): stretch metrics and diagnostic data reported for analysis but excluded from fidelity_score

The fidelity score is: `sum(passed_item_weights) / sum(all_item_weights)`

**Tier aggregation**: each tier's fidelity score is computed independently using only the items belonging to that tier. The **aggregate score** displayed on the leaderboard is the Level 3 fidelity score (since Level 3 includes all slides). For submissions targeting Level 1 or Level 2 only, the aggregate score equals that tier's score.

The pass/fail item count is also reported for item-level analysis.

### 10.3 Item types

Checklist items fall into two buckets:

- slide-level items: scoped to a single slide
- deck-level items: scoped to the entire deck (e.g., master reuse consistency, cross-slide theme coherence)

Deck-level items are scored independently from slide-level items. A deck-level item failing does not automatically zero any slide-level items.

However, **automatic-fail rules** (§4.3) are a separate mechanism from normal item scoring. When an automatic-fail rule triggers, it zeroes all items on the affected slide(s), regardless of whether the rule was triggered by a slide-level or deck-level condition.

### 10.4 Efficiency metrics

Efficiency metrics are split into **verified** (measured by the service) and **attested** (self-reported by the submitter):

**Verified metrics** (objective, measured by the hosted service):

- `submission_file_size_bytes`: size of the submitted .pptx
- `grading_duration_seconds`: time taken by the grader to process the submission
- `schema_valid`: boolean from ECMA-376 schema validation

**Attested metrics** (self-reported, displayed with "self-reported" label on leaderboard):

- `generation_strategy`: `"direct"` | `"code"` | `"hybrid"` | `"template-edit"` — describes the generation approach
- `generation_wall_clock_seconds`: total wall-clock time for generation
- `generation_token_count`: total tokens consumed
- `generation_cost_usd`: estimated cost of generation
- `retry_count`: number of generation attempts before final submission

For `"code"` or `"hybrid"` strategy submissions, optionally:

- `code_language`: e.g., `"python-pptx"`, `"docx4j"`, `"Open XML SDK"`
- `code_line_count`: lines of generated code (excluding comments/blanks)

Efficiency metrics do not affect the fidelity score. Verified metrics appear prominently on the leaderboard. Attested metrics are displayed with a self-reported indicator.

### 10.5 Suggested v1 item volume

- 12 to 18 checklist items per slide across 20 slides
- 15 to 30 deck-level items

This yields roughly 255 to 390 total checks. Severity distribution should target approximately 30% critical, 40% major, 30% minor.

## 11. Stochasticity and Reproducibility

### 11.1 Official scoring protocol

For non-deterministic generation systems:

- the official leaderboard score is the **best score across all submissions** for a given `(model_id, model_version, benchmark_version, prompt_variant)` tuple
- all submission scores are recorded and visible on the leaderboard
- mean and standard deviation across submissions are also displayed
- hosted mode enforces a maximum of **3 submissions per (model_id, model_version, benchmark_version, prompt_variant) tuple** within a 7-day window
- a model claiming robustness (§8.2) must submit for all 3 standard variants, consuming up to 9 total submission slots (3 per variant) within the window

### 11.5 Multi-window behavior

The leaderboard uses **all-time** statistics for each `(model_id, model_version, benchmark_version, prompt_variant)` tuple. When a new 7-day window opens, new submissions are added to the cumulative record. The leaderboard's `best_score`, `mean_score`, `worst_score`, and `submission_count` reflect all submissions ever made (not just the latest window). The official score is the best across all submissions for that tuple.

### 11.2 Seed handling

If a model accepts a random seed:

- the submission metadata must include the seed used
- the same seed should produce the same output (if the model claims determinism)
- the grader does not verify determinism but records the seed for reproducibility analysis

### 11.3 Cherry-picking prevention

- All submissions within a scoring window are recorded, not just the best
- The leaderboard shows best, mean, and worst scores
- Withdrawing a submission after seeing its score is not permitted in hosted mode

### 11.4 Model identity policy

- `model_id` is a free-text identifier chosen by the submitter (e.g., "gpt-4o", "claude-sonnet-4")
- `model_version` distinguishes versions (e.g., "2025-03-01", "v2.1")
- The 3-submission-per-window limit applies to the `(model_id, model_version, benchmark_version, prompt_variant)` tuple (consistent with §11.1)
- Submitters who change `model_version` to circumvent the limit are treated as separate entries on the leaderboard (which is the correct behavior — each version gets its own scores)
- The leaderboard has two views: (a) **summary view** groups entries by `model_id` and shows the best `model_version`'s score per model, and (b) **detail view** lists every `(model_id, model_version)` entry individually
- Maintainers may merge or relabel entries if aliasing is detected (e.g., same model submitted under different IDs)

## 12. Checklist Specification Format

Each checklist item is defined declaratively in YAML.

Schema:

```yaml
schema_version: "1.0"
id: slide-07.native-table-required
scope: slide
slide: 7
tier: 2          # minimum tier that includes this item (1, 2, or 3) — slide 7 is in Level 2
title: Native table required
description: Slide must contain a native OOXML table matching the gold slide.
kind: structure
severity: critical
source_of_truth: ooxml   # ooxml | render | both
  # ooxml: ECMA-376 OOXML package inspection is authoritative
  # render: reference renderer (LibreOffice) export/visual output is authoritative
  # both: both OOXML and renderer must independently pass; if either fails, the item fails
verification:
  method: object_compare
  selector: table
  expectation:
    exact_count: 1
    required: true
  tolerance:
    bbox_px: 2             # ±pixels at export resolution
    units: pixels_at_1920x1080
  semantic_equivalence:
    allow_different_cell_merge_strategy: false
    allow_different_border_implementation: true
failure_mode:
  automatic_fail_if:
    - grouped_lines_and_text_used_as_table
    - raster_image_used_as_table
  propagation: zero_slide  # zero_slide | zero_item | zero_affected_slides
  # zero_slide: zero all items on this slide
  # zero_item: zero only this item (cannot be used with automatic_fail_if per §4.3)
  # zero_affected_slides: zero all items on all slides affected by a deck-level condition (for deck-scoped auto-fail rules)
  # automatic_fail_if rules MUST use zero_slide or zero_affected_slides
```

A normative JSON Schema for checklist files will be published in `schemas/checklist-item.schema.json` (same location as the ECMA-376 schemas in the package layout, §7).

Recommended top-level item categories:

- `visual`
- `structure`
- `text`
- `typography`
- `master-layout`
- `image-asset`
- `chart`
- `table`
- `fields`
- `grouping`
- `z-order`
- `overflow`
- `multilingual`
- `theme-consistency`
- `bullet-paragraph` (NEW: bullet and paragraph semantics)
- `spacing-autofit` (NEW: line spacing and autofit modes)
- `gradient-pattern` (NEW: gradient and pattern fills)

## 13. Gold Deck Authoring Plan

### 13.1 Authoring workflow

The gold deck is authored using a **prompt-first** workflow. Prompts are designed and validated as independent artifacts before the gold deck is built.

Recommended workflow:

1. **Design prompts first.** Write natural-language slide specifications for each slide, covering all required constructs (tables, charts, masters, etc.). Prompts are the primary artifact — they must be unambiguous and complete.
2. **Validate prompts independently.** Have 2-3 skilled slide authors independently create slides from the prompts alone (no reference images), using LibreOffice Impress with the benchmark font set. **Convergence rule**: for each slide, score all independent implementations through the grader's structural comparison. If any two implementations achieve ≥ 80% structural similarity, the prompt is considered sufficiently specified. If no pair reaches 80%, the prompt is underspecified and must be revised. This process is documented per slide with results archived.
3. **Build the gold deck.** A skilled author builds the canonical gold deck in **LibreOffice Impress** (the reference renderer) using only the bundled libre fonts and approved assets. The gold deck must be authored in the same tool that will grade it to avoid serialization-dependent rendering differences.
4. **Validate ECMA-376 compliance.** Run the gold deck through RELAX NG schema validation against ECMA-376 Part 1 Transitional. Fix any schema violations.
5. **Export reference images.** Export gold slides using the canonical Docker environment (LibreOffice headless) to create the reference PNGs.
6. **Generate checklist items** from gold structure plus human review.
7. **Create baseline scores** (see §13.4).

This prompt-first flow ensures that:
- Prompts are tested artifacts, not afterthoughts
- The benchmark measures prompt interpretation, not just reconstruction from reference images
- Ambiguous prompts are caught before the gold deck is frozen

### 13.2 Gold deck design principles

The deck should be playful, varied, and deliberately hostile to naive slide generation.

Each slide should combine several failure modes at once rather than isolating only one.

### 13.3 Gold deck constraints

- use only libre/open-source fonts bundled in the Docker image (Noto, Liberation, Carlito, Caladea)
- use only allowed assets with clear licensing
- keep to 16:9
- avoid SmartArt
- avoid video and audio
- avoid notes/comments/hidden slides
- include multilingual content
- include rotated text boxes, but not true vertical East Asian layout

### 13.4 Baseline calibration

Before public release, generate baseline scores from:

- **Human expert**: a skilled PowerPoint author recreating the deck from the **exact official inputs** (deck-level prompt, per-slide prompts, reference images, asset manifest). This measures the ceiling for prompt interpretation by a human.
- **Programmatic copy**: a script using `python-pptx` that reads the gold deck's OOXML and reconstructs it programmatically (no direct file copy). This measures the ceiling for structural fidelity achievable via the python-pptx API.
- **Naive LLM**: current frontier model with no benchmark-specific tuning, using the exact official inputs.

These baselines establish the score distribution and verify that the benchmark discriminates meaningfully. Expected ranges:

- Human expert: 0.85–0.98 (high fidelity but minor visual differences from manual recreation)
- Programmatic copy: 0.90–1.0 (near-perfect structure, possible visual differences from python-pptx rendering quirks)
- Naive LLM: 0.20–0.60 (significant structural and visual gaps)

If baselines fall outside these ranges, the checklist or threshold needs revision before release.

## 14. Proposed Slide Matrix (Non-Normative)

The slide matrix below is a design target, not a frozen contract. The exact slides will be finalized during Phase 1 (§28) and frozen before Phase 2 begins. Slides are assigned to tiers as indicated.

### Level 1 slides

#### Slide 1. Cover stress test (Level 1)

Includes: title placeholder, subtitle/body placeholder, master-driven background behavior, one precisely cropped hero image, overlapping decorative shapes, shadow and transparency, repeated footer or field behavior

#### Slide 2. Dense agenda with layout semantics (Level 1)

Includes: title placeholder, body placeholder, repeated section markers from layout, grouped icon-text rows, strict alignment distribution, dense text fit behavior, bullet and paragraph semantics

#### Slide 3. Native table stress slide (Level 1)

Includes: required native table, merged or emphasized cells, precise cell fills and borders, table-aligned side annotation objects, dense data and autofit hazards, tab stops and indentation

#### Slide 4. Native chart stress slide (Level 1)

Includes: required native chart, exact chart type, chart title/legend/labels, axis formatting, overlaid callout shapes, nearby supporting text blocks

#### Slide 5. Master reuse enforcement (Level 1)

Includes: repeated master-derived header/footer components, placeholder-bound content, layout-specific repeated elements, visual correctness that could be faked by copying but must not be

### Level 2 additional slides

#### Slide 6. Multilingual editorial slide (Level 2)

Includes: English, Arabic RTL text, Japanese text, different text blocks with exact script handling, overlap with images and callouts, strict line wrapping expectations

#### Slide 7. Image crop and mask slide (Level 2)

Includes: multiple allowed images, different crop rectangles, crop-to-shape masking, overlapping layers, exact placement, caption blocks, object stacking traps

#### Slide 8. Overlap and shadow slide (Level 2)

Includes: stacked cards, semi-transparent fills, shadows, tight z-order dependencies, grouped and ungrouped combinations, gradient fills

#### Slide 9. Dense text overflow slide (Level 2)

Includes: high text density, narrow columns, exact fit expectations, no illegal autofit tricks, deliberate line-break sensitivity, line spacing control

#### Slide 10. Connector and alignment diagram (Level 2)

Includes: built-in shapes only, connectors, grouped labels, exact alignment, nested grouping, overlap and ordering dependencies

#### Slide 11. Theme versus local override slide (Level 2)

Includes: some elements required to inherit from theme/master, some elements required to override locally, visible color consistency traps, theme font and color reference vs. explicit RGB

#### Slide 12. Native field slide (Level 2)

Includes: slide number placeholder/field, date/footer field, title/body placeholders, master and layout interactions

### Level 3 additional slides

#### Slide 13. Composite stress slide (Level 3)

Includes: native chart, native table, allowed image, multilingual text, repeated layout content, dense annotations

#### Slide 14. RTL-heavy comparison slide (Level 3)

Includes: stronger Arabic emphasis, bidirectional layout interactions, mixed LTR and RTL text blocks, mirrored alignment traps

#### Slide 15. Rotated text slide (Level 3)

Includes: rotated text boxes, supporting shapes, exact anchors, alignment with non-rotated objects

#### Slide 16. Intentional off-canvas bleed slide (Level 3)

Includes: objects intentionally extending beyond canvas, legitimate crop/bleed behavior, need to distinguish design intent from cheating

#### Slide 17. Deep grouping slide (Level 3)

Includes: nested groups, repeated small elements, exact z-order inside groups, connector or label interactions

#### Slide 18. Multi-column editorial layout (Level 3)

Includes: complex alignment grid, image-text interaction, strict spacing, multilingual subcomponents, repeated layout semantics, pattern fills

#### Slide 19. Repetition and consistency slide (Level 3)

Includes: strong deck-consistency expectations, repeated elements that must match rest of deck, title/body placeholders, exact typography and spacing patterns, internal hyperlinks (slide-to-slide links within the deck, not external URLs — external links are rejected in quarantine)

#### Slide 20. Final combined torture slide (Level 3)

Includes: chart, table, allowed image, multilingual text, rotated text, overlap, transparency, grouping, master/layout dependencies, field behavior, gradient fills, bullet semantics, tab stops — every failure mode in one slide

## 15. Automated Grader Architecture

The grader uses a three-layer inspection model:

- **ECMA-376 schema validation**: validates the `.pptx` against the official RELAX NG / XSD schemas from the ECMA-376 5th Edition standard
- **OOXML structural inspection**: direct XML inspection for semantic verification of object types, relationships, and properties
- **Reference renderer export**: LibreOffice Impress headless for visual export and comparison
- **Deterministic checklist execution engine**

**Canonical source of truth**: OOXML package inspection is authoritative for structural properties. Reference renderer (LibreOffice) export is authoritative for visual appearance. Schema validation runs first and reports a `schema_valid` boolean, but schema-invalid files are NOT automatically rejected (see Stage 0.5).

### 15.1 Major grader stages

#### Stage 0. Ingestion and quarantine

- validate file extension is `.pptx`
- validate file size is within limits (max 100 MB)
- validate ZIP structure (reject ZIP bombs: max decompression ratio 20:1, max decompressed size 500 MB)
- scan for and reject: VBA macros, ActiveX controls, OLE embedded objects, external links, password protection
- validate slide count matches expected tier count
- load manifest and checklist definitions
- ensure benchmark package version match

All quarantine checks run in the same Docker container as the grader.

#### Stage 0.5. ECMA-376 schema validation

- validate the `.pptx` PresentationML content against ECMA-376 Part 1 **Transitional** schemas (RELAX NG from `schemas/ecma-376/relaxng-transitional/`). Transitional is used because virtually all real-world .pptx files target transitional conformance, not strict.
- log all schema violations
- a file that fails schema validation is **not automatically rejected** (many real-world .pptx files have minor schema violations) but schema violations are reported and a `schema_valid` boolean is included in the report

#### Stage 1. Reference renderer export

- open submitted `.pptx` in LibreOffice Impress headless within the canonical Docker environment
- export all slides to PNG at 1920 × 1080
- enforce per-submission timeout (max 120 seconds for open + export)
- if LibreOffice fails to open the file, the submission is marked as `failed` with a retryable error

#### Stage 2. Visual comparison

- compare submitted export to gold export per slide
- compute perceptual similarity score (SSIM) per slide
- also compute exact pixel match (reported as a stretch metric)
- emit diff visualization for debugging
- pass/fail threshold: SSIM ≥ 0.9999 (strict perceptual match; calibration per §22 may only tighten)

#### Stage 3. OOXML structure extraction

- inspect the uploaded `.pptx` ZIP contents directly for structural analysis
- inspect slide XML (PresentationML)
- inspect slide layout and master relationships
- inspect media parts and relationships
- inspect charts, tables, placeholders, and theme references
- validate all embedded media hashes against asset manifest (using two-tier hash model per §8.3)

#### Stage 4. Scene graph normalization

- build normalized scene graph for gold deck
- build normalized scene graph for submission
- ignore unstable non-visible identifiers
- apply semantic equivalence rules (§5.2)
- preserve user-visible type, hierarchy, geometry, and semantics

#### Stage 5. Checklist evaluation

- run slide-level items with severity scoring
- run deck-level items with severity scoring
- run automatic-fail anti-cheat rules
- compute per-tier fidelity scores
- compute aggregate fidelity score

#### Stage 6. Reporting

- generate machine-readable JSON report
- generate optional HTML report
- include slide-by-slide pass/fail, severity, and diff artifacts
- include efficiency metrics
- include repair log
- include environment attestation (Docker image hash, LibreOffice version, font bundle hash, grader version)

## 16. Normalized Scene Graph Model

The grader defines an internal canonical representation for every slide object.

Object fields:

- `type`
- `subtype`
- `parent_group_path`
- `z_index`
- `bbox`
- `rotation`
- `text_runs`
- `font_family`
- `font_size`
- `font_style`
- `line_spacing`
- `paragraph_properties` (bullets, indentation, tab stops)
- `fill` (solid, gradient, pattern)
- `stroke`
- `opacity`
- `shadow`
- `placeholder_type`
- `is_table`
- `table_dimensions` (rows, cols)
- `is_chart`
- `chart_type`
- `chart_data_summary`
- `field_type`
- `asset_hash`
- `crop`
- `crop_to_shape`
- `hyperlink` (internal slide-to-slide links only; external URLs are rejected in quarantine)
- `children`

This representation is extracted from:

- **OOXML package inspection** (primary source for all structural properties: object types, hierarchy, text content, geometry, relationships)
- **Reference renderer export** (supplementary source for render-derived geometry verification: bounding box positions as rendered at 1920×1080)

The gold scene graph is committed to the benchmark package for transparency and regression testing.

## 17. Structural Comparison Rules

### 17.1 Required comparison behavior

The structural comparator requires:

- exact object count per slide for required objects
- correct object type correspondence (semantic, not literal)
- correct group nesting correspondence (semantic equivalence per §5.2)
- correct ordering correspondence where user-visible
- correct placeholder semantics where required by prompt
- correct chart/table native semantics where required by prompt
- exact text content, including multilingual Unicode text
- correct user-visible field semantics where required
- correct bullet and paragraph semantics where specified
- correct line spacing and autofit behavior where specified

### 17.2 Geometry tolerance

Bounding box comparison uses a tolerance of ±2 pixels at export resolution for position and ±2 pixels for dimensions. This accounts for minor implementation differences in shape anchoring.

### 17.3 Normalization rules

The comparator normalizes away:

- generated IDs
- relationship IDs
- other invisible identifiers
- internal serialization order

The comparator does not normalize away:

- user-visible text differences
- geometry differences beyond tolerance
- z-order differences
- missing grouping
- substituting a required native object with a visual approximation

## 18. Anti-Cheat and Fakery Detection

The grader detects attempts to game the benchmark at multiple levels.

### 18.1 Image fakery rules

Flag as automatic failures when:

- a full-slide screenshot is embedded (any single raster ≥ 90% of slide area)
- a large region screenshot is used to fake native layout (any single non-manifest raster ≥ 40% of slide area)
- multiple rasters are tiled to approximate a screenshot composite (combined non-manifest raster area ≥ 60% of slide area)
- rasterized text is used instead of editable text (detected via absence of text runs for visible text content)
- a chart is flattened into an image
- a table is flattened into an image
- thin editable text is overlaid on a raster background to simulate native text (text bbox within 5px of a non-manifest raster bbox)

### 18.2 Allowed image rules

Only images whose embedded content hash matches the asset manifest's two-tier hash model (§8.3) may appear — either the primary hash or an accepted recompression hash. No other re-encoded variants are accepted. PowerPoint's internal thumbnail and preview artifacts are excluded from this check.

Verification methods:

- hash all embedded media parts against the manifest's primary and recompression hash sets
- compare dimensions against manifest-defined expected dimensions per asset
- compare crop values against the gold deck's crop for the specific slide position where the asset appears (within ±2px tolerance measured in export-resolution pixels at 1920×1080) — the same asset may legitimately appear with different crops on different slides
- detect any non-manifest raster objects and measure their area
- compare against gold asset inventory

### 18.3 Hidden object hacks

Flag as failures when:

- incorrect objects are placed fully off-canvas with no corresponding gold off-canvas object
- incorrect content is hidden under opaque objects (z-order analysis reveals covered non-gold objects)
- extra objects beyond gold object count are hidden off-canvas or under opaque layers

### 18.4 Higher-level gaming prevention

The following are tracked and flagged (not automatic failures in v1, but reported):

- submissions that appear to be hard-coded deck synthesis (e.g., near-perfect structural match with zero visual customization from prompt)
- submissions with metadata indicating non-model generation tools
- multiple submissions that are byte-identical or differ only in metadata

For hosted mode, model attestation (§25.7) provides additional gaming prevention.

## 19. Multilingual Requirements

V1 includes:

- English
- Arabic (RTL)
- Japanese (CJK)

The grader verifies:

- exact Unicode text content
- editability as real text (not rasterized, not outlined)
- correct RTL text direction where required
- correct line breaking and layout behavior as represented in the gold deck
- no transliteration
- no outlining
- no rasterization
- correct font fallback (must use bundled fonts from manifest)

## 20. Master, Layout, and Placeholder Requirements

Some slides are intentionally impossible to pass structurally unless the submission uses masters/layouts correctly.

The grader verifies:

- the expected slide layout is referenced in OOXML
- repeated elements come from master/layout where required by the prompt
- required content is placed in the correct placeholder types
- visually correct manual copies do not count as passing when the prompt specifies master/layout usage

Checks:

- compare layout references in OOXML
- inspect placeholder metadata
- compare expected inherited objects versus slide-local objects

## 21. Native Tables, Charts, and Fields

### 21.1 Tables

If the prompt explicitly calls for a table, the grader requires:

- native OOXML table object (not grouped shapes)
- correct row/column count
- correct placement within geometry tolerance
- correct visible styling and content
- correct cell merge behavior where specified

### 21.2 Charts

If the prompt explicitly calls for a chart, the grader requires:

- native OOXML chart object
- correct chart type
- correct visible series/labels/legend behavior
- correct axis formatting where specified

### 21.3 Fields

Where specified, the grader requires native slide-number, date, or footer fields. Static text that visually matches the expected field value is not accepted. The grader verifies field type in OOXML, not just rendered text.

## 22. Visual Comparison Rules

### 22.1 Official rule

- exported submitted slide PNG is compared to exported gold slide PNG using SSIM (Structural Similarity Index)
- pass threshold: SSIM ≥ 0.9999 (this is the v1 default; calibration per §22.3 may only **tighten** this threshold, never loosen it)
- exact pixel match is also computed and reported as a stretch metric but is not the pass/fail criterion

### 22.2 Rationale for perceptual threshold

Exact pixel matching is desirable but may be infeasible due to:

- anti-aliasing differences in text rendering
- sub-pixel positioning differences
- font hinting variations even within a pinned environment
- locale-sensitive layout micro-differences

SSIM ≥ 0.9999 is extremely strict while tolerating renderer-level noise that does not reflect generation quality. The exact detection power (e.g., whether a single misplaced character triggers failure) depends on the character's size and position; the threshold is validated empirically during calibration.

### 22.3 Threshold calibration

Before release, the threshold is calibrated using both positive and negative fixtures:

**Positive calibration (self-export stability):**
- exporting the gold deck 100 times in the pinned environment
- computing SSIM between all export pairs
- verifying self-comparison SSIM is consistently ≥ 0.99999
- if not, investigating and resolving instability before releasing

**Negative calibration (rejection power):**
- creating controlled negative fixtures with known single-element mutations (moved text box, changed font size, wrong color, missing object)
- computing SSIM for each negative fixture against the gold export
- verifying that all negative fixtures score below the pass threshold
- if any negative fixture passes, tightening the SSIM threshold (the v1 visual rule is SSIM-only; if SSIM alone cannot discriminate, the export environment must be tightened, not the scoring rule)

The final threshold is set to maximize the gap between the worst self-export pair and the best negative fixture.

**v1 visual rule freeze**: the official v1 visual pass/fail rule is SSIM-only (no region-aware supplementary checks). If calibration reveals that SSIM alone cannot discriminate between self-exports and negative fixtures, the benchmark must tighten the export environment (not add undocumented supplementary rules). Region-aware checks may be added in a future MAJOR version with a new calibration cycle.

### 22.4 Practical safeguard

If LibreOffice export is not stable enough even in a pinned Docker environment, the benchmark must not silently relax the threshold. It must first solve determinism operationally. The drift canary (§9.6) enforces this.

## 23. Reference Implementation Stack

**Implementation authority**: where this spec defines the contract (what is checked, pass/fail criteria, scoring rules), the reference implementation in `grader/` is authoritative for algorithmic details (exact SSIM parameters, anti-cheat geometry computation methods, opacity thresholds, etc.). The reference implementation's behavior IS the spec for any detail not explicitly defined in this document. Third-party implementations must match the reference implementation's output on the published test fixtures.

The recommended reference grader stack is:

- Python `3.12+`
- `lxml` for OOXML XML inspection and ECMA-376 RELAX NG schema validation
- `zipfile` for `.pptx` package extraction
- `Pillow`, `numpy`, and `scikit-image` for visual comparison (SSIM)
- `pydantic` for normalized scene graph models and API schemas
- `pytest` for regression tests
- LibreOffice Impress headless (pinned version) for slide export to PNG
- Docker for reproducible environment packaging

ECMA-376 schema files (RELAX NG from `schemas/ecma-376/relaxng-transitional/`) are bundled in the grader package for schema validation.

**XML hardening**: all `lxml` usage for untrusted submissions must use a hardened parser:
```python
parser = lxml.etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False,
    huge_tree=False,
)
```
Additionally, XInclude processing (`tree.xinclude()`) must never be called on untrusted content.

No Windows, COM automation, or Microsoft Office dependency exists in the reference stack.

## 24. Automated Test Suite Plan

### 24.1 Positive control tests

- gold deck scores perfect across all tiers
- exported gold images match stored references (SSIM = 1.0)
- normalized gold scene graph is stable across repeated extractions
- baseline scores (§13.4) are within expected ranges

### 24.2 Negative control tests

Create intentionally broken fixtures that each fail a narrow set of checks:

- wrong font
- copied master content instead of inherited layout
- full-slide screenshot cheat
- tiled screenshot composite cheat
- chart replaced by image
- chart replaced by grouped shapes
- table replaced by grouped lines and text
- missing placeholder type
- wrong object count
- wrong z-order
- off-canvas hidden content
- rasterized multilingual text
- incorrect RTL ordering
- wrong slide number field implementation
- text overlaid on raster background
- missing bullet/paragraph semantics
- incorrect line spacing
- wrong gradient fill

### 24.3 Mutation tests

Automated mutators that alter gold deck structure and verify expected checklist failures:

- delete object
- duplicate object
- swap z-order
- change bounding box
- replace text
- flatten group
- convert native chart/table into image or generic shapes
- substitute forbidden font
- change severity of failures and verify correct severity scoring

### 24.4 Determinism tests

- run export 100 times in same environment
- verify self-export stability (SSIM ≥ 0.99999 across all pairs, consistent with §22.3)
- verify identical structural extraction results
- verify report stability

### 24.5 End-to-end tests

- run full grader against passing deck
- run full grader against representative failing fixtures per tier
- verify machine-readable report schema against normative JSON Schema
- verify HTML report rendering
- verify efficiency metrics capture

### 24.6 Hosted service tests

- quarantine evasion tests: submit files with known evasion techniques (renamed extensions, nested ZIP structures, OLE objects hidden in non-standard parts) and verify rejection
- API contract tests: verify all endpoints against OpenAPI spec, including error codes and rate limiting
- container isolation tests: verify that grading container has no network egress, no persistent state, is destroyed after each job, and runs with hardened security profile (rootless, read-only rootfs, dropped capabilities)
- webhook delivery tests: verify callback on completion with correct HMAC signature
- leaderboard consistency tests: verify that leaderboard entries match stored run records
- concurrent submission tests: verify fairness under load

### 24.7 Baseline acceptance bands

- Human expert: fidelity_score in [0.85, 0.98] — if outside, review checklist item difficulty
- Programmatic copy: fidelity_score in [0.90, 1.0] — if below 0.90, review structural comparison rules
- Naive LLM: fidelity_score in [0.20, 0.60] — if above 0.60, the benchmark may be too easy; if below 0.20, prompts may be underspecified

## 25. Hosted Service Architecture

### 25.1 Service overview

The Gloss hosted service accepts `.pptx` submissions via API, grades them in a controlled environment, and publishes verified scores to a public leaderboard. Only hosted-mode scores appear on the official leaderboard.

### 25.2 Submission API

**Base URL**: `https://api.gloss.dev/v1`

#### POST /submissions

Create a new submission.

```json
Request:
{
  "model_id": "string (required) — unique model identifier",
  "model_version": "string (required) — model version string",
  "tier": "integer (required) — 1, 2, or 3",
  "benchmark_version": "string (required) — e.g. gloss-v1.0.0",
  "prompt_variant": "string (optional) — canonical (default), paraphrase-a, paraphrase-b",
  "efficiency_metrics": {
    "generation_strategy": "string (required) — direct | code | hybrid | template-edit",
    "generation_wall_clock_seconds": "number (optional, attested)",
    "generation_token_count": "integer (optional, attested)",
    "generation_cost_usd": "number (optional, attested)",
    "retry_count": "integer (optional, attested)",
    "code_language": "string (optional, for code/hybrid strategies)",
    "code_line_count": "integer (optional, for code/hybrid strategies)"
  },
  "attestation": {
    "method": "string (required) — generation_method description",
    "human_intervention": "boolean (required)",
    "post_processing": "boolean (required)",
    "external_resources_used": "boolean (required)",
    "external_resources_description": "string (required if external_resources_used is true, else omit)"
  }
}

File: multipart upload of .pptx (max 100 MB)

Response (202 Accepted):
{
  "submission_id": "uuid",
  "status": "queued",
  "estimated_wait_seconds": "integer",
  "status_url": "/submissions/{submission_id}"
}
```

#### GET /submissions/{submission_id}

Poll submission status.

```json
Response:
{
  "submission_id": "uuid",
  "status": "queued | grading | completed | failed | rejected",
  "result": {
    "fidelity_score": 0.847,
    "passed_items": 287,
    "total_items": 312,
    "deck_passed": false,
    "eligible": true,
    "anti_cheat_flags": [],
    "repair_triggered": false,
    "tier_scores": { "level_1": 0.95, "level_2": 0.88, "level_3": 0.847 },
    "report_url": "/submissions/{submission_id}/report"
  },
  "error": {
    "code": "string (e.g., quarantine_rejected, grading_timeout, office_crash, invalid_tier)",
    "message": "string",
    "retryable": "boolean"
  }
}
```

**Error codes:**
- `quarantine_rejected`: file failed security scan (not retryable)
- `grading_timeout`: grading exceeded 10-minute limit (retryable)
- `renderer_crash`: LibreOffice crashed or hung during grading (retryable)
- `invalid_tier`: slide count doesn't match requested tier (not retryable)
- `invalid_benchmark_version`: requested version not found or frozen (not retryable)
- `rate_limited`: submission limit exceeded (retryable after wait)

**Webhook support (optional):**

Include `webhook_url` in the POST /submissions request to receive a POST callback when grading completes, instead of polling.

```json
{
  "webhook_url": "https://your-server.com/callback",
  "webhook_secret": "string (used for HMAC-SHA256 signature verification)"
}
```

Webhook delivery:
- HTTP POST to `webhook_url` with JSON body matching the GET /submissions/{id} response
- Header `X-Gloss-Signature`: HMAC-SHA256 hex digest of the raw request body using `webhook_secret` as key
- Retry on 5xx: 3 attempts with exponential backoff (1s, 4s, 16s)
- Timeout: 10 seconds per attempt
- **SSRF prevention**: `webhook_url` must use `https://` scheme only. URLs resolving to private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, ::1), link-local addresses, or non-routable addresses are rejected at registration time. DNS resolution is re-validated at delivery time to prevent DNS rebinding. **HTTP redirects are not followed** — if the webhook endpoint returns 3xx, the delivery is treated as failed.

#### GET /submissions/{submission_id}/report

Download full JSON or HTML report.

#### GET /leaderboard?view={summary|detail}

Query parameters:
- `view`: `summary` (default) groups by `model_id`, showing best version per model. `detail` lists every `(model_id, model_version)` entry.

```json
Response (summary view):
{
  "benchmark_version": "gloss-v1.0.0",
  "updated_at": "ISO 8601",
  "entries": [
    {
      "model_id": "string",
      "model_version": "string",
      "tier_scores": {
        "level_1": {
          "best_score": 0.95,
          "mean_score": 0.93,
          "worst_score": 0.90,
          "submission_count": 3,
          "robustness_score": 0.91
        },
        "level_2": { "...same structure..." },
        "level_3": { "...same structure..." }
      },
      "aggregate_score": 0.82,
      "efficiency": { "...best submission's efficiency metrics..." },
      "submitted_at": "ISO 8601",
      "environment_hash": "string"
    }
  ]
}
```

**Leaderboard publication rule**: all submissions with `eligible == true` are published. There is no qualification gate — every eligible submission appears on the leaderboard.

**Summary view version selection**: the summary view selects the `model_version` with the highest Level 3 `best_score` (or highest available tier if Level 3 was never submitted). If a model has no Level 3 submissions, it uses Level 2, then Level 1.

#### GET /leaderboard/history

Historical leaderboard snapshots for tracking progress over time.

### 25.3 Authentication and rate limiting

- API key authentication (issued per organization)
- Rate limits:
  - 10 submissions per hour per API key
  - 3 submissions per `(model_id, model_version, benchmark_version, prompt_variant)` tuple per 7-day window
  - 100 MB max file size per submission
  - 5 concurrent grading jobs per API key
- Quota:
  - Free tier: 30 submissions per month
  - Paid tier: configurable per agreement
- All rate limits return `429 Too Many Requests` with `Retry-After` header

### 25.4 Grading pipeline (hosted)

```
[Upload] → [Quarantine] → [Queue] → [Worker Dispatch] → [Grade] → [Store] → [Publish]
```

1. **Upload**: receive .pptx, validate size/extension, assign submission_id
2. **Quarantine**: static OOXML scan (same as Stage 0, §15.1), reject malicious files
3. **Queue**: priority queue with per-tenant fairness, estimated wait time
4. **Worker dispatch**: assign to an isolated Docker container
5. **Grade**: execute grader stages 0-6 with per-job timeout (max 10 minutes)
6. **Store**: write immutable run record with full provenance
7. **Publish**: update leaderboard for all submissions with `eligible == true`

### 25.5 Worker isolation model

Each grading job runs in a fresh, ephemeral Docker container:

- container is created from the canonical grading Docker image (§9.7)
- no network egress from the container during grading
- no persistent state between jobs (container is destroyed after grading completes)
- LibreOffice crash recovery: if LibreOffice hangs or crashes, the container is killed after timeout and the job is marked as `failed` with a retryable error
- worker pool auto-scales based on queue depth using standard container orchestration (Kubernetes, ECS, etc.)
- containers are Linux-based — no Windows or Office licensing required at any scale
- security hardening: rootless containers, read-only rootfs, dropped capabilities (`--cap-drop=ALL`), `--security-opt=no-new-privileges`, seccomp profile, CPU/memory/PID limits, no host mounts beyond controlled scratch space

### 25.6 Results storage and provenance

Each grading run produces an immutable record containing:

- submission_id
- benchmark_version (e.g., `gloss-v1.0.0`)
- grader_version (git hash)
- libreoffice_version (exact build string)
- docker_image_hash (canonical Docker image hash)
- font_bundle_hash
- asset_manifest_hash
- grading_started_at / grading_completed_at (UTC)
- environment_attestation (combined hash of all environment parameters)
- full JSON report
- per-slide diff artifacts (stored in object storage, retained for 90 days)

Scores from different environment attestation hashes are comparable only within the same benchmark version.

### 25.7 Model attestation

Leaderboard entries require attestation:

- `method`: free-text description of how the model generated the deck (e.g., "GPT-4o with python-pptx tool use, single-pass generation")
- `human_intervention`: boolean flag; true if any human edited the output
- `post_processing`: boolean flag; true if any programmatic post-processing modified the model output
- `external_resources_used`: boolean flag; true if external URLs, APIs, or renderers were accessed during generation
- `external_resources_description`: free-text description of external resources (required if `external_resources_used` is true)

Submissions with `human_intervention: true` are displayed in a separate leaderboard section ("Human-Assisted").

Attestation is on the honor system in v1. Automated verification (e.g., requiring the model to generate via an API endpoint the service calls directly) is planned for v2 ("Execution Mode").

### 25.7.1 Report and artifact access control

- **Full JSON reports** are visible only to the submitter (authenticated via API key)
- **Leaderboard summary data** (scores, model info, efficiency metrics) is public
- **Per-slide diff artifacts** are visible only to the submitter for 90 days
- **Gold deck exports** and checklist definitions are always public
- Submitters may opt to make their full report public (one-way toggle, not reversible)

### 25.8 Network access policy (hosted mode)

For hosted-mode leaderboard submissions in v1, the generation process is:

- the model receives the prompt, reference images, and asset manifest
- the model produces a .pptx file
- the .pptx file is uploaded to the service

**v1 limitation**: the service cannot enforce generation-time network restrictions because it only grades uploaded artifacts. The attestation model (§25.7) requires disclosure of external resource use. This is an honor-system disclosure, not a technical enforcement.

In v2 ("Execution Mode"), the service will provide a sandboxed generation environment where the model API is called directly and the output is captured without intermediate human, network, or tool access. Only Execution Mode submissions will be marked as "verified" on the leaderboard.

### 25.8.1 Frozen benchmark version submissions

Submissions targeting a frozen benchmark version (§26.4) are rejected with error code `invalid_benchmark_version`. The API returns the list of active benchmark versions in the error response.

### 25.9 Abuse prevention

Service-level abuse prevention (distinct from benchmark anti-cheat in §18):

- **Upload validation**: reject non-ZIP files, oversized files, ZIP bombs, encrypted archives
- **Account reputation**: track submission quality; accounts with repeated malicious submissions are suspended
- **Job kill threshold**: any grading job exceeding 10 minutes or 2 GB RAM is killed
- **Egress policy**: grading containers have no outbound network access
- **Ban/appeal flow**: suspended accounts can appeal via email; response within 5 business days
- **Denial-of-service protection**: standard CDN/WAF in front of the API

### 25.10 Cost model

Infrastructure cost per grading job (estimated):

- Linux Docker container: ~$0.02–0.08 per job (spot instance, 10-minute max, no Windows/Office license)
- Storage: ~$0.01 per job (report + artifacts, 90-day retention)
- Total: ~$0.15–0.35 per submission

Pricing model:

- Free tier: 30 submissions/month (subsidized)
- Organization tier: $1 per submission (covers infra + margin)
- Enterprise: custom pricing with SLA

## 26. Versioning and Governance

### 26.1 Version scheme

`gloss-vMAJOR.MINOR.PATCH`

- **MAJOR**: new slide set, new tiers, scoring model changes, breaking changes. Scores across major versions are not comparable.
- **MINOR**: new prompt variants, documentation clarifications, new informational fields in reports. Scores are comparable within a major version. **MINOR versions MUST NOT add, remove, or re-weight checklist items or change pass/fail thresholds** — any such change requires a MAJOR version bump.
- **PATCH**: grader bug fixes that do not change scores, documentation updates. No score impact. If a bug fix would change scores, it requires a MAJOR version bump (since MINOR must preserve score comparability).

### 26.1.1 Rerun policy

When a PATCH is released, historical submissions are NOT automatically re-graded (since PATCH changes do not affect scores). When a MAJOR version is released, all historical submissions remain scored against their original version. Submitters must explicitly resubmit against the new version.

### 26.2 Grader versioning

The grader is versioned independently. Grader patches are applied to all active benchmark versions. The grader version is recorded in every run record.

### 26.3 Environment versioning

The Docker/LibreOffice environment is versioned independently. If the environment must be updated (e.g., LibreOffice security patches, font updates), the drift canary (§9.6) validates that scores remain stable. If scores remain stable, the environment is updated in-place with a PATCH note. If scores change, a new benchmark MAJOR version is released (because score-affecting changes require a MAJOR bump per §26.1).

### 26.4 Leaderboard freezing

When a new major version is released:

- the previous version's leaderboard is frozen and archived
- no new submissions are accepted for the frozen version after a 30-day grace period
- historical leaderboards remain publicly accessible

### 26.5 Community governance

- **Proposing new slides or checklist items**: public GitHub issue + PR against the benchmark package
- **Reporting false positives**: public GitHub issue with reproduction steps
- **Challenging checklist items**: public discussion thread; resolution requires maintainer review
- **Dispute resolution for hosted-mode scores**: email to disputes@gloss.dev; reviewed within 10 business days; resolution published publicly (anonymized)
- **New version ratification**: major versions require public RFC period (30 days minimum)

## 27. Reporting Format

### 27.1 JSON report

```json
{
  "benchmark_version": "gloss-v1.0.0",
  "grader_version": "abc123",
  "environment_hash": "def456",
  "submission": "submission.pptx",
  "schema_valid": true,
  "repair_triggered": false,
  "grading_duration_seconds": 23.4,
  "fidelity_score": 0.847,
  "passed_items": 287,
  "total_items": 312,
  "deck_passed": false,
  "eligible": true,
  "tier_scores": {
    "level_1": { "fidelity_score": 0.95, "passed": 68, "total": 72 },
    "level_2": { "fidelity_score": 0.88, "passed": 165, "total": 188 },
    "level_3": { "fidelity_score": 0.847, "passed": 287, "total": 312 }
  },
  "verified_metrics": {
    "submission_file_size_bytes": 4521000,
    "grading_duration_seconds": 23.4,
    "schema_valid": true
  },
  "attested_metrics": {
    "generation_strategy": "code",
    "generation_wall_clock_seconds": 45.2,
    "generation_token_count": 128000,
    "generation_cost_usd": 1.50,
    "retry_count": 0,
    "code_language": "python-pptx",
    "code_line_count": 347
  },
  "prompt_variant": "canonical",
  "attestation": {
    "method": "GPT-4o with python-pptx tool use",
    "human_intervention": false,
    "post_processing": false,
    "external_resources_used": false
  },
  "anti_cheat_flags": [],
  "slides": [
    {
      "slide": 1,
      "tier": 1,
      "visual_ssim": 0.99997,
      "visual_pixel_exact": false,
      "passed_items": 14,
      "total_items": 16,
      "items": [
        {
          "id": "slide-01.visual-ssim",
          "passed": true,
          "severity": "major",
          "source_of_truth": "render",
          "details": "SSIM: 0.99997 (threshold: 0.9999)"
        },
        {
          "id": "slide-01.pixel-exact",
          "passed": false,
          "severity": "informational",
          "source_of_truth": "render",
          "details": "Stretch metric: 47 differing pixels (informational, excluded from fidelity_score)"
        }
      ]
    }
  ],
  "deck_items": [
    {
      "id": "deck.master-reuse",
      "passed": false,
      "severity": "critical",
      "source_of_truth": "ooxml",
      "details": "Slide 6 uses slide-level copy instead of layout inheritance"
    }
  ]
}
```

### 27.2 Optional HTML report

Useful for developers tuning against the benchmark:

- per-slide reference image
- per-slide submission export
- visual diff heatmap with SSIM score
- failed checklist items grouped by severity
- structural mismatch summaries
- efficiency metrics dashboard
- environment attestation details

## 28. Development Phases

### Phase 0. Repository bootstrap

Deliverables: benchmark package skeleton, grader package skeleton, service API spec (OpenAPI), environment documentation, font and asset manifest formats, libre font selection

### Phase 1. Prompt design and validation (prompt-first)

Deliverables: deck-level prompt, per-slide prompt/spec files, paraphrased variants. Prompts are designed BEFORE the gold deck per §13.1. Independent author validation confirms prompt convergence (≥80% structural similarity).

### Phase 2. Gold deck design matrix

Deliverables: final slide matrix for 20 slides with tier assignments, master/layout design, asset list, multilingual content plan, checklist category map, severity assignments

### Phase 3. Gold deck authoring

Deliverables: gold `.pptx` authored in LibreOffice Impress from validated prompts, bundled libre fonts, approved asset mirrors with licenses, exported reference PNGs from canonical Docker environment, ECMA-376 schema validation pass

### Phase 4. Scene graph extraction

Deliverables: OOXML parser, ECMA-376 schema validator, normalized scene graph schema with semantic equivalence rules, saved gold scene graph fixtures

### Phase 5. Visual comparator and anti-cheat rules

Deliverables: SSIM comparator with threshold calibration, media hash inventory checker, full-slide and tiled-raster cheat detection, off-canvas and hidden-content checks, raster-area calculations

### Phase 6. Checklist engine

Deliverables: declarative checklist schema with severity tiers, evaluator runtime, slide-level and deck-level item execution, per-tier scoring, aggregate fidelity score computation

### Phase 7. Grader test suite and baseline calibration

Deliverables: positive fixtures, negative fixtures (including new anti-cheat cases), mutation harness, determinism tests (100-run export stability), **baseline calibration** (§13.4) — human expert, programmatic copy, and naive LLM baselines scored using the now-complete grading pipeline, verified against acceptance bands (§24.7)

### Phase 8. Hosted service MVP

Deliverables: submission API, quarantine pipeline, worker container automation, results storage, basic leaderboard, API key management, rate limiting

### Phase 9. Public release and leaderboard

Deliverables: versioned benchmark release, grader CLI, benchmark README, submission instructions, report schema, leaderboard website, drift canary automation, governance documentation

## 29. Acceptance Criteria for v1

`Gloss v1` is complete when all of the following are true:

- benchmark package is fully public and self-contained
- all bundled fonts are libre/open-source with clear licensing
- gold deck exists and exports stable reference images in the canonical Docker environment (SSIM ≥ 0.99999 across 100 repeated exports, consistent with §22.3)
- baseline calibration scores exist for human expert, programmatic copy, and naive LLM
- difficulty tiers (Level 1/2/3) are defined with distinct slide assignments
- grader runs fully automatically in the canonical Docker environment (Linux + LibreOffice)
- gold deck scores perfect across all tiers
- representative broken fixtures fail the correct checklist items with correct severity
- image fakery, tiled composite, text-on-raster, and structural cheat cases are caught
- multilingual, master/layout, table, chart, field, grouping, z-order, bullet/paragraph, and spacing checks are implemented
- fidelity score output is deterministic
- severity-weighted scoring produces expected results
- no human review is required anywhere in the grading loop
- drift canary is operational
- hosted service API accepts submissions and returns graded results
- leaderboard displays verified scores with provenance
- quarantine pipeline rejects malicious .pptx files (verified with evasion test suite)
- worker isolation prevents cross-job contamination
- version comparability rules are documented and enforced by the API
- leaderboard correctly handles single-tier submissions, multi-submission windows, and model identity grouping
- dispute resolution process is documented and has a designated maintainer
- normative JSON Schemas are published for checklist items and report format

## 30. Risks and Mitigations

### Risk 1. LibreOffice export instability

Mitigation: pin LibreOffice version and Docker image, bundle libre metric-compatible fonts, run 100-export determinism test before releasing, deploy drift canary for ongoing monitoring, use SSIM threshold instead of exact pixel match as primary criterion

### Risk 2. Structural equivalence is harder than visual equivalence

Mitigation: define semantic equivalence classes early (§5.2), build comparison rules from gold deck outward, start with a pilot subset of slides, accept that structural comparison is about semantic correctness not implementation isomorphism

### Risk 3. Too many checks become unmaintainable

Mitigation: use declarative checklist format with severity tiers, generate portions of checklist from gold structure, keep item phrasing concise and machine-verifiable

### Risk 4. Gold deck accidentally contains ambiguous implementation choices

Mitigation: use prompt review process (§13.1 step 6), ensure slides that require native constructs explicitly say so in prompts, run baseline calibration to detect unreasonable checklist items

### Risk 5. Labs overfit the public benchmark

Mitigation: acceptable in v1; hidden suites and prompt variations can be introduced in v2; robustness score across prompt variants partially mitigates this; difficulty tiers ensure basic capabilities are tested separately from advanced ones

### Risk 6. LibreOffice rendering differs from PowerPoint

LibreOffice renders some ECMA-376 features differently from PowerPoint, especially charts, complex text layout, and gradient fills. This means the benchmark scores reflect LibreOffice rendering fidelity, not PowerPoint fidelity.

Mitigation: the v1 slide matrix (§14) deliberately avoids features where LibreOffice fidelity is poor. Renderer-limited features use split checklist items (§9.3.1): structural checks via OOXML (critical) and visual checks via renderer (minor). The optional PowerPoint fidelity score (§9.8) is available for teams with PowerPoint access. Aspose.Slides may be evaluated as a higher-fidelity renderer in future versions.

### Risk 7. Font licensing blocks public distribution

Mitigation: use only libre/open-source fonts from the bundled set (Liberation, Noto, Noto CJK, Carlito, Caladea — as specified in the Dockerfile §9.7), verify licenses before inclusion, include LICENSE file in font bundle

### Risk 8. Hosted service cost exceeds revenue

Mitigation: start with a modest free tier (30 submissions/month), charge per submission for higher volume, use spot instances for worker containers, auto-scale down during low demand

### Risk 9. Malicious .pptx submissions compromise grading infrastructure

Mitigation: quarantine pipeline (§15.1 Stage 0), ephemeral hardened Docker containers (§25.5) with rootless execution, read-only rootfs, and dropped capabilities, XML hardening in lxml (§23), no network egress during grading, per-job resource caps, account reputation system

### Risk 10. Leaderboard integrity (gaming, false attestation)

Mitigation: attestation model (§25.7) for v1, execution mode (service-controlled generation) planned for v2, all submissions recorded (no cherry-picking), separate leaderboard for human-assisted submissions

### Risk 11. Anti-cheat false positives

The heuristic anti-cheat rules (§18) may flag legitimate submissions. For example, the text-on-raster detection rule may fire on slides with captions positioned near allowed images.

Mitigation: calibrate every anti-cheat heuristic against the full set of passing and failing fixtures before release. Publish the expected false-positive rate per rule. Allow submitters to dispute anti-cheat flags via the governance process (§26.5). Anti-cheat flags do not suppress leaderboard publication — they zero affected slide scores, so the impact is proportional and visible.

### Risk 12. Score churn from environment/grader changes

Even within a frozen benchmark version, grader patches or OS security updates could subtly change scores.

Mitigation: the drift canary (§9.6) detects environment changes. Grader PATCH versions must not change scores (§26.1). If a bug fix would change scores, it requires a MAJOR version bump (since MINOR must preserve comparability). The rerun policy (§26.1.1) ensures historical scores are never silently invalidated.

## 31. Recommended Immediate Next Steps

**Phase A — Contract publication (encode the locked decisions into implementable schemas):**

1. Publish normative JSON Schemas for checklist items and report format (encoding the rules in §§10, 12, 27).
2. Publish OpenAPI spec for the hosted-service API (encoding the contracts in §25).
3. Publish the asset manifest schema with recompression hash pre-computation (encoding §8.3).
4. Validate all schemas against the spec examples to catch inconsistencies before implementation begins.

**Phase B — Benchmark construction:**

6. Validate the bundled font set (Liberation, Noto, Noto CJK, Carlito, Caladea — as specified in the Dockerfile §9.7).
7. **Design and validate prompts** for the v1 slide matrix (prompt-first per §13.1). Run independent author convergence tests.
8. Freeze the v1 slide matrix with tier assignments and checklist category taxonomy.
9. Build and pin the canonical Docker image (LibreOffice version + fonts).
10. Define the benchmark directory structure and manifest schemas.
11. Author a 5-slide Level 1 pilot deck from validated prompts in LibreOffice Impress.
12. Build the export and scene-graph extraction pipeline against the pilot.
13. Calibrate the SSIM threshold using 100 repeated gold deck exports + negative fixtures.
14. Validate anti-cheat rules on intentionally broken pilot decks.
15. Expand to Level 2 and Level 3 only after determinism and grading logic are stable.

**Phase C — Calibration and release:**

16. Run baseline calibration and publish baseline scores (requires complete grading pipeline from Phase B).
17. Validate baselines against acceptance bands (§24.7); iterate on checklist or thresholds if needed.

**Phase D — Service deployment:**

18. Build the hosted service API and quarantine pipeline.
19. Deploy worker container automation with isolation and drift canary.
20. Deploy the leaderboard.

## 32. Future Extensions

Not part of v1, but natural follow-ons:

- Execution Mode: service calls model API directly for verified generation
- hidden holdout suites
- realistic multi-slide story decks
- animation and transition benchmarks
- edit-in-place tasks (modify an existing deck per instructions)
- cross-prompt robustness benchmarks with adversarial prompts
- cross-renderer compatibility checks
- deck regeneration after partial prompt changes
- community-contributed slide challenges
- multi-model tournament mode
