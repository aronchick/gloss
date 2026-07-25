# Contributing to Gloss

Gloss improves when a benchmark claim becomes easier to inspect, reproduce, or challenge. Small, evidence-backed pull requests are welcome.

## Good first contributions

- Add a PowerPoint construct the corpus does not cover.
- Reproduce a grader false positive or false negative.
- Improve a candidate assertion and its mutation fixture.
- Improve a deterministic comparative generation path and prove the score change.
- Review a prompt requirement, evidence record, or release gate.
- Make the documentation easier to run from a clean checkout.

Start with an [issue](https://github.com/aronchick/gloss/issues/new/choose). This lets contributors agree on the observable failure before investing in a fixture or implementation.

## Ground rules

1. Keep public claims traceable to committed evidence.
2. Do not add invented model results, scores, costs, or generation provenance.
3. Keep the public name **Gloss** and the protocol identifier `acidslide-v1` distinct.
4. Treat the OpenSpec as Draft until the release validator passes and maintainers freeze it.
5. Add or update tests for grader behavior changes.
6. Never commit private slide decks, credentials, customer data, or proprietary fonts.

## Local setup

Install [uv](https://docs.astral.sh/uv/), Python 3.12, LibreOffice Impress, and Poppler. Then:

```bash
git clone https://github.com/aronchick/gloss.git
cd gloss/acidslide-v1/grader
uv sync --extra dev --locked
uv run ../benchmark/validate_corpus.py
uv run pytest tests/test_mutation_fixtures.py -q
```

Run the full grader checks before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy acidslide tests
uv run pytest --cov=acidslide --cov-fail-under=85
uv build
uv run pip-audit
```

The hosted service has its own locked environment:

```bash
cd ../service
uv sync --extra dev --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy acidslide_service tests
uv run pytest --cov=acidslide_service --cov-fail-under=85
uv run pip-audit
```

## Adding a benchmark case

A benchmark change should identify:

- the natural-language requirement;
- the intended visual and native artifact behavior;
- the affected slides and tier;
- the verification method;
- a positive control;
- a single-fault negative fixture when the check is automatic;
- why the requirement came from the prompt or published assets rather than the gold deck.

Gold output does not create a requirement. Requirements must remain traceable to the public prompt, references, or allowed assets.

## Pull requests

Keep a pull request focused enough to review. In the description, include:

- the failure or gap;
- the changed contract or behavior;
- exact commands run;
- evidence files added or changed;
- any release claims that remain intentionally blocked.

CI must pass. Maintainers may ask for a smaller fixture, clearer provenance, or an explicit release-state caveat before merging.

## Launch surface

The static site lives in `site/`. Harness counts come from
`site/evidence/preview-v1.json`; comparative bars come from the byte-equivalent
public copy of `acidslide-v1/benchmark/comparative-v1/summary.json`. Verify both
sources, local assets, copy, and media metadata with:

```bash
node launch/verify-launch.mjs
```

Rebuild the silent 21-second launch film with:

```bash
node launch/render-video.mjs
```

The renderer requires `rsvg-convert` and `ffmpeg`. It reads the comparative
summary directly. Do not hand-edit a published number in the site or video.

## Conduct and security

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the process in [SECURITY.md](SECURITY.md), not a public issue.
