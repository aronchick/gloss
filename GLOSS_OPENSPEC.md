# Gloss v1 OpenSpec

Status: Draft — adversarial review remediation in progress; not freeze-ready
Scope: Public benchmark, automated grading suite, and hosted evaluation service for slide generation fidelity  
Primary artifact: A fully public, machine-graded PowerPoint benchmark inspired by the ACID browser tests

## 1. Summary

`Gloss` is a benchmark for grading whether a submitted `.pptx` artifact conforms to natural-language prompt requirements while preserving both:

- rendered visual fidelity under a fixed reference renderer (LibreOffice Impress headless)
- user-visible structural fidelity inside the PowerPoint deck

The artifact test exercises two properties in combination:

1. **Prompt conformance**: does the artifact encode the requested PowerPoint constructs?
2. **Output fidelity**: does the artifact match the published reference images visually and satisfy
   the frozen item-scoped structural assertions?

V1 may record a submitter's attested model attribution, but artifact-only grading cannot establish
that the named model performed the generation. Model capability claims require v2 Execution Mode.

Reference images supplement the natural-language prompt and resolve visual details the prompt leaves
underspecified. They are authoritative only for assertions explicitly marked
`provenance.kind: reference_image`; they never create structural requirements from gold OOXML.

The benchmark is intentionally gameable in v1. The goal is not secrecy. The goal is to create a brutal, public, tunable target that forces frontier models to get meaningfully better at producing real slides instead of image-backed fakes.

`Gloss` ships in three difficulty tiers:

- **Level 1** (5 slides): basic constructs — placeholders, images, simple tables, master usage
- **Level 2** (12 slides): intermediate — multilingual text, charts, grouping, overlap, z-order
- **Level 3** (20 slides): full torture — all failure modes combined, deep nesting, composite stress

Each tier is scored independently. A submission targets a specific tier and is graded only on that tier's slides. The leaderboard tracks per-tier scores. A **full-deck perfect pass** requires submitting for Level 3 and achieving `deck_passed == true` (see §10.1 for the precise definition) — this is the ceiling achievement, not a prerequisite for leaderboard presence.

`Gloss` is available in two modes:

- **Local mode**: download the benchmark package and run the grader locally using Docker (Linux/macOS/Windows). Scores are self-reported and are not official leaderboard results.
- **Hosted mode**: submit via API to the Gloss service, which grades in the canonical controlled environment and publishes **grading-verified** scores to the official leaderboard.

Submissions are graded only from the final submitted `.pptx`. No tool traces, reasoning logs, or intermediate artifacts affect the score.

### 1.1 Verification terminology

Gloss distinguishes three claims that MUST NOT be collapsed into a single unlabeled
"verified" badge:

- **Grading-verified**: the uploaded artifact was quarantined, rendered, inspected, and scored by
  the official hosted service in an attested canonical environment. Every official v1
  leaderboard score has this property.
- **Generation-attested**: the submitter disclosed the generation method, intervention, post-
  processing, and external-resource use. These fields are self-reported in v1.
- **Generation-verified**: the service controlled the generation execution itself. This is out of
  scope for v1 and reserved for v2 Execution Mode.

Throughout this specification, an unqualified "verified score" means **grading-verified**. The v1
UI and API MUST label generation claims as attested and MUST NOT imply that v1 verifies model
identity, generation method, absence of human intervention, or generation-time network behavior.

Gloss v1 verifies **artifact conformance only**. Every public submission, campaign, robustness,
and leaderboard result MUST carry the exact label
`grading-verified artifact score; generation-attested`. The service, API, documentation, and UI
MUST NOT state or imply that a named model generated, passed, or independently reproduced the
benchmark. Model and generation fields are attribution metadata supplied by the submitter.

Every normative report also carries `grading_mode: local | hosted`. A local submission report uses
the exact label `local artifact score; self-reported`, is permanently `eligible: false`, has
`campaign_contribution: 0.0`, null hosted identity/campaign/slot fields, and is never published by the
leaderboard service even when all artifact checks pass. Its `disqualification_state` is
`non_official_local` with reason `local_mode`, distinguishing publication ineligibility from an
artifact defect. Only `grading_mode: hosted` submission reports may use the public v1 verification
label or become eligible.

Because the gold artifact is public, the release manifest publishes both its byte SHA-256 and a
`canonical_package_hash_v1` computed by the normative §18.4.2 profile. A submission matching either
hash is completed-ineligible with `gold_artifact_copy`
and is not leaderboard-eligible. This duplicate guard does not verify generation and cannot prevent
a submitter from making a semantically inert change to the public gold.

## 2. Product Principles

### 2.1 Core principles

- Public by default: gold deck, prompts/specs, assets, checklist items, and grader logic are all public in v1.
- Deterministic by design: rendering, fonts, assets, slide size, and grading environment are fixed.
- Native slides only: a visually correct screenshot hack is a failure.
- Machine-graded only: no human judgment may change an individual score. Administrative dispute
  review may reproduce a run or identify a grader defect, but any score-affecting correction must
  follow the versioning policy and must never mutate an immutable run record in place.
- User-visible equivalence: ignore unstable non-visible identifiers, but require equivalent visible and structural fidelity.
- Single benchmark deck first: keep v1 operationally simple and hard enough to matter.
- Progressive difficulty: Level 1/2/3 tiers track industry progress over time.
- Prompt-first evaluation: prompt-derived structural requirements are frozen before gold; published
  reference images later become authoritative only for explicitly provenance-linked visual assertions.
- Standards-based: targets ECMA-376 (Office Open XML), not any single renderer. Like the ACID browser tests targeted W3C standards, not one browser.
- Cross-platform by design: the entire benchmark runs on Linux in Docker. No Windows or Microsoft Office dependency.
- Prompts are designed artifacts: prompts are authored and validated independently before the gold deck, not reverse-engineered from it.

### 2.2 What this benchmark is testing

The intended generation task asks a generator to create an artifact that demonstrates:

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
- whether the attributed generator is useful for ordinary business decks (see §2.4)

### 2.4 External validity disclaimer

Gloss v1 is a ceiling test using deliberately hostile torture slides, not a measure of general slide-generation utility. A low artifact score does not prove the attributed generator is useless in production. A high artifact score—especially on a public gold—does not prove the attributed generator can handle novel slide generation. Realistic multi-slide story decks and generation-verified execution are planned for v2.

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
- Structural grading: ECMA-376 Part 1 Transitional XSD validation plus item-scoped assertion
  evaluation against the content-addressed MCE-resolved OOXML package; gold structure is a control
  fixture, not an oracle
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

For the intended task, a generator receives:

- a deck-level prompt describing global design system and cross-slide consistency expectations
- a per-slide natural-language prompt/spec (the primary input)
- a reference image exported from the gold deck (supplementary visual guidance)
- a list of allowed external assets, including mirrored local copies and fixed URLs

The graded PowerPoint artifact must:

- satisfy every applicable frozen scored assertion derived from the published task inputs
- render with high visual fidelity to the published reference images under the reference renderer
- use native PowerPoint constructs where the prompt/spec requires them
- achieve the structural semantics required by the item-scoped assertion inventory

Every scored assertion has exactly one authoritative provenance kind:

- `prompt`: an atomic requirement transcribed from the deck or slide prompt before gold authoring
- `reference_image`: a visual assertion located by reference-image hash plus slide/region coordinates
- `asset_manifest`: an asset identity, licensing, or allowed-usage assertion

The provenance kind is schema-constrained to the property being asserted. The compatibility matrix
is normative and fail-closed:

| Provenance kind | May prove | MUST NOT prove |
|---|---|---|
| `prompt` | Any atomic visual, textual, structural, editability, native-object, relationship, master/layout, field, or asset-usage requirement stated by the cited prompt bytes | A requirement absent from the cited prompt locator |
| `reference_image` | Only properties directly observable in the cited pixels: visible glyph appearance, color, geometry, crop, overlap, z-order as rendered, spacing, and other rendered appearance | Exact Unicode/text semantics; native chart/table/field/placeholder type; editability; grouping; master/layout inheritance; theme semantics; relationship targets; hidden/off-canvas content; source font identity where pixels do not distinguish it; any other OOXML structure |
| `asset_manifest` | Asset identity, exact allowed bytes/hash, media type, intrinsic pixel dimensions, license, canonical URL, and explicitly declared allowed/required use | Placement/rendered dimensions, crop, z-order, visual composition, text, editability, native object type, master/layout/theme semantics, or any property not present in the cited manifest entry |

A `reference_image` assertion therefore uses `source_of_truth: render`; an
`asset_manifest` assertion may use OOXML inspection only to prove embedded-media identity or declared
usage. Any assertion whose kind, source of truth, verification method, or expectation falls outside
this matrix is schema-invalid and prevents the assertion inventory and release from freezing. A
reviewer cannot waive the matrix. If one property needs evidence from two kinds, it is split into two
independently scored atomic assertions; provenance is never expressed as an unordered union.

The gold `.pptx` package and extracted gold scene graph are control fixtures, never requirement
sources. They cannot create, waive, or strengthen a scored assertion. A gold-derived expected value is
scoreable only after an independent reviewer traces it to one of the three published provenance kinds
above and freezes that assertion before release.

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

V1 detects only observable repair signals: a LibreOffice recovery diagnostic, a renderer warning
classified in the frozen release manifest, a non-zero renderer exit, or a saved recovery artifact.
V1 does **not** claim to detect every in-memory or silent LibreOffice normalization.

When an observable repair signal occurs:

- **Visual scoring** (Stage 2) renders the content-addressed MCE-resolved package
- **Structural scoring** (Stage 3) inspects that same MCE-resolved package
- **Schema validation** (Stage 0.5) validates that same package before rendering
- the original upload is retained only for provenance, quarantine evidence, and duplicate detection

A submission that triggers an observable repair signal is flagged with `repair_triggered: true`, and `deck_passed` is set to `false` (a repaired deck cannot achieve a perfect pass). The event and matched signal are logged in the report. `schema_validation_performed == false`, `schema_valid == false`, an unclassified renderer warning, or an observable repair signal also forces `verification_complete == false`, `eligible == false`, and `deck_passed == false`.

## 5. Scope of Structural Fidelity

Structural fidelity in v1 means satisfaction of the frozen item-scoped structural assertions, not
literal isomorphism with the gold deck's internal representation.

### 5.1 Structural properties that must match (semantically)

- slide ordering
- slide count
- layout/master usage where required by the prompt
- placeholder usage and placeholder type where required by the prompt
- object type (a table must be a table, a chart must be a chart)
- grouping structure at the depth required by the prompt-derived assertion; nesting may vary only for items whose declared equivalence policy permits it
- z-order (user-visible stacking order must match)
- object count where an assertion requires it (within a tolerance of ±0 for required objects; optional decorative objects may vary only when the item declares a bounded optional count and deterministic matching rule)
- text content (exact Unicode match)
- text editability
- script and directionality behavior
- image usage and source legality (strict hash match against manifest)
- chart presence, chart object type, and visible data representation where required
- table presence and table object type where required
- native field usage where required by the prompt
- geometry and placement where constrained by a prompt- or reference-image-sourced assertion (within defined tolerance)
- crop behavior where constrained by a prompt- or reference-image-sourced assertion
- overlap relationships where constrained by an assertion
- on-canvas and intentional off-canvas placement where constrained by an assertion
- theme/master-driven versus per-slide override behavior where required by the prompt

### 5.2 Semantic equivalence rules

The comparator recognizes that multiple valid PowerPoint implementations can produce the same user-visible result. Equivalence is item-scoped, not global: every checklist item MUST declare the property it constrains and its matching/equivalence policy. A permissive policy never overrides an explicit prompt requirement. Subject to that declaration, the following may be treated as equivalent:

- Different internal group nesting that produces the same visual hierarchy and z-order, except when group depth or membership is the tested property
- Different XML serialization order that produces the same rendered output
- Different shape implementation (e.g., freeform vs. preset geometry) that produces visually identical geometry within tolerance, except when a native/preset shape type is required
- Different color specification methods (theme reference vs. explicit RGB) that produce the same rendered color, except when theme inheritance or local override behavior is required

Unmatched objects fail unless the applicable item marks them optional, supplies a bounded count, and defines deterministic matcher tie-break rules. The comparator MUST NOT silently choose the pairing that maximizes score.

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

Each tier is scored independently. A leaderboard attribution profile may include separately completed
campaign results for:

- Level 1 score (foundation)
- Level 2 score (intermediate)
- Level 3 score (full torture)
- Aggregate weighted score

A submitter may open a separately bound campaign for any tier.

The inclusion algorithm is exact. Let `S1 = {1..5}`, `S2 = {1..12}`, and `S3 = {1..20}`. For a
campaign targeting tier `T`, the evaluator constructs one immutable ordered item set before reading
submission results:

1. include an item only when `item.tier <= T`;
2. for `scope: slide`, additionally require `item.slide in ST` and require the checklist validator to
   prove that `item.tier` equals the minimum tier containing that slide;
3. for `scope: deck`, evaluate the item against exactly `ST`; any resolved affected-slide list is
   intersected with `ST` before propagation;
4. order included items by UTF-8 byte order of `item.id`, reject duplicate IDs/assertion IDs, and
   compute totals only from this frozen set; and
5. include informational items in diagnostics and counts explicitly labeled informational, but omit
   their zero weights from the score denominator and perfect-pass predicate.

No runtime object match, gold content, failure outcome, or optional field may change item
applicability. The three tier-item-set hashes are published in the scoring manifest and tested against
the complete checklist bundle.

## 7. Proposed Benchmark Package

The public package ships as a versioned directory with a stable layout.

