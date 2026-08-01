# Gloss launch surface

The launch page is static, repository-owned, and centered on the public 20-slide
challenge deck. Every slide image links to its exact instructions, and the primary
calls to action download the native deck, open the single master prompt, or join
the GitHub project.

## Evidence

`site/evidence/preview-v1.json` records candidate-harness counts for the
supporting measurement layer. The launch film is presentation-first: it uses
real Gloss v1 slide renders, the two-object checker example, the ACID lineage,
and the GitHub call to action. It does not lead with comparative scores.

Verify the deck, all twenty renders and prompt links, supporting evidence, local
assets, claims, and media metadata:

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
