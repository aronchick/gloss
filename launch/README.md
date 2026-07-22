# Gloss launch assets

The launch page and film are static, repository-owned, and derived from committed evidence.

## Evidence

`site/evidence/preview-v1.json` is the single launch evidence bundle. It records the exact generated mutation reports and SHA-256 hashes used for every homepage and film count.

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

The film deliberately reports harness composition and mutation-operator evidence. It does not show model rankings because no verified model-result cohort exists yet.
