# Gloss comparative v1

This frozen bundle compares four deterministic, repository-owned PowerPoint
generation paths:

- `native-precise`
- `native-fast`
- `visual-precise`
- `visual-fast`

Each path has three seeded runs (`1103`, `2207`, `3301`). These are reproducible
workflow baselines, not model rankings. Every result is labeled:

> local artifact score; self-reported

Every generation record is labeled:

> repository-owned path; no model attribution

## Reproduce every bar

From the repository root:

```bash
./acidslide-v1/benchmark/comparative-v1/reproduce.sh
```

The command regenerates all 12 editable 20-slide decks, builds the pinned
Linux/amd64 grader image, grades all 240 slides, freezes artifact hashes, and
recomputes every published metric.

## Published artifacts

- `cohort.json` binds the local scoring cohort to the exact grader source,
  container, prompts, checklist, schemas, fonts, and assets.
- `manifest.json` freezes the hashes and metrics for all 12 runs.
- `summary.json` is the only source used by the public chart and launch video.
- `runs/<path>/run-<n>/` contains `deck.pptx`, `generation.json`,
  `artifact-context.json`, `report.json`, and `artifact-sha256.json`.
- `verify_bundle.py` independently checks archive structure, all hashes,
  disclosure labels, report completion, cohort identity, and summary math.

Metrics:

- **Local fidelity** — AcidSlide’s severity-weighted artifact score.
- **Visual SSIM** — mean full-slide similarity to the gold renders.
- **Native pass** — severity-weighted checklist pass rate with every
  `visual_ssim` check excluded.

Local reports are intentionally ineligible for an official leaderboard. They do
not assert that a hosted service verified the score or that any model generated
the artifact.
