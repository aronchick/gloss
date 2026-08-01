# Gloss Checker

The friendly front door is a native-object check against the public Gloss deck:

```bash
uv sync --extra dev --locked
uv run gloss check ../benchmark/deck/gold/gloss-v1-gold.pptx
uv run gloss check /path/to/edited.pptx
```

An untouched deck returns zero findings. Change the position, size, text, type,
rotation, field, chart, table, image, fill, shadow, group, or z-order of one native
object and `gloss check` returns one aggregated finding for that object. Use
`--format json` for machine-readable output or `--reference other.pptx` to compare
against another deck.

The same CLI also contains the deeper Gloss v1 grading protocol: quarantine checks,
deterministic ECMA-376 Markup Compatibility preprocessing, Part 1 Transitional XSD
validation, LibreOffice export, SSIM comparison, native inspection, checklist
evaluation, and release-grade reports.

The wheel contains the benchmark corpus and schemas. Source and Docker layouts are also discovered automatically; `--benchmark-dir` or `GLOSS_BENCHMARK_DIR` can select an explicit corpus.

```bash
uv run gloss validate ../benchmark/deck/gold/gloss-v1-gold.pptx
uv run gloss grade ../submission.pptx --tier 3 \
  --artifact-context ./local-artifact-context.json --format json
uv run gloss grade ../submission.pptx --tier 3 \
  --artifact-context ./local-artifact-context.json --format html -o report.html
```

Advanced `grade` output formats are `text`, `json`, and standalone `html`. Use
`--artifacts DIR` to retain `diff-slide-NN.png` visual diagnostics. Incomplete
verification exits with status `2` and is always reported as `eligible: false`.

`--artifact-context` is required and must name a complete JSON serialization of
`ArtifactReportContext`, including explicit `null` values. Missing or unknown fields are rejected. The
CLI never invents release, artifact, gold, profile, generation, or environment identities; it verifies
the supplied artifact hashes and the RFC 8785 environment-attestation hash against the signed scoring
cohort before grading.

Local scores are self-reported. Only the controlled hosted service may label a grading result grading-verified; generation metadata remains generation-attested.

Frozen releases above sequence 1 include canonical `benchmark/release-index-chain.json`. Configure
the independently published genesis checkpoint and a durable, non-cache acceptance-state path before
grading:

```bash
export GLOSS_TRUSTED_GENESIS_SHA256='sha256:<published-genesis-index-hash>'
export GLOSS_RELEASE_STATE_PATH='/var/lib/gloss/release-head-v1.json'
export GLOSS_GRADER_SOURCE_PATH='/opt/gloss/grader-source-tree.tar'
```

The verifier checks every index signature, sequence, predecessor hash, cohort binding, and effective
time from genesis through the packaged head, then atomically persists the highest accepted head
before returning it. A lower sequence, same-sequence alternate, fork, gap, premature head, or chain
whose final entry differs from `release-index.json` fails closed. Sequence-1 packages remain
supported; production deployments should still pin their published genesis explicitly.

Before accepting that head, the verifier also reconstructs the complete grader source inventory from
the repository `grader/` directory, packaged `benchmark/grader-source-tree.tar`, or the explicit
`GLOSS_GRADER_SOURCE_PATH`. It requires exact file membership, byte length, SHA-256, and execute
bits to match the canonical `grader-source-tree-manifest.json` and all signed scoring-manifest/cohort
bindings. Links, special files, path collisions, extras, omissions, and archive traversal fail closed.

See `GLOSS_OPENSPEC.md` in the repository root for the normative contract.