```text
gloss-v1/
  README.md
  SPEC.md
  VERSION
  CHANGELOG.md
  RELEASE_KEYS.json
  Dockerfile                    # canonical grading environment
  docker-compose.yaml
  environment/
    libreoffice-version.md
    docker-image.md
    font-install.md
    drift-canary.md
  schemas/
    ecma-376/                    # ECMA-376 5th Edition schemas
      xsd-transitional/
    checklist-item.schema.json
    report.schema.json
    report-semantic-projection.schema.json
    submission-status.schema.json
    prompt-requirements.schema.json
    scored-assertion.schema.json
    scored-assertion-inventory.schema.json
    scoring-manifest.schema.json
    release-index.schema.json
    release-index-chain.schema.json
    release-keys.schema.json
    runtime-freeze-input.schema.json
    environment-attestation.schema.json
    grader-source-tree-profile.schema.json
    grader-source-tree-profile-v1.json
    grader-source-tree-manifest.schema.json
    generation-profile.schema.json
    control-handoff.schema.json
    gold-evidence.schema.json
    export-determinism-evidence.schema.json
    scene-graph.schema.json
    baseline-evidence.schema.json
    mce-profile.schema.json
    mce-profile-v1.json
    schema-root-map.schema.json
    schema-root-map-v1.json
    canonical-package-hash-profile.schema.json
    canonical-package-hash-v1.json
    package-hash-fixture.schema.json
  benchmark/
    scoring-manifest.json
    release-index.json
    release-index-chain.json    # required above sequence 1; optional for legacy genesis
    grader-source-tree-manifest.json
    environment-attestation.json
    gold-evidence.json
    export-determinism-evidence.json
    requirements/
      prompt-requirements.json
      scored-assertion-inventory.json
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
      index.json
      positive/
      single-fault-negative/
      mutations/
      mce/
      gold-duplicate/
      quarantine-handoff/
      verdict-replay/
      opc/
      report-semantic-projection/
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
- optional paraphrased prompt variants that all target the same published reference images, asset
  manifest, and assertion semantics

Prompt design principles:

- no intentional ambiguity in canonical prompts
- no hidden constraints
- no attempt to trap the model on underspecified details
- canonical prompts are authored and independently convergence-tested before the gold deck; the
  gold deck is then authored from those frozen prompts

The reference image is a published task input and may resolve visual details that the prompt leaves
unspecified (for example an exact color shade). The prompt takes precedence for any conflict. The
scored-assertion inventory records whether each expectation comes from `prompt`, `reference_image`,
or `asset_manifest`, including an exact prompt citation or reference-image hash and region. Gold OOXML
is never a fourth provenance kind.

### 8.2 Prompt robustness protocol

Paraphrased variants are scored as follows:

- The canonical prompt set is the official benchmark input
- Each prompt variant is a separate single-tier campaign scored against the same published reference
  images, asset manifest, and scored-assertion inventory
- A `robustness_group` score is computed per tier as the minimum official mean of its exactly three
  child campaigns (`canonical`, `paraphrase-a`, `paraphrase-b`) in one scoring cohort and window
- A group produces an official robustness score only after all three child campaigns complete their
  three slots. Partial groups remain provisional and unranked
- The leaderboard displays each canonical campaign score and the parent robustness score when complete
- Mean and standard deviation across variants are also displayed when available

### 8.3 Asset model

Each explicitly allowed external image must have:

- a fixed canonical URL if relevant
- a mirrored local copy in the benchmark package
- a stable asset ID
- content hash (SHA-256)
- usage constraints if needed

V1 accepts only the primary SHA-256 bytes published in the manifest. Gold-derived recompression
hashes are not accepted because they privilege one authoring path and make the gold define its own
oracle. A future MAJOR version may publish a deterministic, versioned encoder matrix and accept its
precomputed outputs. PowerPoint or another tool that recompresses an asset must be configured to
preserve the manifest bytes for v1.

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
- it supports headless batch export to PDF for rasterization by the pinned Poppler build
- it has no COM automation fragility, no modal dialogs, no GUI dependency

ECMA-376 schema validation using the bundled Part 1 Transitional XSD schema set provides structural validation that is independent of any renderer. RELAX NG validation is out of scope for v1; publishing two nominally normative schema paths without identical processing semantics would make conformance ambiguous.

### 9.3 Rendering fidelity expectations

LibreOffice differs from PowerPoint, but v1 does not publish unmeasured fidelity percentages. The
only normative visual expectation is conformance to the frozen canonical LibreOffice export. Any
renderer comparison is a dated, descriptive experiment with its corpus and method published. V1
excludes SmartArt, animations, and 3D effects.

### 9.3.1 Renderer-limited features

Some v1 slide features (charts, gradients, shadows, autofit, complex text layout) may render differently in LibreOffice than in PowerPoint. For these features, checklist items are **split into structural and visual checks**:

- **Structural checks** (source_of_truth: `ooxml`): verify the correct OOXML construct exists in the XML (e.g., a native chart element, correct gradient definition). These pass/fail based on XML inspection, independent of rendering.
- **Visual checks** (source_of_truth: `render`): verify the rendered output matches the gold export. These may have lower SSIM scores due to renderer differences, not model errors.

This split ensures models get credit for producing correct OOXML structures even when the reference renderer's visual output differs from PowerPoint. Structural checks are weighted as `critical`; visual checks for renderer-limited features are weighted as `minor`.

### 9.4 Environment freeze requirements

Before grading is enabled, the benchmark must freeze:

- one official platform (`linux/amd64`) and an OCI image digest, including a digest-pinned base image
- LibreOffice version (exact build string, e.g., `libreoffice-7.6.4.1`)
- Poppler, Pillow, NumPy, scikit-image, lxml, Python, and grader versions
- exact export commands, flags, color mode, PNG encoding parameters, and export resolution
- a fresh isolated LibreOffice user profile for every export; command templates serialize its
  runtime `file://` URI as the literal token `file://<isolated-temporary-profile>`
- slide size
- font installation set and file hashes (libre metric-compatible fonts)
- a frozen Fontconfig configuration whose discovered font-file set equals the font manifest exactly;
  extra dependency, host, or fallback font files fail the environment build
- locale settings (`en_US.UTF-8`)
- timezone (`UTC`)
- reference datetime for date/time fields: `2025-01-01T00:00:00Z`
- `libfaketime` build/version and wrapper configuration used to supply that datetime to LibreOffice
  and every grader subprocess
- the final SSIM algorithm profile and numeric threshold

The release publishes a content-addressed scoring manifest containing every value above plus the
benchmark, prompt, checklist, schema, asset, font, MCE-profile, gold, and 100-run export-determinism
evidence hashes. The scoring-manifest hash is present in every report and defines the comparison
cohort.

`scoring-manifest.json` is serialized as RFC 8785 canonical JSON and intentionally contains neither
its own hash nor `scoring_cohort_id`; this avoids a self-hash cycle. A separately signed
`release-index.json` records the manifest hash, the three-field cohort descriptor below, its derived
ID, benchmark version, single release state, chain metadata, and release signature. Consumers recompute both hashes
before trusting the index. The signature is Ed25519 over RFC 8785 canonical JSON with the `signatures`
field omitted; each signature object contains `key_id` and base64 signature bytes. Authorized public
keys and validity windows live in version-controlled `RELEASE_KEYS.json`, and a release requires at
least one non-revoked key valid at `issued_at` and `effective_at`.

For API and storage interoperability, `scoring_cohort_id` is
`sha256:<hex(SHA-256(RFC8785-JCS(cohort_descriptor)))>`, where `cohort_descriptor` is exactly:

```json
{
  "schema_version": "1.0",
  "scoring_manifest_sha256": "sha256:...",
  "grader_source_tree_sha256": "sha256:...",
  "environment_attestation_sha256": "sha256:..."
}
```

Every report and public row carries the ID and all three component hashes. Comparability and
aggregation require exact equality of all four fields; the service recomputes the ID and rejects a
mismatch. A benchmark version string alone never defines a scoring cohort.

#### 9.4.1 Grader source-tree construction profile

The release publishes the algorithm `schemas/grader-source-tree-profile-v1.json`, validated by
`schemas/grader-source-tree-profile.schema.json`, and a release-specific
`grader-source-tree-manifest.json`, validated by
`schemas/grader-source-tree-manifest.schema.json`. `grader_source_tree_sha256` is the SHA-256 of RFC
8785 canonical JSON for exactly the release manifest (the manifest contains no self-hash). It binds
the profile ID/hash and contains:

- `schema_version`, `manifest_id`, `source_tree_profile_sha256`, and the fixed root
  `gloss-v1/grader`;
- one entry for every release source, resource, lock, build, and test file under that root, with a
  root-relative NFC-normalized POSIX path, byte length, exact-byte SHA-256, and executable boolean;
- entries sorted by Unicode code-point order of `path`, with duplicate, case-fold-colliding,
  non-NFC, absolute, empty-segment, `.`/`..`, backslash, NUL, symlink, device, socket, and hard-link
  entries rejected; and
- no implicit ignore rules. Generated caches/build output are absent only because the frozen profile
  enumerates the complete allowed path set; an extra or missing filesystem entry fails verification.

File contents are hashed byte-for-byte; line endings, encoding, modes represented by the executable
flag, and empty files are not normalized away. A source archive is accepted only after reconstructing
and matching this exact inventory. The scoring manifest binds the profile hash, manifest hash, and
resulting tree identity. The repository does not create a release manifest until the source tree is
actually frozen.

The frozen package carries the reconstruction input as
`benchmark/grader-source-tree.tar`. It is a tar archive whose regular-file members are rooted at
`gloss-v1/grader/`; container ordering, timestamps, owners, and compression are not identities.
The verifier rejects absolute/dot/non-NFC/case-colliding paths, links, special files, duplicate or
unmanifested members, missing members, byte-length/hash drift, and execute-bit drift before accepting
the signed cohort. A repository checkout may instead supply the exact grader root directory. The
runtime must reconstruct and match `benchmark/grader-source-tree-manifest.json`, its profile hash,
the scoring-manifest artifact bindings, and the signed cohort's `grader_source_tree_sha256` before
activating a release. The archive and final manifest remain absent until the source tree is frozen.

#### 9.4.2 Environment-attestation construction profile

The environment payload validates against `schemas/environment-attestation.schema.json` and contains
no self-hash. It records the platform/architecture, OCI digest, exact build IDs and executable hashes
for LibreOffice/Poppler/Python and every scoring library, locale/timezone/reference clock,
`libfaketime`, export/PNG/SSIM profile hashes, Fontconfig configuration hash, sorted exact font-file
inventory, schema/MCE/package-hash profiles, grader source-tree hash, and canary identity. Unknown
properties fail validation. `environment_attestation_sha256` is
`sha256:<hex(SHA-256(RFC8785-JCS(payload)))>`.

The worker reconstructs the attestation from the running container rather than trusting submitted or
deployment metadata, validates it, recomputes its hash, and compares it with the active scoring
manifest before grading. Every report contains both the payload and digest; a missing field,
unexpected runtime/font, invalid schema, or digest mismatch makes verification incomplete.

#### 9.4.3 Signed release-index chain and rollback protection

Every release index belongs to the fixed `gloss-v1-stable` channel and adds `sequence` (positive
integer), `previous_release_index_sha256` (`null` only for sequence 1), `issued_at`, and
`effective_at`. The Ed25519 signature covers these fields with the rest of the RFC 8785 canonical
index. `state` is one enum—`active`, `frozen`, or `superseded`—not simultaneous booleans. At most one
chain head may be active; a frozen/superseded index remains verifiable history but cannot accept new
campaigns.

A consumer initializes from a configured trusted genesis or previously persisted chain head, then
accepts only a signature-valid index whose sequence is exactly the prior sequence plus one, whose
`previous_release_index_sha256` equals the exact JCS hash of that prior index, and whose
`effective_at >= issued_at`. It persists the highest accepted `(channel, sequence, hash)` before
activating the index. A lower sequence, same-sequence different hash, skipped sequence, unknown fork,
future-issued index outside the configured clock-skew bound, or rollback to an earlier active state
fails closed. Reinstalling a client or clearing cache does not authorize rollback; recovery requires
the trusted chain from genesis, not a mutable latest-index pointer.

The frozen release package serializes that recovery chain as RFC 8785 canonical
`benchmark/release-index-chain.json`, validated by `schemas/release-index-chain.schema.json`. Its
`indexes` array contains every complete signed index from sequence 1 through the current head, and
its final object must be byte-for-byte equal to canonical `benchmark/release-index.json`. A legacy
sequence-1 genesis package may omit the chain file. A package above sequence 1 cannot bootstrap from
its own mutable contents: it requires a configured trusted-genesis hash or a durable previously
accepted head. The consumer stores the highest accepted channel, sequence, index hash, and genesis
hash outside cache storage before activating the head; cache deletion does not remove or reset this
state.

#### 9.4.4 100-run export-determinism evidence

The release publishes RFC 8785 canonical `benchmark/export-determinism-evidence.json`, validated by
`schemas/export-determinism-evidence.schema.json`. It contains no self-hash. The signed scoring
manifest binds `sha256:<hex(SHA-256(JCS(evidence)))>` as
`gold.export_determinism_evidence_sha256`.

The evidence binds the exact environment-attestation hash; original and MCE-resolved gold hashes;
canonical-package identity/profile; canonical PDF and ordered page-1..20 PNG hashes; and the frozen
export and SSIM profile hashes. Run 1 is the canonical published PDF/PNG export and must match those
bound hashes exactly. A substituted environment, package, profile, PDF, or page export invalidates
the evidence.

The payload contains exactly 100 ordered export runs, each with exactly 20 ordered pages, and every
unordered run pair in lexicographic `(run_a, run_b)` order. Therefore it contains exactly
`100 choose 2 = 4,950` run-pair records and `4,950 * 20 = 99,000` page-pair SSIM comparisons. For
every pair, the validator recomputes the pair minimum from its 20 pages; for every page, it recomputes
the minimum across all 4,950 run pairs; and it recomputes the global minimum across all 99,000
comparisons. Stored counts and summaries are assertions, not trusted shortcuts. Missing, duplicate,
reordered, non-finite, or out-of-range records fail closed.

Every recomputed per-page minimum and the recomputed global minimum must be at least `0.99999`.
Meeting only the aggregate minimum is insufficient. The release file is created only from the real
pinned-environment runs; the repository keeps the schema and validator without a placeholder or
synthetic evidence instance before that campaign completes.

### 9.5 Export contract

The one official export path is PPTX → PDF → PNG:

- before export, require `/ppt/presentation.xml` `p:sldSz` to be exactly
  `cx=12192000`, `cy=6858000` EMU; missing, alternate-orientation, or merely ratio-equivalent values
  fail validation
- open the presentation in LibreOffice Impress headless and export PDF
- require exactly 5, 12, or 20 PDF pages according to the targeted campaign tier. LibreOffice
  `7.3.7.2` converts the exact v1 EMU width through its 1/100-mm representation, so the frozen raw
  page profile is `MediaBox [0 0 960.009448818898 540]` PostScript points—not an idealized `960 ×
  540`. Parse PDF numbers as exact decimals and require those four values; `CropBox` must be absent or
  exactly equal that MediaBox, and `Rotate` must be absent or numeric zero. This observed profile
  stores coordinates as canonical decimal strings and is bound with its LibreOffice build in the
  scoring manifest. A missing, extra, differently boxed,
  cropped, rotated, or stretched page is an artifact export failure and is never inserted, removed,
  resized, or tolerated by ratio alone
- rasterize every PDF page with the pinned `pdftoppm` at exactly **1920 × 1080 pixels** (16:9)
- convert to RGB and encode PNG using the pinned Pillow version and frozen encoder parameters
- compare exported PNGs against gold exports using perceptual similarity (see §22)
- the reference datetime for date/time fields is pinned to `2025-01-01T00:00:00Z`
- the canonical wrapper launches LibreOffice, Poppler, and grader subprocesses with the manifest-
  pinned `libfaketime` preloaded, `FAKETIME=@2025-01-01 00:00:00`,
  `FAKETIME_DONT_FAKE_MONOTONIC=1`, locale `en_US.UTF-8`, and timezone `UTC`; the clock conformance
  fixture must render and extract the pinned date before a release may freeze

Export command (reference):
```bash
libreoffice --headless --convert-to pdf \
  --outdir /work /input/submission.pptx
pdftoppm -png -scale-to-x 1920 -scale-to-y 1080 \
  /work/submission.pdf /work/gloss-render
```

Direct PNG export, an alternate rasterizer, a resize fallback, a second architecture, or any other
export path is a grading error. It never silently substitutes for the canonical path.

### 9.6 Environment drift detection

The grading environment includes an automated drift canary:

- re-grades the gold deck on a weekly schedule
- compares canonical PNG hashes, score-semantic-report hashes (§26.1.1), and structural extraction hashes against
  stored baselines
- alerts and blocks grading if any canonical PNG or score-semantic projection byte changes, even when SSIM
  remains above the pass threshold
- alerts if any structural extraction result changes
- blocks new grading runs until drift is investigated and resolved
- logs all canary results with timestamps for audit

### 9.7 Docker reference image

The benchmark ships a Dockerfile that produces the canonical grading environment:

