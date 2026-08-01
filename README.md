# Gloss

**Gloss — Generative Layout & OOXML Scoring System** is an open tool for testing
whether a generated PowerPoint is a real, editable artifact—not merely a convincing
screenshot.

Gloss grades both sides of a deck:

- **Looks right:** rendered pixels, typography, geometry, and visual consistency.
- **Built right:** native shapes, charts, tables, layouts, masters, text semantics,
  relationships, and package safety.

**[gloss.tools](https://gloss.tools)** ·
[Issues](https://github.com/aronchick/gloss/issues) ·
[Pull requests](https://github.com/aronchick/gloss/pulls) ·
[Contributing](CONTRIBUTING.md)

> **A screenshot is not a PowerPoint.** The artifact is the product.

## The ACID idea

The browser ACID tests made standards failures impossible to hand-wave away: every
browser received the same hostile, public artifact, and everyone could inspect the
result. They targeted open web standards rather than one browser's preferred output.

Gloss brings that **ACID-test philosophy** to generated presentations:

- publish the torture cases instead of hiding them;
- grade the final `.pptx`, not a generation trace or a screenshot;
- test both visible output and standards-based OOXML structure;
- make every assertion, fixture, score, and failure reproducible;
- fail closed when required evidence or rendering stages are missing;
- invite the community to add cases and make the grader stricter.

Here, **ACID refers to the public browser conformance-test tradition, not database
transactions**.

## Product and suite

**Gloss** is the tool and public project. It owns the scoring model, evidence
surface, comparative results, hosted verification direction, and collaboration
workflow.

**Gloss v1 is the first ACID-style PowerPoint conformance suite bundled with
Gloss.** It supplies the current prompt corpus, hostile deck cases, assertions, gold
fixture, mutation tests, and protocol adapter:

| Name | Role |
| --- | --- |
| **Gloss** | The tool and public project |
| **ACID tests** | The open conformance-testing philosophy |
| **Gloss v1** | One bundled benchmark protocol and corpus |

> **Technical-preview status:** the bundled
> [`GLOSS_OPENSPEC.md`](GLOSS_OPENSPEC.md) contract is still Draft and its
> official-release gates remain incomplete. Gloss is live for public collaboration,
> but no result should be treated as an official model leaderboard until a release
> announcement names a frozen scoring cohort.

## Technical preview evidence

The current Gloss v1 candidate suite contains 280 schema-valid checks across
rendered pixels and native package structure. Its generated operator suite passes
280/280 positive controls and detects 280/280 generated single-fault mutations.
This proves configured operator behavior only; it is not independent assertion
evidence and it is not a model leaderboard.

Every public count is recorded in
[`site/evidence/preview-v1.json`](site/evidence/preview-v1.json) and checked against
the committed mutation reports:

```bash
node launch/verify-launch.mjs
```

## Frozen Gloss comparison

Gloss includes a frozen comparative bundle produced against Gloss v1:
[`gloss-v1/benchmark/comparative-v1`](gloss-v1/benchmark/comparative-v1).
It contains four repository-owned generation paths, three public seeds per path,
and 12 editable 20-slide decks. The canonical Linux/amd64 grader completed all
240 slide renders.

The current local artifact scores are 67.68% for the native paths and 62.32% for
the visual paths. These are reproducible workflow baselines, not model rankings.
Every report says `local artifact score; self-reported` and carries no model
attribution.

Reproduce every deck, report, hash, and public bar:

```bash
./gloss-v1/benchmark/comparative-v1/reproduce.sh
```

Release mode intentionally fails until independent prompt convergence, assertion
provenance and evidence, reviewer approvals, baselines, environment manifests, and
signed release indexes are complete.

## Score provenance

- **Local grading** measures a deck on the caller's machine. Local results are
  self-reported and are not official leaderboard verification.
- **Hosted grading** runs the same protocol adapter inside the controlled Gloss
  environment. Every public submission score must carry the exact label
  `grading-verified artifact score; generation-attested`.
- Generation strategy, token count, cost, retries, and generation time are supplied
  by submitters. They remain **generation-attested** even when the deck itself was
  grading-verified.
- A report is not eligible when schema validation did not run or failed, the
  canonical renderer or reference exports were unavailable, required slides were
  not compared, or any required stage was incomplete.

## Repository layout

```text
site/                       Static gloss.tools source and public evidence
launch/                     Gloss film renderer, verifier, and launch copy
GLOSS_OPENSPEC.md           Draft contract for the bundled Gloss v1 suite
gloss-v1/
  benchmark/                ACID-style prompts, cases, checks, fixtures, and evidence
  grader/                   Gloss v1 protocol adapter and local CLI
  schemas/                  Bundled ECMA-376 Transitional XSD and report schemas
  service/                  Pre-release hosted grading components
  Dockerfile                Canonical Ubuntu 22.04 grading environment
```

## Run the bundled suite locally

Gloss currently exercises its first suite through the `gloss` CLI. Requirements:
[uv](https://docs.astral.sh/uv/), Python 3.12, LibreOffice Impress, and `pdftoppm`
from Poppler.

```bash
cd gloss-v1/grader
uv sync --extra dev --locked
uv run gloss validate ../benchmark/deck/gold/gloss-v1-gold.pptx
```

Full grading is fail-closed until a frozen release supplies signed cohort provenance
and the caller supplies a complete artifact-context handoff. During development,
use `validate` for the runnable quarantine/XSD smoke above. After the v1 release
artifacts are published:

```bash
uv run gloss grade ../submission.pptx \
  --tier 3 \
  --artifact-context ./artifact-context.json \
  --format json
```

Write a standalone report and private visual diffs:

```bash
uv run gloss grade ../submission.pptx \
  --tier 3 \
  --artifact-context ./artifact-context.json \
  --format html \
  --output report.html \
  --artifacts private-diffs/
```

The protocol CLI exits with status `2` when verification could not be completed.
A normally graded deck may receive a failing score without making the grading
command itself fail.

## Canonical container

```bash
docker build -t gloss-v1 gloss-v1
docker run --rm \
  --volume "$PWD:/workspace:ro" \
  gloss-v1 grade /workspace/submission.pptx --tier 3 \
  --artifact-context /workspace/artifact-context.json --format json
```

## Quality gates

```bash
cd gloss-v1/grader
uv run ruff check .
uv run ruff format --check .
uv run mypy gloss tests
uv run pytest --cov=gloss --cov-fail-under=85
uv build
uv run pip-audit
```

The bundled validator applies deterministic ECMA-376 Markup Compatibility
preprocessing before validating against the bundled Part 1 Transitional XSD set.
RELAX NG validation is outside the Gloss v1 contract.

## Build it with us

The ACID tradition works because hard cases are public. Help Gloss make generated
decks worth editing:

- [Propose a benchmark case](https://github.com/aronchick/gloss/issues/new?template=benchmark-case.yml)
- [Report a grader gap](https://github.com/aronchick/gloss/issues/new?template=grader-bug.yml)
- [Challenge evidence or a public claim](https://github.com/aronchick/gloss/issues/new?template=evidence-challenge.yml)
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a patch

## License

Code and benchmark materials are released under the
[Apache License 2.0](LICENSE), except third-party or asset files that carry their
own license notices.
