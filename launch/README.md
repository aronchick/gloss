# Gloss launch assets

The launch page and film are static, repository-owned, and derived from committed evidence.

## Evidence

`site/evidence/preview-v1.json` records candidate-harness counts.
`acidslide-v1/benchmark/comparative-v1/summary.json` records the frozen
generation-path scores used by the central chart and film. Its public copy at
`site/evidence/comparative-v1-summary.json` must remain semantically identical.

Verify the evidence, local links, caveats, and media metadata:

```bash
node launch/verify-launch.mjs
```

## Film

Rebuild the silent 1080×1080, 30 fps, 21-second MP4 and poster:

```bash
node launch/render-video.mjs
```

The renderer uses Node.js standard libraries, `rsvg-convert`, and `ffmpeg`. It creates temporary frames in the operating system temporary directory and removes them after encoding.

The film deliberately reports deterministic repository-owned workflow
baselines. It does not show model rankings because no verified model-result
cohort exists yet.