```dockerfile
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-core poppler-utils libfaketime \
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

The example is illustrative and intentionally not a release manifest. The Dockerfile is a build
recipe, not the frozen identity. The released `linux/amd64` OCI digest and
scoring manifest are canonical. Mutable base tags, moving APT indexes, and unversioned package
resolution are prohibited in a frozen release. Third-party implementations must match the released
conformance corpus byte-for-byte at the §26.1.1 score-semantic projection layer.

Files whose contents bind the OCI digest (`environment-attestation.json`,
`scoring-manifest.json`, release indexes, determinism/gold evidence, baselines, and control
handoffs) are excluded from the environment-image build context to avoid an OCI-digest
self-reference. The worker mounts the exact signed release package read-only and sets
`GLOSS_BENCHMARK_DIR` to that mount only after its release chain, scoring-manifest hash, grader
source tree, and environment-attestation hash have verified. Rebuilding an image never copies
OCI-bearing release metadata into the image it identifies.

The release image does not trust package names as font evidence. Its build enumerates `fc-list` under
the frozen `FONTCONFIG_FILE`, hashes every reachable font file, compares the exact set with
`benchmark/fonts/manifest.json`, and fails on any missing or extra file. The worker mounts no host
font directories or caches.

### 9.8 Optional PowerPoint fidelity score

For private diagnostic use, an optional **PowerPoint fidelity score** may be computed by running a
separate, non-official comparator on a Windows machine with PowerPoint installed. This score:

- appears only in the submitter's local/private report and never on the official leaderboard
- is not required for leaderboard participation
- uses separately exported PowerPoint gold references and identifies its non-canonical environment
- is only available for on-premise or self-hosted grading (not the hosted service)

This allows teams with PowerPoint access to measure PowerPoint-specific fidelity while keeping the official benchmark cross-platform.

## 10. Scoring Model

### 10.1 Score representation

The benchmark score is represented as:

- `fidelity_score`: weighted aggregate (0.0 to 1.0) when scoring completes, otherwise `null` only for
  the completed diagnostic states in §11.1.1
- `campaign_contribution`: targeted fidelity when eligible, otherwise exactly `0.0`
- `passed_items`: count of passed checklist items
- `total_items`: count of total checklist items
- `deck_passed`: boolean (true only if fidelity_score == 1.0, `verification_complete == true`, `schema_validation_performed == true`, `schema_valid == true`, no score-affecting anti-cheat disposition was triggered, and no repair event occurred)
- `eligible`: boolean (true only for a hosted submission eligible for the leaderboard — all required stages performed, schema-valid, not rejected by quarantine, not timed out, not a gold duplicate, and no grading error; local/control reports are always false)
- `grading_mode`: `local | hosted`; local reports are always non-official/ineligible as §1.1 defines
- `verification_complete`: boolean that is true only when every required grader stage reports `performed == true`
- `scoring_completed`: boolean that is true when Stage 5 produced the complete targeted item set and
  score, even if a later/parallel eligibility condition makes verification incomplete
- per-slide item pass/fail breakdown with severity
- deck-level item pass/fail breakdown with severity
- per-tier scores (Level 1, Level 2, Level 3) — non-targeted tiers are serialized as `null` in JSON output; they are not omitted
- efficiency metrics (see §10.4)
- `anti_cheat_flags`: array of triggered anti-cheat rules, each with `disposition: warning | zero_slide | zero_affected_slides | reject`
- `repair_triggered`: boolean

### 10.2 Severity tiers

Each checklist item has a severity tier that determines its weight in the aggregate score:

- **critical** (weight 3): native object type requirements, anti-cheat rules, master/layout enforcement, text content correctness
- **major** (weight 2): visual fidelity, z-order, grouping structure, field semantics, chart/table data accuracy
- **minor** (weight 1): geometry tolerance, shadow/transparency precision, spacing precision, decorative element details
- **informational** (weight 0): stretch metrics and diagnostic data reported for analysis but excluded from fidelity_score

The fidelity score is: `sum(passed_item_weights) / sum(all_item_weights)`

**Tier aggregation**: a submission targets exactly one tier and serializes exactly one non-null tier
score matching the immutable `campaign.tier`; other tier fields are `null`. Level 3 includes all 20
slides but is not simultaneously a Level 1 or Level 2 submission. The **aggregate score** equals the
targeted tier score.

The pass/fail item count is also reported for item-level analysis.

### 10.3 Item types

Checklist items fall into two buckets:

- slide-level items: scoped to a single slide
- deck-level items: scoped to the entire deck (e.g., master reuse consistency, cross-slide theme coherence)

Deck-level items are scored independently from slide-level items. A deck-level item failing does not automatically zero any slide-level items.

However, **automatic-fail rules** (§4.3) are a separate mechanism from normal item scoring. When an automatic-fail rule triggers, it zeroes all items on the affected slide(s), regardless of whether the rule was triggered by a slide-level or deck-level condition.

Only `zero_slide`, `zero_affected_slides`, and `reject` anti-cheat dispositions affect `deck_passed`. A `warning` is diagnostic and does not change the score or pass state.

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

An official reliability result is a precommitted seven-day **single-variant campaign** keyed by
`(submitter_id, model_key, model_revision_key, scoring_cohort_id, tier, prompt_variant,
assistance_class, generation_profile_sha256, window_id)`:

- the service assigns an immutable `campaign_id` before the first artifact is uploaded
- the campaign contains the first **three accepted uploads that complete grading**; a graded but
  ineligible artifact occupies a slot with campaign score `0.0`, while a service failure before a
  report exists does not occupy a slot. A campaign with fewer than three completed slots is
  displayed as provisional and is not ranked
- no reservation is accepted at or after derived `accepts_until` (§11.5.1); an earlier reservation
  may finish afterward. Once every pre-cutoff reservation is terminal, a campaign with fewer than three occupied slots is
  `closed-incomplete` and can never be ranked or refilled
- `official_score` is the arithmetic mean of the three `campaign_contribution` values; best, worst,
  and standard deviation use those same values, while every constituent diagnostic fidelity (which
  may be null) is displayed separately
- an all-time `record_score` may be displayed separately but MUST NOT be labeled official,
  reliable, or reproducible
- each campaign has exactly one tier and one prompt variant and therefore contains exactly three
  occupied grading slots when complete
- each campaign immutably precommits `assistance_class: unassisted | human-assisted` and a
  `generation_profile_sha256`. The profile is RFC 8785 canonical JSON describing the generator/API
  revision, generation strategy, toolchain, temperature/sampling configuration, and whether human
  intervention or post-processing is permitted; unknown properties fail its published schema. The
  profile contains no artifact, result, run seed, timestamp, or self-hash. Every slot must attest the
  same profile hash and assistance class. An `unassisted` campaign requires
  `profile.permissions.human_intervention_permitted: false` and every run's
  `human_intervention: false`. `human_intervention: true` is compatible only with
  `human-assisted`; `post_processing` is independently frozen in the generation profile and may
  describe an automated toolchain. A declaration inconsistent with either campaign binding is a
  completed-ineligible result, never silently reclassified after scoring
- a `robustness_group` is a parent resource that links exactly three child campaigns—`canonical`,
  `paraphrase-a`, and `paraphrase-b`—with the same immutable submitter/model/revision, tier,
  scoring cohort, assistance class, generation-profile hash, and seven-day window. It contains nine
  run slots in total but is not itself a campaign
- all eligible and ineligible run summaries are append-only and public; a run cannot be withdrawn
  after the score is known

#### 11.1.1 Submission/report/slot terminal-state table

For `grading_mode: hosted`, transport acceptance creates one reservation, but only an immutable grading or diagnostic report
occupies a campaign slot. These outcomes are exhaustive:

| Condition | Submission terminal status | Report/public run row | Slot effect | Retry semantics |
|---|---|---|---|---|
| Security quarantine rejection before schema diagnostics (malware, encryption, ZIP bomb, forbidden active/external content) | `rejected` | none; only a private non-attacker-controlled audit record | release reservation | artifact is non-retryable; a new upload consumes normal quota |
| Signed handoff signature/expiry/binding/object/hash mismatch | `failed` with `quarantine_handoff_mismatch` | none | release reservation | same verdict is never retried; service must rerun quarantine and issue a new verdict or operator-remediate |
| Schema/OPC/MCE invalid artifact after safe diagnostics exist | `completed` | completed-ineligible diagnostic report and sanitized public run row | occupy at campaign score `0.0` | non-retryable for that artifact |
| Published gold byte/canonical duplicate | `completed` | completed-ineligible diagnostic report and sanitized public run row with duplicate outcome | occupy at campaign score `0.0` | non-retryable for that artifact |
| Observable repair, unclassified renderer warning, attestation/campaign mismatch, or score-affecting `reject` disposition after a report exists | `completed` | completed-ineligible report and public run row | occupy at campaign score `0.0` | non-retryable for that report |
| Artifact-deterministic LibreOffice open/export failure reproduced once in a fresh worker with the same resolved hash | `completed` | completed-ineligible diagnostic report and sanitized public run row | occupy at campaign score `0.0` | non-retryable for that artifact |
| Infrastructure renderer crash/timeout, queue loss, storage outage, or worker loss before any report commit, with no evidence the artifact deterministically caused it | `failed` | none | release reservation | retryable service failure; a retry uses a fresh quarantine verdict |
| Successful complete grading, eligible or score-reduced | `completed` | immutable report and public run row | occupy with fidelity score when eligible, otherwise `0.0` | immutable; never replaceable |

The service distinguishes artifact-deterministic renderer failure from infrastructure failure by one
fresh-worker replay of the same resolved object after issuing a new quarantine verdict. Two identical
artifact-stage failures yield the diagnostic zero-slot result; disagreement is an infrastructure
failure and releases the reservation. No other retry is permitted in an official campaign. A report
commit and `reserved -> occupied` transition occur in one transaction; once either exists, release is
forbidden. `failed` and `rejected` responses contain no `result`; `completed` responses contain a
schema-valid result, even when ineligible.

Every completed result has `campaign_contribution`. It equals the numeric targeted fidelity score
only when `eligible: true`; otherwise it is exactly `0.0`. When grading never reached a complete score
(schema/OPC invalidity, duplicate rejection, or artifact renderer failure), `fidelity_score` and all
tier score objects are JSON `null`, not fabricated zeros, and `scoring_completed` is false. A
completed-ineligible report produced
after scoring may retain its numeric diagnostic score, but that value is explicitly non-ranking and
does not change `campaign_contribution: 0.0`; in that case `scoring_completed` is true even though
`verification_complete`/`eligible` are false.

### 11.2 Seed handling

Every submission metadata object, grade report, immutable run record, and public run row contains the
member `generation_seed`. Its value is either the exact provider-facing seed rendered as a UTF-8
string (maximum 256 bytes, with no normalization) or JSON `null` when the generator exposes no seed.
An omitted member is contract-invalid. If a generator accepts a seed, `null` is not permitted; the
submitter records the seed actually used. The same seed should produce the same output when the model
claims determinism. V1 records but does not independently verify generation determinism, and the seed
never changes scoring or campaign identity.

### 11.3 Cherry-picking prevention

- Campaign membership is fixed before grading begins and uses the first three accepted uploads that
  produce a grading report. A graded-ineligible upload occupies a slot at `0.0`; a service failure
  before any report exists does not occupy a slot.
- Aliasing a display label or creating a new free-text version cannot create a new quota identity.
- The leaderboard shows every run plus mean, best, worst, standard deviation, and attempt count.
- Withdrawing or replacing a run after seeing its score is not permitted.
- Completed campaigns remain historical cohorts. A new campaign never modifies an earlier result.

### 11.4 Model identity policy

- `submitter_id`, `model_key`, and `model_revision_key` are server-issued immutable identifiers.
- Free-text model names and versions are display metadata only and never participate in quota,
  grouping, comparison, or campaign keys.
- A model revision payload is immutable from creation. A new revision requires a new server-issued
  key and public revision note; creating one does not reset organization-level quotas.
- Public rows identify the submitting organization and whether any model-owner attribution is
  owner-verified or submitter-attested.
- Maintainers may correct display labels, but immutable keys and historical run records never change.

### 11.5 Multi-window behavior

Campaigns are displayed by their exact scoring cohort and closing date. The default ranking uses the
most recent completed campaign within each complete selection key
`(submitter_id, model_key, model_revision_key, scoring_cohort_id, tier, prompt_variant,
assistance_class, generation_profile_sha256)` and within the last 30 days. The ordering is
`completed_at DESC, campaign_id ASC`; neither a different tier/variant nor an assisted/profile cohort
may replace another row. Older campaigns remain accessible as history and receive a `stale` label.
Scores from different scoring cohorts are never combined. The all-time record view is explicitly
descriptive and non-official.

#### 11.5.1 UTC windows and campaign state

Seven-day windows are half-open UTC intervals anchored at `2025-01-06T00:00:00Z`. For server receipt
time `t`, `k = floor((t - anchor) / 604800 seconds)`, `opens_at = anchor + k*604800`, and
`closes_at = opens_at + 604800`; `window_id` is the ASCII string
`utc7:<opens_at in RFC3339 with Z>`. The server uses its trusted clock. A reservation transaction
whose commit time is `>= accepts_until` is rejected even if its request began earlier.
`accepts_until = min(closes_at, cohort_freeze_effective_at)` when a signed release-index transition
freezes/supersedes the cohort, otherwise it equals `closes_at`; the service returns this derived field
and the index hash that caused any earlier cutoff.

Campaign status is derived, never client-set:

| State | Exact predicate |
|---|---|
| `open` | current time is before `accepts_until`, zero occupied slots, and zero live reservations |
| `provisional` | fewer than three occupied slots and at least one occupied or live pre-cutoff reservation; after cutoff it remains provisional only while a pre-cutoff reservation is nonterminal |
| `completed` | exactly three immutable report-producing slots are occupied |
| `closed-incomplete` | current time is at/after `accepts_until`, fewer than three slots are occupied, and no pre-cutoff reservation remains nonterminal |

`completed` and `closed-incomplete` are terminal. A campaign cannot transition from either state back
to `open`/`provisional`, and a completed campaign cannot become stale by mutation; `stale` is a derived
display label relative to query time.

## 12. Checklist Specification Format

Each checklist item is defined declaratively in YAML.

Schema:

```yaml
schema_version: "1.0"
lifecycle_state: frozen
id: slide-03.native-table-required
scope: slide
slide: 3
tier: 1          # minimum tier that includes this item (1, 2, or 3) — slide 3 is in Level 1
title: Native table required
description: Slide must contain the native OOXML table required by the frozen prompt oracle.
prompt_requirement_id: slide-03.prompt-r005
assertion_id: slide-03.assert-native-table
provenance:
  status: complete
  kind: prompt             # prompt | reference_image | asset_manifest
  source_hash: sha256:...
locator: "prompts/variants/canonical/slide-03.md#L15"
kind: structure
severity: critical
source_of_truth: ooxml   # ooxml | render | both
  # ooxml: ECMA-376 OOXML package inspection is authoritative
  # render: reference renderer (LibreOffice) export/visual output is authoritative
  # both: both OOXML and renderer must independently pass; if either fails, the item fails
verification:
  method: object_compare
  selector: table
  matching_policy: exact_native_type_and_prompt_geometry
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
  propagation: zero_slide  # zero_slide | zero_affected_slides
  affected_slides:
    status: complete
    mode: current_slide    # current_slide | explicit | named_selector
    slides: [3]            # required and sorted for current_slide/explicit
    selector_id: null      # content-addressed algorithm id for named_selector
    selector_sha256: null  # required hash for named_selector, otherwise null
  # zero_slide: zero all items on this slide
  # zero_affected_slides: zero all items on all slides affected by a deck-level condition (for deck-scoped auto-fail rules)
  # automatic_fail_if rules MUST use zero_slide or zero_affected_slides
evidence:
  status: complete
  positive_fixture_ids: [fixture.slide-03.native-table.valid]
  single_fault_negative_fixture_ids: [fixture.slide-03.native-table.flattened]
  mutation_expectation_ids: [mutation.slide-03.flatten-native-table]
