# Gloss

**Gloss — Generative Layout & OOXML Scoring System** is a public, machine-graded benchmark for PowerPoint artifact conformance against published
prompt, reference-image, and asset requirements. It evaluates native ECMA-376 PresentationML
structure and rendered output in one pinned environment; v1 does not verify which model generated an
artifact.

**[gloss.tools](https://gloss.tools)** · [Issues](https://github.com/aronchick/gloss/issues) · [Pull requests](https://github.com/aronchick/gloss/pulls) · [Contributing](CONTRIBUTING.md)

> **A screenshot is not a PowerPoint.** Gloss measures whether generated decks look right and are built right.

> **Pre-release status:** `ACIDSLIDE_OPENSPEC.md` is still Draft and the release gates are incomplete.
> No deployment should be treated as the official leaderboard until a release announcement names the
> frozen scoring cohort.

## Technical preview evidence

The current candidate harness contains 280 schema-valid checks across rendered pixels and native package structure. Its generated operator suite passes 280/280 positive controls and detects 280/280 generated single-fault mutations. This proves configured operator behavior only; it is not independent assertion evidence and it is not a model leaderboard.

Every launch count is recorded in [`site/evidence/preview-v1.json`](site/evidence/preview-v1.json) and checked against the committed mutation reports by:

```bash
node launch/verify-launch.mjs
```

Release mode intentionally fails until independent prompt convergence, assertion provenance and evidence, reviewer approvals, baselines, environment manifests, and signed release indexes are complete.

## Score provenance

- **Local grading** measures a deck on the caller's machine. Local results are self-reported and are not official leaderboard verification.
- **Hosted grading** runs the same grader inside the controlled Gloss environment. Every public
  submission score must carry the exact label
  `grading-verified artifact score; generation-attested`.
- Generation strategy, token count, cost, retries, and generation time are supplied by submitters. They remain **generation-attested** even when the deck itself was grading-verified.
- A report is not eligible when schema validation did not run or failed, the canonical renderer or
  reference exports were unavailable, required slides were not compared, or any required stage was
  incomplete.

## Repository layout

```text
ACIDSLIDE_OPENSPEC.md       Normative v1 contract
acidslide-v1/
  benchmark/                Prompts, assets, candidate checks, gold fixture, and mutation evidence
  grader/                   Local Python grader and CLI
  schemas/                  Bundled ECMA-376 Transitional XSD and report schemas
  service/                  Pre-release hosted API, worker, and leaderboard implementation
  Dockerfile                Canonical Ubuntu 22.04 grading environment
site/                       Static gloss.tools source and launch evidence
launch/                     Deterministic film renderer and launch copy
```

## Local development

Requirements: [uv](https://docs.astral.sh/uv/), Python 3.12, LibreOffice Impress, and `pdftoppm` from Poppler.

```bash
cd acidslide-v1/grader
uv sync --extra dev --locked
uv run acidslide validate ../benchmark/deck/gold/acidslide-v1-gold.pptx
```

Full grading is fail-closed until a frozen release supplies signed cohort provenance and the caller
supplies a complete artifact-context handoff. During development, use `validate` for the runnable
quarantine/XSD smoke above. After the v1 release artifacts are published:

```bash
uv run acidslide grade ../submission.pptx \
  --tier 3 \
  --artifact-context ./artifact-context.json \
  --format json
```

Write a standalone report and private visual diffs with:

```bash
uv run acidslide grade ../submission.pptx \
  --tier 3 \
  --artifact-context ./artifact-context.json \
  --format html \
  --output report.html \
  --artifacts private-diffs/
```

The CLI exits with status `2` when verification could not be completed. A normally graded deck may receive a failing score without making the grading command itself fail.

## Canonical container

```bash
docker build -t acidslide-v1 acidslide-v1
docker run --rm \
  --volume "$PWD:/workspace:ro" \
  acidslide-v1 grade /workspace/submission.pptx --tier 3 \
  --artifact-context /workspace/artifact-context.json --format json
```

## Quality gates

```bash
cd acidslide-v1/grader
uv run ruff check .
uv run ruff format --check .
uv run mypy acidslide tests
uv run pytest --cov=acidslide --cov-fail-under=85
uv build
uv run pip-audit
```

The bundled validator applies deterministic ECMA-376 Markup Compatibility preprocessing before validating against the bundled Part 1 Transitional XSD set. RELAX NG validation is outside the v1 contract.

## Build it with us

- [Propose a benchmark case](https://github.com/aronchick/gloss/issues/new?template=benchmark-case.yml)
- [Report a grader gap](https://github.com/aronchick/gloss/issues/new?template=grader-bug.yml)
- [Challenge evidence or a public claim](https://github.com/aronchick/gloss/issues/new?template=evidence-challenge.yml)
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a patch

## License

Code and benchmark materials are released under the [Apache License 2.0](LICENSE), except third-party or asset files that carry their own license notices.