```

`assertion_id`, `provenance`, and `evidence` are mandatory for every scored item. A
`prompt_requirement_id` is mandatory when `provenance.kind == prompt`; reference-image assertions
instead identify the immutable image hash and slide/region, and asset assertions identify the asset
manifest hash and asset ID. An extracted gold value without one of these provenance records is
diagnostic only.

Authoring work may use `lifecycle_state: candidate` with explicit `status: pending` provenance,
evidence, or affected-slide metadata so the repository records omissions honestly. Such a document
is schema-valid candidate metadata but is never scoreable. A frozen scoring manifest accepts only
`lifecycle_state: frozen`; every frozen item must have complete matrix-compatible provenance,
complete nonempty evidence IDs that resolve to published fixtures/mutations, and complete
affected-slide rules for every automatic failure. The release validator rejects any candidate or
pending member across the complete bundle.

At release, `benchmark/fixtures/index.json` is a closed
`gloss-assertion-evidence-index-v1` projection. It binds the RFC 8785 review-projection SHA-256
of the frozen assertion inventory and contains exactly one entry for every frozen assertion. Each
entry repeats that assertion's `assertion_id`, `checklist_item_id`, positive-fixture IDs,
single-fault-negative-fixture IDs, and mutation-expectation IDs byte-for-byte and in the same array
order. The release validator rejects duplicate, missing, substituted, or extra entries and any
projection hash mismatch. The index is an addressable cross-binding record, not evidence by itself;
it cannot upgrade candidate or generated-operator fixtures into independent assertion evidence.

Every automatic-fail result emits the resolved, sorted `affected_slides`. `current_slide` resolves to
the slide being evaluated; `explicit` uses the frozen list; `named_selector` invokes an algorithm
whose identifier and content hash are in the scoring manifest. Scoring intersects that list with the
submitted campaign tier and zeroes only the intersection. An empty intersection is reported as a
warning for that targeted tier. The grader MUST NOT infer affected slides from whichever objects
happen to match most favorably.

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
2. **Freeze a prompt-derived requirements oracle before gold authoring.** Two independent reviewers transcribe every mandatory prompt requirement into atomic, machine-readable requirements. Each requirement identifies its prompt citation, severity, source of truth, and matching/equivalence policy. Disagreements are resolved against the prompt, never against a deck.
3. **Validate prompts independently without gold.** At least three blinded authors create each slide from the prompts alone (no gold or reference images), using LibreOffice Impress with the benchmark font set. Every mandatory assertion in the requirements oracle must pass for every implementation. Pairwise normalized scene-graph similarity is diagnostic only; it has no release threshold and cannot override a missed requirement. Any author disagreement or failed assertion requires prompt revision, oracle revision, and a fresh blinded round.
4. **Freeze the pre-gold assertion core.** Prompt-sourced assertions originate from the prompt-derived
   oracle, and asset-identity/usage assertions originate from the independently authored asset
   manifest. Each records an exact immutable source hash and locator before gold authoring. No
   reference-image assertion exists yet.
5. **Build the gold deck.** A skilled author builds the canonical gold deck in **LibreOffice Impress** (the reference renderer) using only the bundled libre fonts and approved assets. The gold deck must be authored in the same tool that will grade it to avoid serialization-dependent rendering differences.
6. **Validate ECMA-376 compliance.** Run the gold deck through XSD validation against the bundled ECMA-376 Part 1 Transitional schema set. Apply Markup Compatibility and Extensibility preprocessing before XSD validation as defined in §15.1 Stage 0.5. Fix any schema violations.
7. **Export reference images.** Export gold slides using the one canonical export pipeline in the release manifest to create the reference PNGs.
8. **Freeze the complete scored-assertion inventory.** Independent reviewers may now add only visual
   properties that satisfy the §4.1 `reference_image` matrix, each bound to exact reference-image
   hash/slide/region. They review pixels and task inputs, not gold OOXML or the extracted gold scene
   graph. Extractor-generated gold data may propose diagnostics, but cannot add, omit, waive, pass, or
   become authority for a requirement.
9. **Validate the independent oracle.** Every scored property and anti-cheat rule must have at least one passing fixture, one single-fault failing fixture, and a published mutation expectation. Alternative valid implementations must exercise each declared semantic-equivalence policy. Gold-perfect is necessary but not sufficient; release requires the complete mutation matrix to match and every required mutant to be killed.
10. **Create baseline scores** (see §13.4). Baseline ranges are descriptive. A missed target range does not permit checklist or threshold tuning unless a diagnosed contract defect is published and the prompt/oracle freeze restarts.

This prompt-first flow ensures that:
- Prompts are tested artifacts, not afterthoughts
- The benchmark measures prompt interpretation, not just reconstruction from reference images
- Ambiguous prompts are caught before the gold deck is frozen
- A parser or gold extractor cannot certify itself by omitting a requirement

#### 13.1.1 Single published gold identity

The release publishes one `gold-evidence.json` that validates against
`schemas/gold-evidence.schema.json` and binds, at minimum:

- the original authored gold byte hash/object identity;
- the exact `mce_resolved_package_sha256`/size produced by the frozen MCE, root-map, OPC, and XSD
  pipeline;
- `canonical_package_hash_profile_sha256` and the resulting gold
  `canonical_package_hash_v1`;
- schema/OPC validation evidence, gold scene-graph hash, each canonical PDF/PNG hash, page count and
  page geometry, and the three signed reference-control report hashes; and
- the scoring manifest and release-index hashes under which those values were produced.

There is exactly one resolved gold package per scoring manifest. XSD/OPC validation, reference PDF
and PNG export, scene-graph extraction, exact and canonical duplicate comparison, mutation-control
parentage, and all three tier reference controls MUST consume that same byte-identical resolved
package. A tool may retain the original authored package for provenance, but may not validate one
resolution, render another, extract a third, or compute duplicate hashes from the unresolved ZIP. A
digest or profile mismatch invalidates the complete gold evidence set and prevents release; no
component may be regenerated independently without issuing a new scoring manifest/cohort and rerunning
all dependent controls.

#### 13.1.2 Reviewer approval projections

Reviewer hashes bind the exact object reviewed and never hash an approval array containing their own
hashes. The prompt-oracle approval projection is RFC 8785 canonical JSON for exactly:

```json
{
  "domain": "Gloss prompt requirements oracle review v1",
  "oracle": "<the complete prompt-requirements object with independent_reviews omitted>"
}
```

`reviewed_oracle_sha256` is the lowercase, unprefixed hexadecimal SHA-256 of those JCS bytes, matching
the existing prompt-oracle schema field. The scored-assertion approval projection is exactly:

```json
{
  "domain": "Gloss scored assertion inventory review v1",
  "inventory": "<the complete scored-assertion-inventory object with review omitted>"
}
```

`inventory_sha256` is `sha256:<lowercase hex SHA-256>` of those JCS bytes. At freeze, each document
requires at least two approval objects with distinct `reviewer_id` values, and every approval must
carry the recomputed projection hash. Counting objects, `uniqueItems`, or accepting arbitrary
well-formed hashes is insufficient. A change to any projected field invalidates every prior approval;
approval metadata itself is outside the projection to avoid a self-hash cycle.

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

### 13.4 Baseline measurement

Before public release, generate baseline scores from:

- **Human expert**: a skilled PowerPoint author recreating the deck from the **exact official inputs** (deck-level prompt, per-slide prompts, reference images, asset manifest). This measures the ceiling for prompt interpretation by a human.
- **Programmatic copy**: a published, content-addressed script using a pinned `python-pptx` version that reads the gold deck's OOXML and reconstructs it programmatically (no direct file copy). This is a descriptive API ceiling, not independent oracle evidence.
- **Naive LLM**: a named model, immutable provider model/version identifier, dated API configuration, exact prompt bundle, seed/temperature where supported, and published generation transcript hashes, with no benchmark-specific tuning.

Baselines run as explicit `run_kind: baseline_control` through the complete conformance harness. They
are permanently `eligible: false`, cannot reserve campaign slots or appear in leaderboard/model
profiles, and publish their descriptive provenance. Gold duplicate detection still runs and is
reported; for this control kind only, a duplicate result does not suppress downstream diagnostic
scoring. They carry the fixed label `grading-verified baseline control; not a leaderboard result`.
Hosted baseline controls require a maintainer signature. Public submission behavior is unchanged.

These baselines establish the score distribution and verify that the benchmark discriminates meaningfully. Expected ranges:

- Human expert: 0.85–0.98 (high fidelity but minor visual differences from manual recreation)
- Programmatic copy: 0.90–1.0 (near-perfect structure, possible visual differences from python-pptx rendering quirks)
- Naive LLM: 0.20–0.60 (significant structural and visual gaps)

If baselines fall outside these ranges, publish and investigate the result. Do not revise the checklist, threshold, or gold merely to fit the anticipated bands. A diagnosed contract defect requires restarting the affected prompt/oracle freeze and all dependent calibration.

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

- **ECMA-376 schema validation**: validates the `.pptx` against the bundled ECMA-376 5th Edition Part 1 Transitional XSD schema set
- **OOXML structural inspection**: direct XML inspection for semantic verification of object types, relationships, and properties
- **Reference renderer export**: LibreOffice Impress headless for visual export and comparison
- **Deterministic checklist execution engine**

**Canonical source of truth**: scored assertions declare whether OOXML inspection, reference rendering,
or both are authoritative. The same content-addressed MCE-resolved package is consumed by XSD
validation, semantic inspection, and rendering. A schema-invalid, unresolved, or incompletely mapped
package may receive diagnostics but is never verified, eligible, passed, or ranked.

### 15.1 Major grader stages

#### Stage 0. Ingestion and quarantine

- the long-lived API performs only streaming byte-count, upload timeout, magic-byte, and opaque
  object-storage checks; it does not open ZIP or XML content
- a fresh disposable quarantine sandbox validates file extension and package content
- validate file size is within limits (max 100 MB)
- validate ZIP structure (reject ZIP bombs: max decompression ratio 20:1, max decompressed size 500 MB)
- scan for and reject: VBA macros, ActiveX controls, OLE embedded objects, external links, password protection
- validate slide count matches expected tier count
- load manifest and checklist definitions
- ensure benchmark package version match
- compute `submission_sha256` while streaming and store the opaque upload under an immutable
  content-addressed object version

All archive and XML inspection runs in a disposable, resource-limited, no-egress quarantine
sandbox before the grading sandbox is created. Local and hosted modes use the same normative
quarantine library and evasion-fixture corpus. The API/control-plane process never parses an
untrusted ZIP member or XML document.

Stages 0 and 0.5 execute in the same disposable sandbox. The sandbox emits a signed quarantine verdict
containing the original `submission_sha256`/size/object version, quarantine-profile hash, MCE-profile
hash, schema-bundle/root-map hashes, `canonical_package_hash_profile_sha256`, gold byte/canonical
hashes, `run_kind`,
`control_authorization_sha256` plus immutable authorization object version (both null for submissions),
server-issued `job_id`, conditional submission/campaign/slot binding (non-null only for submissions),
single-use `verdict_id`, issued/expiry timestamps, and verdict. It signs RFC 8785 canonical JSON with
an Ed25519 key whose
`key_id` and public key are in the active service configuration; rotation uses an audited overlap
window. Queue messages contain only that envelope and immutable identifiers. Before any package parse,
the grading worker verifies signature, key status, expiry, single-use verdict ID, and campaign binding,
then reads the immutable resolved-
package object and recomputes digest and size; any mismatch is a terminal
`quarantine_handoff_mismatch`. The worker never opens the original upload. Thus all first-pass parsing
of attacker-controlled ZIP/XML occurs only inside the disposable quarantine sandbox, and every later
stage consumes the exact schema-valid resolved package that sandbox produced.

An `accept` verdict additionally requires non-null sanitized
`mce_resolved_package_sha256`/size/object version, computed candidate
`canonical_package_hash_v1`, and a duplicate outcome permitted by its run-kind authorization:
`submission` requires `clear`; `reference_control` requires the authorized exact gold duplicate;
`baseline_control` records either outcome and follows its authorization. A `reject` verdict sets resolved and
candidate fields to null unless safe processing completed far enough to compute them, and carries a
stable diagnostic code; it is never dispatched to a worker. Schema-invalid and gold-duplicate reject
verdicts are committed directly as the completed-ineligible diagnostic outcomes in §11.1.1, while a
security rejection has no report. These conditional forms are schema-enforced.

The worker also recomputes the candidate canonical package hash using the verdict-bound profile and
requires exact equality with the bound value and duplicate outcome before Stage 1. For controls it
verifies the separate purpose-scoped authorization in §18.4.1. Any missing profile, computed hash,
comparison result, run-kind authorization, or cross-binding fails closed before parsing.

##### Signed-verdict replay state machine

The durable verdict store is authoritative and transitions atomically:

`issued -> leased(generation, worker_id, lease_deadline) -> consumed`.

- issuance inserts a unique `verdict_id` in `issued`, generation 0, with the signed expiry;
- dispatch compare-and-swaps `issued` to `leased`, increments generation, records one worker and a
  lease deadline no later than verdict expiry, and emits a dispatcher-signed lease token binding all
  four values;
- the worker verifies both envelope and lease token, rehashes the resolved object, then atomically
  changes its exact lease generation to `consumed` immediately before the first package parse;
- `consumed`, `expired`, and `revoked` are terminal. No delivery, worker, retry, or operator action may
  parse using that verdict ID again;
- an expired lease may return to `issued` only when durable state proves `parse_started_at` and report
  are both absent and the signed verdict itself has not expired. The next claim increments generation;
  a delayed worker holding an older generation is rejected;
- a failure after consumption requires a complete fresh quarantine execution and a new verdict ID.
  The old verdict is linked as superseded but never reset. Verdict expiry before consumption releases
  a campaign reservation only under the pre-report rules in §11.1.1.

State transition, lease acquisition, parse-start, and report/slot commit use serializable transactions
or equivalent compare-and-swap constraints. The conformance corpus includes concurrent delivery,
lease timeout/redelivery, delayed stale worker, two-worker claim, crash immediately before and after
consumption, expired signature, revoked key, and fresh-verdict retry fixtures; at most one worker may
reach package parsing for one verdict.

#### Stage 0.5. ECMA-376 schema validation

Stage 0.5 is the sanitizing second half of the disposable quarantine job, not a parser inside the API
or long-lived grading worker.

- preprocess Markup Compatibility and Extensibility using the normative, content-addressed
  `schemas/mce-profile-v1.json` before validation. That profile enumerates the exact namespace URIs
  understood for `Requires` evaluation; extension namespaces are unsupported unless explicitly listed
- fail on undeclared prefixes, malformed QName lists, an unsupported `mc:MustUnderstand` namespace,
  or `mc:AlternateContent` with neither a supported `mc:Choice` nor an `mc:Fallback`
- for `mc:AlternateContent`, select the first `mc:Choice` whose complete `Requires` set is understood,
  otherwise select `mc:Fallback`, then recursively process only the selected branch
- for unsupported ignorable elements and attributes, apply `mc:ProcessContent`,
  `mc:PreserveElements`, and `mc:PreserveAttributes` exactly as declared by the profile: processed
  child content remains in the validation tree, ignored markup is removed from the validation tree,
  and preserved unknown markup is recorded byte-for-byte in sidecar evidence but is never interpreted
- apply identical MCE output to XSD validation and semantic inspection; graders MUST NOT validate one
  tree and score another
- deterministically serialize every processed XML part back into a schema-valid, content-addressed
  `mce_resolved_package`. XSD validation, Stage 1 rendering, and Stage 3 semantic inspection consume
  only this package; the original upload is retained solely for provenance and duplicate detection
- validate the resulting `.pptx` PresentationML content against the bundled ECMA-376 Part 1 **Transitional** XSD schema set from `schemas/ecma-376/xsd-transitional/`. Transitional is used because virtually all real-world `.pptx` files target transitional conformance, not strict.
- before XSD success, enforce the complete frozen OPC package profile:
  - `[Content_Types].xml` has exactly one `Default` per lowercase extension and at most one `Override`
    per normalized part name; each existing part has exactly one unambiguous effective content type,
    every override names an existing part, and declared content type/root pairs match the root map
  - part names and relationship targets satisfy the OPC URI grammar and RFC 3986 resolution used by
    ECMA-376: absolute ZIP names, backslashes, query/fragment, empty/`.`/`..` segments, invalid or
    non-canonical percent escapes, encoded separators, control/NUL bytes, non-NFC names, and trailing
    slash parts are rejected. Normalized-name and Unicode case-fold collisions are rejected
  - `/_rels/.rels` exists with exactly one internal Transitional `officeDocument` relationship to
    `/ppt/presentation.xml`; relationship IDs are unique per source and every `.rels` part is located
    only at its OPC-defined relationship-part name
  - every internal relationship target is resolved against its source part, normalizes to an existing
    package part, and has the expected content type; dangling targets and illegal URI forms fail.
    External relationships are forbidden by Stage 0 and never dereferenced
  - every non-metadata part is reachable from the package root relationship graph; orphan parts,
    duplicate ZIP member names, and parts omitted from `[Content_Types].xml` fail closed
  - `/ppt/presentation.xml` contains exactly one `p:sldSz` with
    `cx=12192000`, `cy=6858000` EMU and a slide-ID list exactly matching the campaign's 5/12/20
    resolved slide relationships
- reject every relevant XML part whose content type/root-element pair is absent from the frozen
  schema mapping. Unknown, ambiguous, or multiply mapped roots fail closed; they are not skipped
- publish the MCE profile hash, XSD bundle hash, and content-type/root-element-to-XSD mapping in
  the scoring manifest and every report; log all preprocessing and schema violations
- a file that fails schema validation receives only the fail-closed diagnostic form described in
  §11.1.1: `verification_complete`, `eligible`, and `deck_passed` are false, its occupied campaign
  contribution is `0.0`, and its sanitized run row is public but never ranked as eligible

#### Stage 1. Reference renderer export

- open the content-addressed `mce_resolved_package` in LibreOffice Impress headless within the
  canonical Docker environment
- export exactly one PDF, then rasterize every page with the pinned Poppler `pdftoppm` and normalize
  with the pinned Pillow encoder to RGB PNG at exactly 1920 × 1080, as specified in §9.5
- enforce a 120-second component timeout for LibreOffice open/PDF export inside the separate
  10-minute hosted-job timeout; Poppler and normalization have their own manifest-pinned limits
- distinguish infrastructure failure from an artifact-deterministic open/export failure exactly as
  §11.1.1 specifies; only the former is `failed`/retryable, while a reproduced artifact failure
  commits a completed-ineligible diagnostic result and occupies its slot at `0.0`
- direct PNG export, an alternate rasterizer, resizing, or rendering the unresolved upload is a
  grading error and makes verification incomplete

#### Stage 2. Visual comparison

- compare submitted export to gold export per slide
- compute perceptual similarity score (SSIM) per slide
- also compute exact pixel match (reported as a stretch metric)
- emit diff visualization for debugging
- pass/fail threshold: SSIM ≥ 0.9999 using the frozen §22.1 profile; validation checks but never
  changes this v1 value

#### Stage 3. OOXML structure extraction

- inspect only the content-addressed `mce_resolved_package` for structural analysis
- inspect slide XML (PresentationML)
- inspect slide layout and master relationships
- inspect media parts and relationships
- inspect charts, tables, placeholders, and theme references
- validate all embedded media hashes against the primary asset hashes in §8.3

#### Stage 4. Scene graph normalization

- build normalized scene graph for gold deck
- build normalized scene graph for submission
- ignore unstable non-visible identifiers
- apply semantic equivalence rules (§5.2)
- preserve user-visible type, hierarchy, geometry, and semantics

#### Stage 5. Checklist evaluation

- materialize the targeted tier item set with the exact §6.2 algorithm and verify its scoring-manifest
  hash before evaluating any item
- run slide-level items with severity scoring
- run deck-level items with severity scoring
- run automatic-fail anti-cheat rules
- compute per-tier fidelity scores
- compute aggregate fidelity score

#### Stage 6. Reporting

- generate machine-readable JSON report
- validate the terminal-state conditionals and compute both the full report hash and the
content-addressed score-semantic projection defined in §26.1.1
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

The gold scene graph is committed for transparency, regression testing, and visual-diff alignment.
It is not an independent oracle and cannot create or waive a scored requirement. Scored structural
expectations come from the frozen prompt requirements inventory and independently reviewed
checklist (§13.1).

## 17. Structural Comparison Rules

### 17.1 Required comparison behavior

The structural comparator evaluates only properties named by each frozen scored assertion. Depending
on the item-specific matching/equivalence policy it may require:

- exact object count for objects constrained by that assertion
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

Only images whose embedded content hash matches the asset manifest's primary SHA-256 (§8.3) may appear. Re-encoded variants are not accepted in v1. PowerPoint's internal thumbnail and preview artifacts are excluded from this check.

Verification methods:

- hash all embedded media parts against the manifest's primary hashes
- compare dimensions against manifest-defined expected dimensions per asset
- compare crop values only when a prompt- or reference-image-sourced assertion specifies the crop for
  that slide position (within its frozen tolerance); the same asset may legitimately appear with
  different crops on different slides
- detect any non-manifest raster objects and measure their area
- compare required/allowed usage against asset-manifest-sourced assertions, never an extracted gold
  asset inventory

### 18.3 Hidden object hacks

Flag as failures when:

- objects violate a frozen prompt/reference-image assertion for visible on-canvas placement or a
  prompt-sourced assertion for intentional off-canvas placement
- incorrect content is hidden under opaque objects in violation of a frozen assertion
- objects outside the bounded optional counts declared by assertions are hidden off-canvas or under
  opaque layers

### 18.4 Higher-level gaming prevention

The following receive `disposition: warning` and are reported without changing the score:

- submissions that appear to be hard-coded deck synthesis (e.g., near-perfect structural match with zero visual customization from prompt)
- submissions with metadata indicating non-model generation tools
- multiple non-gold submissions that are byte-identical or differ only in metadata

An artifact matching either published gold duplicate hash (§1.1) receives `disposition: reject`,
ineligibility code `gold_artifact_copy`, and is never leaderboard-eligible. Near-match and hard-coded synthesis
heuristics remain warnings because v1 cannot reliably distinguish benchmark-specific generation
from copying after a semantically inert modification.

This rejection applies whenever `run_kind: submission`, in hosted or local mode. The conformance
harness has a separate explicit `run_kind: reference_control` used only by release tests and the drift
canary. It accepts only the gold hashes embedded in the active scoring manifest, sets
`eligible: false`, bypasses campaign/leaderboard publication, and cannot carry submitter/model
attribution. Hosted reference controls additionally require a maintainer signature; a public API key
cannot request or emulate them. Reference-control reports are published as operational evidence,
never as leaderboard runs, with the distinct fixed label
`grading-verified reference control; no generation attribution`.

The separately defined `baseline_control` path in §13.4 also remains permanently ineligible and
outside campaigns. It may continue diagnostic scoring after recording `gold_artifact_copy`; this
exception is not exposed by `POST /submissions` and cannot produce a public submission result.

#### 18.4.1 Signed control authorization envelopes

`submission`, `reference_control`, and `baseline_control` are separate signed handoff contracts, not
a client-selectable string. Every quarantine verdict binds `run_kind`. A submission verdict requires
`control_authorization_sha256: null`, a real campaign/slot binding, and the ordinary duplicate policy
`reject_and_complete_ineligible`. Any control field on a public submission is a handoff mismatch.

A reference or baseline control requires a separate RFC 8785 canonical control-authorization
envelope validated by `schemas/control-handoff.schema.json` and signed by a currently authorized,
purpose-scoped maintainer key distinct from API keys and quarantine-verdict keys. The authorization
binds `authorization_id`, `run_kind`, exact purpose (`release_reference`, `drift_canary`, or
`descriptive_baseline`), original/resolved/canonical artifact identities, scoring manifest/cohort,
all profile hashes, requested tier, no-campaign/no-slot policy, duplicate disposition, issuer key ID,
issued/expiry timestamps, and a single-use nonce. The quarantine verdict includes the authorization
envelope hash and signature result; the worker independently verifies both signatures, key purposes,
expiry, nonce state, and all cross-envelope bindings before parsing.

For `reference_control`, artifact identities must equal the exact gold identities in §13.1.1,
duplicate disposition is `allow_reference_only`, and downstream scoring must be perfect while
remaining unpublished from leaderboard/model paths. For `baseline_control`, the authorized baseline
evidence ID and artifact hashes must match its published evidence, duplicate disposition is
`record_then_continue_diagnostic`, and output remains descriptive/ineligible. Neither control may
name a campaign, slot, submitter, model, or model revision. A missing, wrong-purpose, expired,
replayed, cross-bound, or API-key-signed authorization fails before worker parsing. Control results
use their distinct verification labels and can never be converted into submission rows.

#### 18.4.2 Canonical gold-duplicate profile

The release publishes `schemas/canonical-package-hash-v1.json` as a content-addressed normative
profile. It defines the exact included OPC parts, accepted content types, normalized part-name
ordering, XML Canonicalization method, relationship normalization, binary-part treatment, and the
only ignored volatile core-property nodes/attributes. ZIP timestamps, compression, member ordering,
and other container metadata never affect the result. Duplicate normalized part names, orphan parts,
unknown content types, unmapped XML roots, or non-profile extensions are rejected rather than omitted
from the hash. No implementation may add an ignore rule locally.

The canonical hash input is the Stage 0.5 `mce_resolved_package`, not the unresolved ZIP. The gold
canonical hash is computed through the identical MCE/root-map/profile pipeline. The original-upload
byte hash remains a separate exact-copy guard. A profile/version/hash mismatch makes duplicate
screening incomplete and the run ineligible; it never falls back to byte-hash-only screening.

The §13.1.1 gold evidence publishes the original-byte SHA-256, resolved-package SHA-256,
`canonical_package_hash_profile_sha256`, and `canonical_package_hash_v1`. The
conformance corpus contains the exact gold, a ZIP-repacked copy, copies with every individually
ignored volatile field changed, and close non-gold controls. Every gold-derived case must reject and
every declared non-gold control must remain distinguishable. Passing this guard is duplicate
screening only; it does not verify generation provenance.

For hosted mode, model attestation (§25.7) provides additional gaming prevention.

## 19. Multilingual Requirements

V1 includes:

- English
- Arabic (RTL)
- Japanese (CJK)

For each applicable prompt-sourced assertion, the grader verifies:

- exact Unicode text content
- editability as real text (not rasterized, not outlined)
- correct RTL text direction where required
- correct line breaking and layout behavior where constrained by a prompt- or
  reference-image-sourced assertion
- no transliteration
- no outlining
- no rasterization
- correct font fallback (must use bundled fonts from manifest)

## 20. Master, Layout, and Placeholder Requirements

Some slides are intentionally impossible to pass structurally unless the submission uses masters/layouts correctly.

For each applicable prompt-sourced assertion, the grader verifies:

- the assertion-required slide layout is referenced in OOXML
- repeated elements come from master/layout where required by the prompt
- required content is placed in the correct placeholder types
- visually correct manual copies do not count as passing when the prompt specifies master/layout usage

Checks:

- compare layout references in OOXML
- inspect placeholder metadata
- compare assertion-required inherited objects versus slide-local objects

## 21. Native Tables, Charts, and Fields

### 21.1 Tables

If the prompt explicitly calls for a table, the grader requires a native OOXML table. The remaining
properties below are required only when named by a frozen prompt- or reference-image-sourced
assertion:

- correct row/column count
- correct placement within geometry tolerance
- correct visible styling and content
- correct cell merge behavior where specified

### 21.2 Charts

If the prompt explicitly calls for a chart, the grader requires a native OOXML chart. The remaining
properties below are required only when named by a frozen prompt- or reference-image-sourced
assertion:

- correct chart type
- correct visible series/labels/legend behavior
- correct axis formatting where specified

### 21.3 Fields

Where specified, the grader requires native slide-number, date, or footer fields. Static text that visually matches the expected field value is not accepted. The grader verifies field type in OOXML, not just rendered text.

## 22. Visual Comparison Rules

### 22.1 Official rule

- exported submitted slide PNG is compared to exported gold slide PNG using SSIM (Structural Similarity Index)
- pass threshold: SSIM ≥ **0.9999**; this value is frozen for v1 and validation does not tune it
- inputs are two same-shaped `uint8` RGB arrays at 1920 × 1080; a missing or differently sized image fails rather than being resized
- the normative call is scikit-image `structural_similarity` with `channel_axis=2`,
  `data_range=255`, `win_size=7`, `gaussian_weights=false`, `use_sample_covariance=true`,
  `K1=0.01`, and `K2=0.03`; the exact scikit-image and NumPy versions are pinned in the scoring manifest
- exact pixel match is also computed and reported as a stretch metric but is not the pass/fail criterion

### 22.2 Rationale for perceptual threshold

Exact pixel matching is desirable but may be infeasible due to:

- anti-aliasing differences in text rendering
- sub-pixel positioning differences
- font hinting variations even within a pinned environment
- locale-sensitive layout micro-differences

SSIM ≥ 0.9999 is extremely strict while tolerating renderer-level noise that does not reflect generation quality. The exact detection power (e.g., whether a single misplaced character triggers failure) depends on the character's size and position; the threshold is validated empirically during calibration.

### 22.3 Fixed-threshold validation

Before release, the already frozen threshold is validated using both positive and negative fixtures:

**Positive validation (self-export stability):**
- exporting the gold deck 100 times in the pinned environment
- computing SSIM for all 4,950 unordered run pairs and all 99,000 corresponding page pairs
- verifying every per-page minimum and the global minimum SSIM are ≥ 0.99999
- if not, investigating and resolving instability before releasing

**Negative validation (rejection power):**
- creating controlled negative fixtures with known single-element mutations (moved text box, changed font size, wrong color, missing object)
- computing SSIM for each negative fixture against the gold export
- verifying that all negative fixtures score below the pass threshold
- verifying every required negative fixture scores below the frozen `0.9999` threshold
- if any negative fixture passes, the benchmark is not releaseable; the environment, prompts, gold,
or mutation design must be corrected and the complete validation rerun. The threshold is not tuned
  to fit desired baseline outcomes

**v1 visual rule freeze**: the official v1 visual pass/fail rule is SSIM-only (no region-aware supplementary checks). If validation reveals that SSIM alone cannot discriminate between self-exports and negative fixtures, the benchmark must tighten the export environment without changing the scoring rule, then restart the complete environment/oracle freeze and validation. If the fixed rule still cannot discriminate, v1 is not releasable. Region-aware checks require a future MAJOR version with a new freeze and validation cycle.

### 22.4 Practical safeguard

If LibreOffice export is not stable enough even in a pinned Docker environment, the benchmark must not silently relax the threshold. It must first solve determinism operationally. The drift canary (§9.6) enforces this.

## 23. Reference Implementation Stack

**Implementation authority**: the frozen OpenSpec, scoring manifest, schemas, and published fixture
expectations define the contract. A mutable checkout is not normative. Algorithmic details that can
affect a score—including SSIM parameters, geometry matching, opacity thresholds, tie-break rules,
and PNG normalization—MUST be explicit in the scoring manifest or a content-addressed normative
file it references. Third-party implementations must produce byte-identical §26.1.1 score-semantic
report projections on the published conformance corpus.

The recommended reference grader stack is:

- Python `3.12+`
- `lxml` for OOXML XML inspection and ECMA-376 XSD schema validation
- `zipfile` for `.pptx` package extraction
- `Pillow`, `numpy`, and `scikit-image` for visual comparison (SSIM)
- `pydantic` for normalized scene graph models and API schemas
- `pytest` for regression tests
- LibreOffice Impress headless (pinned version) for PDF export and pinned Poppler `pdftoppm` for PNG
  rasterization
- Docker for reproducible environment packaging

ECMA-376 XSD schema files from `schemas/ecma-376/xsd-transitional/` are bundled in the grader package for schema validation.

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

- three maintainer-signed `reference_control` jobs (one per tier) score perfect without entering a
  campaign or leaderboard
- exported gold images match stored references (SSIM = 1.0)
- normalized gold scene graph is stable across repeated extractions
- baseline scores (§13.4) exist with complete provenance; deviations from descriptive bands are
  published and investigated but do not fail this control

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
- every individual OPC fault in §15.1: duplicate/ambiguous content type, invalid/colliding part name,
  missing or duplicate root officeDocument relationship, illegal/dangling relationship target,
  orphan part, incorrect `p:sldSz`, slide-ID/count mismatch, and wrong PDF page count/box/rotation

### 24.3 Mutation tests

Automated mutators alter independently validated positive fixtures—including the gold control where
appropriate—and verify the assertion inventory's predeclared checklist failures:

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
- start from an opaque hostile-capable upload and prove disposable quarantine emits a signature-valid
  verdict plus immutable resolved object; prove the worker atomically consumes the verdict, never
  receives/parses the original, runs Stages 1–6, commits a schema-valid report and slot atomically,
  and publishes a byte/hash-matching immutable public row
- run the same path for eligible, schema-invalid zero-slot, gold-duplicate zero-slot, artifact-render
  zero-slot, handoff mismatch, service failure/release, reference-control, and baseline-control cases
- verify every full report round-trips through the §26.1.1 semantic projection schema/JCS/hash process

### 24.6 Hosted service tests

- quarantine evasion tests: submit files with known evasion techniques (renamed extensions, nested ZIP structures, OLE objects hidden in non-standard parts) and verify rejection
- API contract tests: verify all endpoints against OpenAPI spec, including error codes and rate limiting
- container isolation tests: verify that grading container has no network egress, no persistent state, is destroyed after each job, and runs with hardened security profile (rootless, read-only rootfs, dropped capabilities)
- webhook delivery tests: verify callback on completion with correct HMAC signature
- leaderboard consistency tests: verify that leaderboard entries match stored run records
- concurrent submission tests: verify fairness under load
- control-plane isolation tests: instrument the API process and prove it never opens an untrusted ZIP
  member or parses untrusted XML
- quarantine handoff integrity tests: mutate object bytes/version/digest between quarantine and worker
  dispatch and require `quarantine_handoff_mismatch` before parsing
- verdict replay tests: concurrent two-worker claim, stale lease generation, lease expiry before parse,
  crash before/after consume, signature/key expiry, and fresh-verdict retry prove at most one parse per
  verdict ID
- control-authorization tests: submissions cannot request control kinds; wrong-purpose/API/quarantine
  keys, campaign-bound controls, mismatched gold/baseline identities, and replayed authorizations fail
  before parsing
- campaign contract tests: prove immutable single-tier/single-variant binding, first-three slot
  occupation including zeroed graded-ineligible runs, atomic three-campaign robustness groups, and no
  alias/quota reset
- scoring-cohort tests: prove mismatched manifest, grader-tree, or environment hashes never aggregate
- verification-label schema tests: prove every public/API result includes the exact v1 constant
- tier-selection tests: prove the exact §6.2 item sets/hashes for tiers 1/2/3, including deck items,
  affected-slide intersection, and rejection of tier/slide inconsistency
- release-chain tests: reject rollback, fork, gap, same-sequence alternate hash, invalid state,
  premature effective time, revoked signature, and cache-clearing rollback attempts

### 24.7 Descriptive baseline bands

- Human expert: anticipated fidelity_score in [0.85, 0.98]
- Programmatic copy: anticipated fidelity_score in [0.90, 1.0]
- Naive LLM: anticipated fidelity_score in [0.20, 0.60]

These ranges are hypotheses, not release acceptance targets. Results outside them are published and
investigated; they do not authorize tuning the checklist, threshold, or gold to obtain a preferred
ranking. A diagnosed contract defect requires restarting the affected prompt/oracle freeze.

## 25. Hosted Service Architecture

### 25.1 Service overview

The Gloss hosted service accepts `.pptx` submissions via API, grades them in a controlled
environment, and publishes grading-verified artifact scores to a public leaderboard. Only hosted-mode
artifact scores appear on the official leaderboard with the label required by §1.1. Generation provenance remains attested in v1, as
defined in §1.1.

### 25.2 Submission API

**Base URL**: `https://api.gloss.dev/v1`

All response objects that contain or summarize a score include these immutable constants:

```json
{
  "verification_scope": "artifact_conformance",
  "verification_label": "grading-verified artifact score; generation-attested"
}
```

#### POST /models

Register display metadata and issue an immutable model identity for the authenticated submitter.

Request metadata part:

```json
{
  "display_name": "string (required)",
  "claimed_owner_name": "string (optional, attested)"
}
```

Response (`201 Created`):

```json
{
  "submitter_id": "uuid (derived from API key)",
  "model_key": "uuid (server-issued)",
  "display_name": "string",
  "owner_attribution": "submitter-attested",
  "created_at": "ISO 8601"
}
```

Display names are mutable presentation metadata; `submitter_id` and `model_key` never change and are
the only identity fields used for authorization, quotas, grouping, and comparison. New identities
default to `submitter-attested`; only a separate maintainer verification workflow may set
`owner-verified`, with an immutable audit record. Clients cannot self-assert the verified state.

#### POST /models/{model_key}/revisions

Issue an immutable revision before its first campaign.

Request:

```json
{
  "display_version": "string (required)",
  "revision_note": "string (required)",
  "provider_revision": "string (optional, attested immutable provider identifier)"
}
```

Response (`201 Created`):

```json
{
  "model_key": "uuid",
  "model_revision_key": "uuid (server-issued)",
  "display_version": "string",
  "revision_note": "string",
  "created_at": "ISO 8601"
}
```

The revision payload is immutable after creation. Only display-label corrections may be stored as
separate audited aliases; they never change the original record or historical rows.

#### POST /generation-profiles

Register the exact self-hash-free generation configuration before campaign creation.

Request:

```json
{
  "model_revision_key": "uuid (required)",
  "profile": {
    "schema_version": "1.0",
    "profile_id": "gloss-generation-profile-v1",
    "canonicalization": "RFC8785-JCS",
    "generator": {
      "provider": "provider name",
      "model_identifier": "provider model ID",
      "immutable_revision": "provider immutable revision",
      "api_surface": "API/product surface"
    },
    "generation_strategy": "direct | code | hybrid | template-edit",
    "toolchain": [],
    "sampling": {
      "temperature": null,
      "top_p": null,
      "top_k": null,
      "max_output_tokens": null,
      "other_parameters": []
    },
    "permissions": {
      "human_intervention_permitted": false,
      "post_processing_permitted": false
    }
  }
}
```

The server validates `profile` against `schemas/generation-profile.schema.json`, RFC 8785
canonicalizes it, computes `generation_profile_sha256`, and returns that digest plus the immutable
stored profile (`201`, or the original response for an idempotent replay). The client cannot supply
the digest. The profile is scoped to the authenticated submitter and named immutable model revision;
it cannot be changed or deleted after any campaign references it. Campaign creation rejects an
unknown, cross-tenant, wrong-revision, schema-invalid, or digest-mismatched profile.

#### POST /campaigns

Precommit one reliability campaign before any artifact is uploaded.

Request:

```json
{
  "model_revision_key": "uuid (required)",
  "scoring_cohort_id": "sha256:... (required, currently active cohort)",
  "tier": "integer (required) — 1, 2, or 3",
  "prompt_variant": "canonical | paraphrase-a | paraphrase-b (required)",
  "assistance_class": "unassisted | human-assisted (required)",
  "generation_profile_sha256": "sha256:... (required; registered immutable profile)"
}
```

Response (`201 Created`):

```json
{
  "campaign_id": "uuid (server-issued)",
  "submitter_id": "uuid (derived)",
  "model_key": "uuid (derived)",
  "model_revision_key": "uuid",
  "benchmark_version": "gloss-v1.0.0 (derived from cohort)",
  "scoring_cohort_id": "sha256:...",
  "tier": 3,
  "prompt_variant": "canonical",
  "assistance_class": "unassisted",
  "generation_profile_sha256": "sha256:...",
  "window_id": "server-issued seven-day window identifier",
  "opens_at": "ISO 8601",
  "closes_at": "ISO 8601",
  "accepts_until": "ISO 8601 (derived; initially closes_at)",
  "cutoff_release_index_sha256": null,
  "slot_count": 3,
  "occupied_slots": 0,
  "status": "open"
}
```

The service derives submitter/model/version/benchmark/window from authenticated immutable records and
the active cohort. The tuple in §11.1 is unique. Client-supplied free text cannot alter binding or
create another campaign in the same window.

#### GET /campaigns/{campaign_id}

Returns the immutable binding plus ordered slot state. Before completion, `official_score` is `null`
and `status` is `open | provisional | closed-incomplete`; after three report-producing slots it is
`completed` and returns their arithmetic mean, best, worst, standard deviation, and public run IDs.
Those statistics use `campaign_contribution`, not nullable diagnostic fidelity.
Every completed score object includes the exact `verification_scope` and `verification_label`
constants and all four cohort fields from §9.4. Only the owner can read private reservation/job state;
the public response contains completed run IDs only.

#### POST /robustness-groups

Atomically precommit the three standard variants for one tier.

Request:

```json
{
  "model_revision_key": "uuid (required)",
  "scoring_cohort_id": "sha256:... (required)",
  "tier": "integer (required) — 1, 2, or 3",
  "assistance_class": "unassisted | human-assisted (required)",
  "generation_profile_sha256": "sha256:... (required)"
}
```

Response (`201 Created`):

```json
{
  "robustness_group_id": "uuid",
  "tier": 3,
  "scoring_cohort_id": "sha256:...",
  "assistance_class": "unassisted",
  "generation_profile_sha256": "sha256:...",
  "window_id": "string",
  "campaigns": {
    "canonical": "uuid",
    "paraphrase-a": "uuid",
    "paraphrase-b": "uuid"
  },
  "status": "open"
}
```

Creation is all-or-nothing. The three child campaigns share submitter/model/revision, tier, cohort,
assistance class, generation-profile hash, and window; each retains its own first-three slots. A child campaign cannot be linked to two groups or
replaced after creation. The robustness score is the minimum of the three completed campaign means.

#### GET /robustness-groups/{robustness_group_id}

Returns the immutable group binding, three enum-keyed child campaign IDs/statuses, and
`robustness_score: null` until every child is complete. A completed response includes the minimum
child mean, cross-variant mean and standard deviation as descriptive fields, the exact verification
constants, and all cohort fields. No partial group is ranked.

#### POST /submissions

Create a new submission.

Request metadata part:

```json
{
  "campaign_id": "uuid (required) — precommitted reliability campaign",
  "generation_seed": "string | null (required; exact provider-facing seed or null)",
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
  },
  "webhook_url": "https://example.com/callback (optional)",
  "webhook_secret": "string (required only with webhook_url; write-only)"
}
```

File: multipart upload of .pptx (max 100 MB)

The service derives `submitter_id`, `model_key`, `model_revision_key`, `benchmark_version`,
`scoring_cohort_id`, `tier`, `prompt_variant`, and window from `campaign_id`; the request cannot
override them. The submission's attestation and registered generation profile must match the
campaign's assistance class and generation-profile hash. An accepted upload reserves the next
ordinal, but the slot becomes occupied only when
a grading report exists. A report with `eligible == false` occupies that ordinal with campaign score
`0.0`; a service failure before report creation releases the reservation for retry.

Response (`202 Accepted`):

```json
{
  "submission_id": "uuid",
  "campaign_id": "uuid",
  "campaign_slot": "integer (1, 2, or 3)",
  "status": "queued",
  "estimated_wait_seconds": "integer",
  "status_url": "/submissions/{submission_id}"
}
```

#### GET /submissions/{submission_id}

Poll submission status.

Response:

```json
{
  "submission_id": "uuid",
  "campaign_id": "uuid",
  "campaign_slot": 1,
  "status": "queued | grading | completed | failed | rejected",
  "result": {
    "grading_mode": "hosted",
    "verification_scope": "artifact_conformance",
    "verification_label": "grading-verified artifact score; generation-attested",
    "scoring_cohort_id": "sha256:...",
    "scoring_manifest_sha256": "sha256:...",
    "grader_source_tree_sha256": "sha256:...",
    "environment_attestation_sha256": "sha256:...",
    "canonical_package_hash_profile_sha256": "sha256:...",
    "canonical_package_hash_v1": "sha256:...",
    "gold_duplicate_check": "clear",
    "targeted_tier": 3,
    "prompt_variant": "canonical",
    "assistance_class": "unassisted",
    "generation_profile_sha256": "sha256:...",
    "generation_seed": null,
    "schema_validation_performed": true,
    "schema_valid": true,
    "visual_verification_performed": true,
    "verification_complete": true,
    "scoring_completed": true,
    "disqualification_state": "none",
    "ineligibility_reasons": [],
    "fidelity_score": 0.847,
    "campaign_contribution": 0.847,
    "passed_items": 287,
    "total_items": 312,
    "deck_passed": false,
    "eligible": true,
    "anti_cheat_flags": [],
    "repair_triggered": false,
    "tier_scores": {
      "level_1": null,
      "level_2": null,
      "level_3": { "fidelity_score": 0.847, "passed": 287, "total": 312 }
    },
    "report_url": "/submissions/{submission_id}/report"
  },
  "error": null
}
```

`result` is `null` until completion. `error` is `null` unless status is `failed` or `rejected`; when
present it uses the common error schema below. `result` and `error` are never both non-null.

The response validates against `schemas/submission-status.schema.json`. Hosted API results require
`grading_mode: hosted`; its conditionals require:

- `queued | grading`: both `result` and `error` are null;
- `failed | rejected`: `result` is null and `error` is non-null;
- `completed`: `result` is non-null and `error` is null; the result always includes schema/visual/
  verification-performed state, `scoring_completed`, `disqualification_state`, sorted unique `ineligibility_reasons`, and
  canonical-hash profile/digest/comparison fields; and
- `eligible: true` iff `verification_complete`, schema performed/valid, visual performed, no repair,
  duplicate check clear, and `disqualification_state == none`. Otherwise eligibility/deck pass are
  false. A completed-ineligible result has campaign contribution `0.0` even if a diagnostic
  `fidelity_score` is present; if complete scoring was never performed its fidelity and tier scores
  are null as specified in §11.1.1.

**Stable error and ineligibility codes:** `failed`/`rejected` terminal responses place their code in
the common `error` envelope. `completed` diagnostic responses place the applicable code in sorted
`result.ineligibility_reasons` and keep top-level `error: null`.
- `quarantine_rejected`: file failed security scan (not retryable)
- `grading_timeout`: grading exceeded 10-minute limit (retryable)
- `renderer_crash`: LibreOffice crashed or hung during grading (retryable)
- `artifact_renderer_failure`: the same resolved artifact deterministically failed open/export in
  two fresh workers (completed-ineligible; not retryable)
- `resource_not_found`: campaign does not exist or is not owned by the API-key submitter (not retryable)
- `campaign_closed`: campaign window has closed (not retryable)
- `campaign_full`: three report-producing slots are already occupied (not retryable)
- `campaign_binding_mismatch`: artifact slide count or server state conflicts with campaign binding (not retryable)
- `invalid_scoring_cohort`: requested cohort is unknown, inactive, or component hashes do not match (not retryable)
- `rate_limited`: submission limit exceeded (retryable after wait)
- `gold_artifact_copy`: upload matches the published gold byte hash or
  `canonical_package_hash_v1` (not retryable)
- `quarantine_handoff_mismatch`: worker bytes do not match the signed quarantine verdict (not retryable)

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

#### GET /leaderboard

Returns completed campaign results grouped only within an exact scoring cohort. Display labels are
never used as grouping keys.

Response (summary view):

```json
{
  "benchmark_version": "gloss-v1.0.0",
  "grader_version": "1.0.0",
  "verification_scope": "artifact_conformance",
  "verification_label": "grading-verified artifact score; generation-attested",
  "scoring_cohort_id": "sha256:...",
  "scoring_manifest_sha256": "sha256:...",
  "grader_source_tree_sha256": "sha256:...",
  "environment_attestation_sha256": "sha256:...",
  "grader_package_sha256": "sha256:...",
  "oci_image_digest": "sha256:...",
  "prompt_bundle_sha256": "sha256:...",
  "scored_assertion_inventory_sha256": "sha256:...",
  "checklist_bundle_sha256": "sha256:...",
  "schema_bundle_sha256": "sha256:...",
  "schema_root_map_sha256": "sha256:...",
  "mce_profile_sha256": "sha256:...",
  "canonical_package_hash_profile_sha256": "sha256:...",
  "asset_manifest_sha256": "sha256:...",
  "font_manifest_sha256": "sha256:...",
  "updated_at": "ISO 8601",
  "entries": [
    {
      "submitter_id": "uuid",
      "model_key": "uuid",
      "model_revision_key": "uuid",
      "campaign_id": "uuid",
      "model_display_name": "string (attested display metadata)",
      "model_revision_display": "string (attested display metadata)",
      "owner_attribution": "owner-verified | submitter-attested",
      "tier": 3,
      "prompt_variant": "canonical",
      "assistance_class": "unassisted",
      "generation_profile_sha256": "sha256:...",
      "official_score": 0.93,
      "record_score": 0.95,
      "worst_score": 0.90,
      "standard_deviation": 0.0216,
      "submission_count": 3,
      "campaign_status": "completed",
      "robustness_group_id": "uuid | null",
      "robustness_score": 0.88,
      "completed_at": "ISO 8601",
      "scoring_cohort_id": "sha256:..."
    }
  ]
}
```

**Leaderboard publication rule**: every campaign with at least one public completed run appears,
including provisional and stale campaigns with those labels. Each row represents exactly one tier and
one prompt variant, assistance class, and generation profile. Rankings include only completed
three-run campaigns in the current scoring cohort and are partitioned by the complete §11.5 selection
key.
Robustness is a separate parent-group value and appears only when all three child campaigns are
complete. No "best version" roll-up is presented as an official model result.

#### GET /leaderboard/runs

Returns every append-only public summary for a completed grading run without aggregation loss.
Security-rejected uploads and jobs that failed before grading expose no attacker-controlled metadata.
Raw submissions, full reports, and diff artifacts remain private under §25.7.1.

Every row includes `verification_scope`, `verification_label`, campaign/slot/variant/tier bindings,
assistance class, generation-profile hash, nullable generation seed, all scoring-cohort fields from
§9.4, `canonical_package_hash_profile_sha256`, artifact byte/canonical hashes, the recomputed
candidate digest and gold duplicate-check outcome, score/eligibility/disqualification state, every
anti-cheat disposition and affected-slide list, attestation, and timestamps.

#### GET /leaderboard/history

Historical leaderboard snapshots for tracking progress over time.

#### Resource and state invariants

The normative OpenAPI and database migration encode these minimum resources and constraints:

- `model_identity(model_key PK, submitter_id, display_name, owner_attribution, created_at)`; immutable
  identity fields, audited display-label aliases only
- `model_revision(model_revision_key PK, model_key FK, immutable_payload_json,
  immutable_payload_sha256, created_at)`; no update/delete after creation
- `generation_profile(generation_profile_sha256 PK, submitter_id FK, model_revision_key FK,
  canonical_profile_json, created_at)`; hash is recomputed from RFC 8785 bytes, profile is immutable,
  and authorization is tenant/revision scoped
- `scoring_cohort(scoring_cohort_id PK, scoring_manifest_sha256,
  grader_source_tree_sha256, environment_attestation_sha256, benchmark_version, state)`; a database
  constraint or trigger verifies the §9.4 derivation
- `campaign(campaign_id PK, submitter/model/revision/cohort FKs, tier, prompt_variant,
  assistance_class, generation_profile_sha256, window_id, opens_at, closes_at, status)` with a
  uniqueness constraint over the complete §11.1 key
- `robustness_group(robustness_group_id PK,
  identity/cohort/tier/assistance_class/generation_profile_sha256/window binding)` and exactly three
  child links unique by `(robustness_group_id, prompt_variant)` and by child `campaign_id`
- `submission_reservation(submission_id PK, campaign_id FK, slot_ordinal, state, created_at)` with
  unique `(campaign_id, slot_ordinal)` and ordinal constrained to 1..3
- `grading_run(run_id PK, submission_id UNIQUE FK, immutable_public_json,
  immutable_public_sha256, created_at)`; append-only and never updated or deleted

Slot reservation is serialized transactionally per campaign. `reserved -> occupied` occurs exactly
once when any grading/diagnostic report is committed; ineligible reports persist score `0.0` for
campaign aggregation. `reserved -> released` is allowed only for a service failure proven to occur
before any report was committed. Campaign completion, robustness completion, and leaderboard
aggregates are derived from immutable occupied runs, never mutable cached scores. Database migrations
must enforce these invariants under concurrent submissions, not only application code.

Every mutating endpoint requires an `Idempotency-Key`. Keys are scoped to authenticated submitter and
route for 24 hours: replaying the same canonical request returns the original status/body, while reuse
with a different payload returns `409 idempotency_conflict`. Errors use one schema:

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "non-sensitive human description",
    "retryable": false,
    "request_id": "uuid"
  }
}
```

Authentication failure is `401`; authorization failures and non-owned opaque resource IDs both return
`404 resource_not_found` to prevent cross-tenant enumeration; invalid state transitions return `409`;
schema errors return `422`; rate limits return `429` with `Retry-After`. The OpenAPI enumerates the
endpoint-specific stable codes, including `identity_not_found`, `revision_immutable`,
`campaign_conflict`, `robustness_group_conflict`, and the submission codes below.

### 25.3 Authentication and rate limiting

- API key authentication (issued per organization)
- Rate limits:
  - 10 submissions per hour per API key
  - one three-run campaign per `(submitter_id, model_key, model_revision_key, scoring_cohort_id, tier, prompt_variant)` per server-issued 7-day window
  - organization-level monthly quota applies across every model/revision key and cannot be reset by registering aliases
  - every transport-accepted upload counts against hourly/monthly quotas even if quarantine rejects it
    or its campaign reservation is later released
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

1. **Upload**: stream opaque bytes while enforcing transport limits, compute `submission_sha256`,
   write an immutable object version, and assign submission/campaign reservation IDs; do not open ZIP
   or XML in the API process
2. **Quarantine**: dispatch a fresh hardened sandbox running normative Stages 0 and 0.5; produce the
   schema-valid MCE-resolved package for accepted artifacts, emit the conditionally complete signed
   verdict binding both original and resolved digest/size/object versions plus every profile/hash
   outcome, and convert security, schema/OPC, and duplicate failures to their exact §11.1.1 terminal
   forms without ZIP/XML parsing in the API process
3. **Queue**: priority queue with per-tenant fairness, estimated wait time
4. **Worker dispatch**: assign the immutable resolved-package object version plus signed verdict to an
   isolated Docker container; rehash before any package parse and fail on mismatch; never dispatch the
   original upload to the grader
5. **Grade**: verify and atomically consume the signed handoff/lease, then execute grader Stages 1–6
   against only the resolved package with per-job timeout (max 10 minutes). Stages 0/0.5 are never
   rerun in or linked into the long-lived worker process
6. **Store**: write immutable run record with full provenance
7. **Publish**: append a public leaderboard run row for every completed `submission` report,
   including ineligible zero-score campaign slots; publish reference/baseline controls only in their
   separately labeled operational/descriptive evidence collections; update campaign/robustness
   aggregates only within the exact cohort

### 25.5 Worker isolation model

Each grading job runs in a fresh, ephemeral Docker container:

- container is created from the canonical grading Docker image (§9.7)
- no network egress from the container during grading
- no persistent state between jobs (container is destroyed after grading completes)
- LibreOffice crash recovery follows §11.1.1: the container is killed after timeout, but only an infrastructure-attributed crash/timeout is
  `failed`/retryable; a failure reproduced from the same resolved artifact in a fresh worker is a
  completed-ineligible artifact outcome
- worker pool auto-scales based on queue depth using standard container orchestration (Kubernetes, ECS, etc.)
- containers are Linux-based — no Windows or Office licensing required at any scale
- security hardening: rootless containers, read-only rootfs, dropped capabilities (`--cap-drop=ALL`), `--security-opt=no-new-privileges`, seccomp profile, CPU/memory/PID limits, no host mounts beyond controlled scratch space

### 25.6 Results storage and provenance

Each grading job produces an immutable kind-conditional record containing:

- grading_mode (`local | hosted`); service records and every public row require `hosted`
- verification_scope and the exact verification_label from §1.1
- run_kind (`submission`; `reference_control`/`baseline_control` use separate signed, non-leaderboard
  conditionals in the report schema)
- submission_id, campaign slot ordinal, prompt variant, and robustness-group ID if any
- submitter_id, model_key, model_revision_key, campaign_id, targeted tier, assistance class,
  generation-profile SHA-256, and nullable generation seed
- original submission SHA-256, MCE-resolved-package SHA-256, and `canonical_package_hash_v1`
- `canonical_package_hash_profile_sha256`, gold byte hash, gold
  `canonical_package_hash_v1`, recomputed candidate canonical digest, and duplicate-check result
- benchmark_version, scoring_cohort_id, scoring_manifest_sha256,
  grader_source_tree_sha256, and environment_attestation_sha256
- prompt, checklist, schema/XSD, MCE-profile, asset, and font bundle hashes
- grader package hash
- libreoffice_version (exact build string)
- Poppler, Python, Pillow, NumPy, scikit-image, and lxml versions
- OCI image digest and platform
- grading_started_at / grading_completed_at (UTC)
- environment attestation payload whose canonical SHA-256 matches
  `environment_attestation_sha256`
- targeted score, every flag with disposition, and submitter attestation
- full report SHA-256 and §26.1.1 `score_semantic_report_sha256`
- full JSON report
- per-slide diff artifacts (stored in object storage, retained for 90 days)

For `grading_mode: hosted, run_kind: submission`, the public leaderboard run row exposes every applicable field above except raw
artifacts, private report details, and diff files. Control records require null
submission/campaign/model fields and are exposed only in the separate evidence collections from
§18.4.1. Scores are comparable or aggregatable only when `scoring_cohort_id` and all three component
hashes in §9.4 match exactly. The service recomputes the cohort ID before publication. Benchmark-
version equality alone is insufficient.

### 25.7 Model attestation

Leaderboard entries require attestation:

- `method`: free-text description of how the model generated the deck (e.g., "GPT-4o with python-pptx tool use, single-pass generation")
- `human_intervention`: boolean flag; true if any human edited the output
- `post_processing`: boolean flag; true if any programmatic post-processing modified the model output
- `external_resources_used`: boolean flag; true if external URLs, APIs, or renderers were accessed during generation
- `external_resources_description`: free-text description of external resources (required if `external_resources_used` is true)

Submissions with `human_intervention: true` are displayed in a separate leaderboard section ("Human-Assisted").

Attestation is on the honor system in v1. It is displayed as **generation-attested**, never as
generation-verified. Automated generation verification (e.g., requiring the model to generate via
an API endpoint the service calls directly) is planned for v2 ("Execution Mode").

### 25.7.1 Report and artifact access control

- **Full JSON reports** are visible only to the submitter (authenticated via API key)
- **Leaderboard campaign summaries and append-only run rows** described in §§25.2 and 25.6 are public
- **Per-slide diff artifacts** are visible only to the submitter for 90 days
- **Gold deck exports** and checklist definitions are always public
- Submitters may opt to make their full report public (one-way toggle, not reversible)

### 25.8 Network access policy (hosted mode)

For hosted-mode leaderboard submissions in v1, the generation process is:

- the model receives the prompt, reference images, and asset manifest
- the model produces a .pptx file
- the .pptx file is uploaded to the service

**v1 limitation**: the service cannot enforce generation-time network restrictions because it only grades uploaded artifacts. The attestation model (§25.7) requires disclosure of external resource use. This is an honor-system disclosure, not a technical enforcement.

In v2 ("Execution Mode"), the service will provide a sandboxed generation environment where the
model API is called directly and the output is captured without intermediate human, network, or
tool access. Only Execution Mode submissions may be marked **generation-verified**. This does not
change the v1 guarantee that official hosted scores are grading-verified.

### 25.8.1 Frozen benchmark cohorts

Campaign creation against an unknown, frozen, or superseded cohort (§26.4) is rejected with
`invalid_scoring_cohort`; the response lists active cohort IDs and benchmark versions. Existing open
campaigns derive `accepts_until` from the signed freeze/supersede effective time, accept no reservation
at or after it, allow already reserved jobs to finish, then derive `completed` or
`closed-incomplete` under §11.5.1. Their immutable window/closes fields are never rewritten;
completed history remains public.

### 25.9 Abuse prevention

Service-level abuse prevention (distinct from benchmark anti-cheat in §18):

- **Upload validation**: reject non-ZIP files, oversized files, ZIP bombs, encrypted archives
- **Account reputation**: track submission quality; accounts with repeated malicious submissions are suspended
- **Job kill threshold**: any grading job exceeding 10 minutes or 2 GB RAM is killed
- **Egress policy**: grading containers have no outbound network access
- **Ban/appeal flow**: suspended accounts can appeal via email; response within 5 business days
- **Denial-of-service protection**: standard CDN/WAF in front of the API
- **Cross-tenant authorization**: every submission, report, artifact, campaign, and webhook route is covered by IDOR tests using two distinct tenants
- **API-key lifecycle**: keys are stored only as salted hashes and support rotation, overlap windows, immediate revocation, and audit logging
- **Webhook secret handling**: webhook secrets and signed payload keys are never logged or returned after creation
- **SSRF corpus**: tests include DNS rebinding, redirects, IPv4-mapped IPv6, IPv6 zone identifiers, alternate numeric IP forms, and public-to-private resolution changes

### 25.10 Cost model

Infrastructure cost per grading job (estimated):

- Linux Docker container: ~$0.02–0.08 per job (spot instance, 10-minute max, no Windows/Office license)
- Storage: ~$0.01 per job (report + artifacts, 90-day retention)
- Total: ~$0.15–0.35 per submission

Pricing model:

- Free tier: 30 submissions/month (subsidized)
- Organization tier: $1 per submission (covers infra + margin)
- Enterprise: custom pricing with SLA

### 25.11 Reliability, observability, and recovery

V1 launch SLOs and operating signals are explicit:

- control-plane/API monthly availability target: 99.5%, excluding announced benchmark freezes
- p95 latency below 500 ms for non-upload metadata reads and below 2 seconds from completed upload
  body receipt to durable reservation/quarantine dispatch
- 99% of non-abusive grading jobs reach a terminal state within 10 minutes; queue time is measured and
  displayed separately from grading time
- backpressure rejects before body upload with `429`/`Retry-After` when durable queue or worker
  capacity thresholds are exceeded; it never accepts bytes that cannot be durably tracked

Structured logs carry `request_id`, immutable tenant/resource IDs, stage, cohort ID, image digest, and
error code. API keys, webhook secrets, raw attestation text, PPTX/XML bytes, and signed URLs are never
logged. Metrics include request/error/latency by route, upload bytes, quarantine disposition, any
handoff mismatch, queue depth/age, worker stage duration/failure, campaign reservations/occupancy,
webhook attempts, public-run publication lag, and drift-canary state. Alerts fire immediately on any
drift block or handoff mismatch, and on sustained API/queue/worker SLO breach.

The relational database uses automated encrypted backups with point-in-time recovery; immutable
object versions and public-run rows have lifecycle policies that preserve the retention promised by
§25.6/§25.7.1. Before launch, a restore drill must recover campaign/run consistency into an isolated
environment and reproduce public-row hashes. Deployments use health-gated rolling replacement and a
documented rollback; a scorer/environment change cannot roll back across cohort identity boundaries.

## 26. Versioning and Governance

### 26.1 Version scheme

`gloss-vMAJOR.MINOR.PATCH`

- **MAJOR**: new slide set, official prompt variants, tiers, assertion/checklist/scoring changes, or any
  breaking change. Scores across major versions are not comparable.
- **MINOR**: documentation clarifications, new informational report fields, or explicitly non-scoring
  experimental prompt variants. MINOR versions MUST NOT add, remove, or re-weight scored assertions,
  change official variants, or change pass/fail rules. The complete conformance corpus must remain
  byte-identical at the score-semantic projection layer below.
- **PATCH**: documentation or implementation changes that also produce byte-identical score-semantic
  projections for the complete conformance corpus. A score-affecting change requires a MAJOR version.

### 26.1.1 Score-semantic report projection

`schemas/report-semantic-projection.schema.json` defines the only cross-build equality surface. From a
schema-valid full report, implementations construct an object containing exactly: projection schema
version; grading mode; run kind; targeted tier and prompt variant; performed/valid/complete stage booleans;
`scoring_completed`; eligibility, disqualification reasons, repair and duplicate outcomes; targeted/tier score and
weighted counts; ordered slide/deck item IDs with pass state, severity, weight, stable outcome code,
and tier-affected slides; ordered anti-cheat rule IDs/dispositions/affected slides; and ordered stable
schema/verification error codes and package part locators. Arrays use the schema-prescribed UTF-8
item/rule/code ordering and numeric values use JSON numbers permitted by the schema.

The projection excludes submission/run/campaign/model/tenant IDs, timestamps, durations, URLs,
display/free-text fields, attestation, seeds, artifact/report/diff hashes, all scoring-cohort and
provenance/profile hashes, environment/version identities, stack traces, diagnostics text, and every
additive informational item/metric. It rejects unknown fields. The canonical bytes are RFC 8785 JSON,
and `score_semantic_report_sha256` is their SHA-256. The full report is independently hashed and may
differ across runs or compatible cohorts; it is never the compatibility gate. Changing projection
membership, any included value, or the projection schema is score-semantic and requires a MAJOR
version unless the complete frozen corpus proves the resulting canonical projection bytes unchanged.

No semantic version claim permits aggregation across scoring cohorts. Projection-identical MINOR/PATCH
cohorts may be displayed as compatible historical cohorts, but §9.4 exact-hash grouping still applies.

### 26.1.2 Rerun policy

Historical submissions are never rewritten. A MINOR or PATCH with any changed cohort component
creates a new scoring cohort even when the complete conformance corpus projection is byte-identical; its runs
remain separate. When a MAJOR version is released, submitters must explicitly resubmit.

### 26.2 Grader versioning

The grader is versioned independently. A replacement grader may serve an active benchmark only
after the complete positive, negative, mutation, security, and determinism corpus produces
byte-identical score-semantic projections. It receives a new grader hash and scoring cohort; it is never
aggregated with earlier runs. If any score-semantic projection differs, the change is score-affecting and
requires a new benchmark MAJOR version.

### 26.3 Environment versioning

The Docker/LibreOffice environment is versioned independently. An environment is never updated in
place. A replacement OCI digest may serve an active benchmark only after the complete conformance
corpus produces byte-identical score-semantic projections. It forms a new scoring cohort and remains
separate from earlier environment hashes. Any difference requires a new benchmark MAJOR version.

### 26.4 Leaderboard freezing

Release-index state transitions are forward-only on the signed §9.4.3 chain:

- `active -> frozen -> superseded` is allowed; reversing a state or publishing a lower-sequence
  active index is invalid
- exactly one accepted chain head is active for new campaign creation; an index may be issued before
  `effective_at`, but does not change serving state until that instant
- workers finish already consumed verdicts against their bound cohort; new reservations and verdicts
  use only the effective active head

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

The following is an abridged, parseable hosted-submission illustration, not a conformance fixture.
`schemas/report.schema.json` is normative and requires the complete provenance/attestation and
kind/mode/state conditionals described in §§1.1, 11.1.1, and 25.6.

```json
{
  "benchmark_version": "gloss-v1.0.0",
  "grading_mode": "hosted",
  "run_kind": "submission",
  "grader_version": "1.0.0",
  "verification_scope": "artifact_conformance",
  "verification_label": "grading-verified artifact score; generation-attested",
  "scoring_cohort_id": "sha256:...",
  "scoring_manifest_sha256": "sha256:...",
  "grader_source_tree_sha256": "sha256:...",
  "environment_attestation_sha256": "sha256:...",
  "grader_package_sha256": "sha256:...",
  "oci_image_digest": "sha256:...",
  "prompt_bundle_sha256": "sha256:...",
  "scored_assertion_inventory_sha256": "sha256:...",
  "checklist_bundle_sha256": "sha256:...",
  "schema_bundle_sha256": "sha256:...",
  "schema_root_map_sha256": "sha256:...",
  "mce_profile_sha256": "sha256:...",
  "canonical_package_hash_profile_sha256": "sha256:...",
  "asset_manifest_sha256": "sha256:...",
  "font_manifest_sha256": "sha256:...",
  "submission_id": "uuid",
  "campaign_id": "uuid",
  "campaign_slot": 1,
  "targeted_tier": 3,
  "prompt_variant": "canonical",
  "assistance_class": "unassisted",
  "generation_profile_sha256": "sha256:...",
  "generation_seed": null,
  "submission_sha256": "sha256:...",
  "mce_resolved_package_sha256": "sha256:...",
  "canonical_package_hash_v1": "sha256:...",
  "gold_submission_sha256": "sha256:...",
  "gold_mce_resolved_package_sha256": "sha256:...",
  "gold_canonical_package_hash_v1": "sha256:...",
  "gold_duplicate_check": "clear",
  "schema_valid": true,
  "schema_validation_performed": true,
  "visual_verification_performed": true,
  "verification_complete": true,
  "scoring_completed": true,
  "disqualification_state": "none",
  "ineligibility_reasons": [],
  "repair_triggered": false,
  "grading_duration_seconds": 23.4,
  "fidelity_score": 0.847,
  "campaign_contribution": 0.847,
  "passed_items": 287,
  "total_items": 312,
  "deck_passed": false,
  "eligible": true,
  "score_semantic_report_sha256": "sha256:...",
  "environment_attestation": {
    "schema_version": "1.0",
    "payload": "validates against schemas/environment-attestation.schema.json"
  },
  "tier_scores": {
    "level_1": null,
    "level_2": null,
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
  "attestation": {
    "method": "GPT-4o with python-pptx tool use",
    "human_intervention": false,
    "post_processing": false,
    "external_resources_used": false
  },
  "anti_cheat_flags": [
    {
      "rule_id": "deck.master-reuse",
      "disposition": "zero_affected_slides",
      "affected_slides": [6],
      "tier_affected_slides": [6]
    }
  ],
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

The example is a hosted submission. `report.schema.json` conditionally requires the exact hosted
label and non-null hosted bindings for that form. A local submission uses the local label and null
hosted identity/campaign/slot bindings required by §1.1, may still have
`scoring_completed: true`/`deck_passed: true`, but always has `eligible: false`,
`campaign_contribution: 0.0`, `disqualification_state: non_official_local`, and
`ineligibility_reasons: ["local_mode"]`.

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

Deliverables: deck-level prompt, per-slide prompt/spec files, paraphrased variants, and the frozen
prompt-requirements oracle. Prompts are designed BEFORE the gold deck per §13.1. At least three
blinded implementations must each satisfy every mandatory prompt-sourced requirement; pairwise scene-
graph similarity is diagnostic only and has no percentage release gate.

### Phase 2. Gold deck design matrix

Deliverables: final slide matrix for 20 slides with tier assignments, master/layout design, asset list, multilingual content plan, checklist category map, severity assignments

### Phase 3. Gold deck authoring

Deliverables: gold `.pptx` authored in LibreOffice Impress from validated prompts, bundled libre fonts, approved asset mirrors with licenses, exported reference PNGs from canonical Docker environment, ECMA-376 schema validation pass

### Phase 4. Scene graph extraction

Deliverables: OOXML parser, ECMA-376 schema validator, normalized scene graph schema with semantic equivalence rules, saved gold scene graph fixtures

### Phase 5. Visual comparator and anti-cheat rules

Deliverables: SSIM comparator with fixed-threshold validation against the complete positive/negative
corpus, media hash inventory checker, full-slide and tiled-raster cheat detection, off-canvas and
hidden-content checks, raster-area calculations

### Phase 6. Checklist engine

Deliverables: declarative checklist schema with severity tiers, evaluator runtime, slide-level and deck-level item execution, per-tier scoring, aggregate fidelity score computation

### Phase 7. Grader test suite and baseline measurement

Deliverables: positive fixtures, single-fault negative fixtures (including anti-cheat, MCE, duplicate,
and quarantine-handoff cases), complete assertion mutation matrix, determinism tests (100-run export
stability), and **descriptive baselines** (§13.4)—human expert, programmatic copy, and naive LLM—
published with provenance. Deviations from §24.7 bands are investigated but are not acceptance failures.

### Phase 8. Hosted service MVP

Deliverables: submission API, quarantine pipeline, worker container automation, results storage, basic leaderboard, API key management, rate limiting

### Phase 9. Public release and leaderboard

Deliverables: versioned benchmark release, grader CLI, benchmark README, submission instructions, report schema, leaderboard website, drift canary automation, governance documentation

## 29. Acceptance Criteria for v1

`Gloss v1` is complete when all of the following are true:

Schemas, empty directories, candidate metadata, and pending review records are not evidence that a
gate passed. While this document is Draft, the release validator MUST fail if concrete signed
`scoring-manifest.json`/`release-index.json`, gold evidence, scene-graph fixtures, baseline evidence,
or reviewer approvals are absent. Those instances are created only from real frozen artifacts and
observed runs; placeholders or synthetic approvals are forbidden.

- benchmark package is fully public and self-contained
- the canonical document header is exactly `Status: Frozen — gloss-v1.0.0` and the public README
  no longer carries a pre-release warning; release-tag CI fails closed on either mismatch
- OpenSpec, OpenAPI, scoring manifest, prompt-requirements oracle, MCE profile, and all normative JSON Schemas are frozen and content-addressed
- the release index and scoring manifest pass JCS/hash/cohort recomputation and an authorized Ed25519
  release signature verifies against `RELEASE_KEYS.json`
- the complete signed release-index chain verifies from trusted genesis through the persisted highest
  head; rollback/fork/gap/state/effective-time fixtures fail closed
- grader-source-tree and environment-attestation payloads validate against their normative schemas,
  recompute exactly by §§9.4.1–9.4.2, and match every report/cohort field
- all bundled fonts are libre/open-source with clear licensing
- canonical `linux/amd64` OCI digest and every renderer/rasterizer/library input are pinned; no mutable runtime dependency remains
- gold deck exists and exports stable reference images in the canonical Docker environment; the
  bound §9.4.4 evidence contains exactly 100 runs, 4,950 run pairs, and 99,000 page comparisons, with
  every recomputed per-page and global minimum SSIM ≥ 0.99999 (consistent with §22.3)
- one published gold-evidence record binds the same exact MCE-resolved package to OPC/XSD validation,
  export, scene graph, duplicate comparison, mutation parentage, and all signed reference controls
- all blinded independent-author prompt-validation rounds pass the frozen prompt requirements oracle
- descriptive baseline scores exist for human expert, programmatic copy, and naive LLM
- difficulty tiers (Level 1/2/3) are defined with distinct slide assignments
- grader runs fully automatically in the canonical Docker environment (Linux + LibreOffice)
- three separate signed gold `reference_control` runs (one per targeted tier) score perfect, publish
  operational evidence, and cannot enter any campaign or leaderboard path
- representative broken fixtures fail the correct checklist items with correct severity
- every scored rule and anti-cheat rule has an independent positive fixture, single-fault negative fixture, and published mutation expectation; every required mutant is killed
- the complete prompt/reference-image/asset assertion inventory has immutable provenance and every
  checklist item traces to exactly one assertion; gold OOXML creates no scored requirement
- every assertion validates against the §4.1 provenance compatibility matrix; incompatible
  reference-image/asset claims and native/editability claims without prompt provenance fail release
- the full MCE conformance corpus covers supported and unsupported `AlternateContent`, `Ignorable`,
  `MustUnderstand`, `ProcessContent`, `PreserveElements`, `PreserveAttributes`, malformed QName data,
  and every unmapped content-type/root pair, with fail-closed expected outcomes
- the OPC corpus covers every §15.1 content-type, part-name/case, root-relationship, URI/target,
  dangling/orphan, exact `p:sldSz`, slide-count, and PDF page-count/geometry rule with one positive and
  single-fault negative fixture per rule
- the canonical package-hash profile is published and its exact-gold, ZIP-repacked-gold,
  volatile-metadata, unknown/orphan-part, and close non-gold fixtures all match expected outcomes
- the complete fixed-SSIM-threshold rejection corpus scores below `0.9999`; any scoring-rule change
  restarts the freeze or creates a new MAJOR version
- image fakery, tiled composite, text-on-raster, and structural cheat cases are caught
- multilingual, master/layout, table, chart, field, grouping, z-order, bullet/paragraph, and spacing checks are implemented
- fidelity score output is deterministic
- full reports validate their terminal-state conditionals and the complete conformance corpus produces
  byte-identical §26.1.1 score-semantic projections under every claimed compatible implementation
- severity-weighted scoring produces expected results
- no human review is required anywhere in the grading loop
- drift canary is operational
- hosted service API accepts submissions and returns graded results
- leaderboard labels every result exactly `grading-verified artifact score; generation-attested`, rejects published gold duplicate hashes, and exposes immutable public run rows with complete scoring-cohort provenance
- quarantine pipeline rejects malicious .pptx files (verified with evasion test suite)
- untrusted ZIP/XML parsing occurs only in the disposable quarantine sandbox, never the API/control plane
- signed quarantine verdicts bind both original and resolved digest/size/object versions plus all
  profile/schema/canonical-package hashes, duplicate result, run kind, control authorization, and
  campaign/slot identity; the worker verifies Ed25519 signature, expiry, atomic lease generation,
  single-use nonce, and binding, receives only the resolved package, rehashes before parsing, and every
  tamper/replay/quarantine-to-worker TOCTOU fixture fails closed
- the end-to-end §24.5 gate proves opaque upload → disposable signed quarantine/resolution → one-time
  worker consume → Stages 1–6 → atomic report/slot commit → externally readable immutable public row,
  including eligible and every required completed-ineligible/pre-report outcome
- worker isolation prevents cross-job contamination
- version comparability rules are documented and enforced by the API
- leaderboard correctly handles single-tier campaigns, first-three-run mean scoring, stable server-issued identity keys, provisional/stale states, robustness campaigns, and strict scoring-cohort separation
- campaign/window conformance proves immutable assistance class and generation-profile hash, nullable
  seed propagation, exact UTC window construction, terminal-state/slot table, and full-key default
  selection; robustness children match both assistance/profile fields
- campaign conformance tests cover immutable tier/variant bindings, graded-ineligible zero slots,
  service-failure slot release, atomic three-child robustness groups, enum-only variants, quota/alias
  resistance, exact cohort grouping, and anti-cheat affected-slide intersection with the targeted tier
- every API score, leaderboard campaign, robustness group, and public run row includes exactly
  `grading-verified artifact score; generation-attested` and `verification_scope: artifact_conformance`
- normative local reports use exactly `local artifact score; self-reported`, cannot carry hosted
  campaign/model bindings, remain ineligible with zero campaign contribution, and are rejected from
  every hosted publication path
- production observability covers every §25.11 signal, alert routing is tested, and an isolated
  database/object restore drill reproduces immutable campaign and public-run hashes
- dispute resolution process is documented and has a designated maintainer
- normative JSON Schemas are published and exercised for checklist items, scored assertions/inventory,
  reports and semantic projections, source-tree/environment attestations, release indexes, control
  handoffs, submission terminal states, gold evidence, normalized scene graphs, and baseline evidence

## 30. Risks and Mitigations

### Risk 1. LibreOffice export instability

Mitigation: pin LibreOffice version and Docker image, bundle libre metric-compatible fonts, run 100-export determinism test before releasing, deploy drift canary for ongoing monitoring, use SSIM threshold instead of exact pixel match as primary criterion

### Risk 2. Structural equivalence is harder than visual equivalence

Mitigation: define item-scoped semantic equivalence classes early (§5.2), derive comparison rules from
the frozen scored-assertion inventory, use gold only as a control fixture, and validate alternative
valid implementations plus single-fault mutants before release

### Risk 3. Too many checks become unmaintainable

Mitigation: use a declarative checklist with severity tiers, derive scored assertions from the frozen prompt requirements oracle, allow gold extraction only for reviewed diagnostics, and keep item phrasing concise and machine-verifiable

### Risk 4. Gold deck accidentally contains ambiguous implementation choices

Mitigation: use the prompt-derived requirements-oracle and blinded-author process (§13.1 steps 2–4), ensure slides that require native constructs explicitly say so in prompts, and test multiple valid implementations plus single-fault mutants before the freeze

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

Mitigation: validate every anti-cheat heuristic against the full set of passing and failing fixtures before release. Publish the expected false-positive rate per rule. Allow submitters to dispute anti-cheat flags via the governance process (§26.5). Anti-cheat flags do not suppress leaderboard publication — they zero affected slide scores, so the impact is proportional and visible.

### Risk 12. Score churn from environment/grader changes

Even within a frozen benchmark version, grader patches or OS security updates could subtly change scores.

Mitigation: the drift canary (§9.6) detects environment changes. Grader PATCH versions must not change scores (§26.1). If a bug fix would change scores, it requires a MAJOR version bump (since MINOR must preserve comparability). The rerun policy (§26.1.1) ensures historical scores are never silently invalidated.

## 31. Recommended Immediate Next Steps

**Phase A — Contract publication (encode the locked decisions into implementable schemas):**

1. Publish normative JSON Schemas for checklist items and report format (encoding the rules in §§10, 12, 27).
2. Publish OpenAPI spec for the hosted-service API (encoding the contracts in §25).
3. Publish the asset manifest schema with primary byte hashes (encoding §8.3).
4. Validate all schemas against the spec examples to catch inconsistencies before implementation begins.
5. Publish the scoring manifest, prompt-requirements oracle, scored-assertion inventory, MCE profile,
   schema/root mapping, canonical-package-hash profile, and complete fixture/mutation index.

**Phase B — Benchmark construction:**

6. Validate the bundled font set (Liberation, Noto, Noto CJK, Carlito, Caladea — as specified in the Dockerfile §9.7).
7. **Design and validate prompts** for the v1 slide matrix (prompt-first per §13.1). Run independent author convergence tests.
8. Freeze the v1 slide matrix with tier assignments and checklist category taxonomy.
9. Build and pin the canonical Docker image (LibreOffice version + fonts).
10. Define the benchmark directory structure and manifest schemas.
11. Author a 5-slide Level 1 pilot deck from validated prompts in LibreOffice Impress.
12. Build the export and scene-graph extraction pipeline against the pilot.
13. Validate the frozen `0.9999` SSIM threshold using 100 repeated gold exports plus the complete
    negative mutation corpus; do not tune it to fit baselines.
14. Validate anti-cheat rules on intentionally broken pilot decks.
15. Expand to Level 2 and Level 3 only after determinism and grading logic are stable.

**Phase C — Baseline measurement and release:**

16. Run the three descriptive baselines and publish scores (requires the complete grading pipeline from Phase B).
17. Publish and investigate baseline deviations from the descriptive bands (§24.7). A diagnosed
    contract defect restarts the affected freeze; baseline outcomes never authorize tuning.

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
