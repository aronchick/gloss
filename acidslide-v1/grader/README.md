# AcidSlide Grader

The AcidSlide CLI performs quarantine checks, deterministic ECMA-376 Markup Compatibility preprocessing, Part 1 Transitional XSD validation, LibreOffice export, SSIM comparison, native object inspection, checklist evaluation, and report generation.

The wheel contains the benchmark corpus and schemas. Source and Docker layouts are also discovered automatically; `--benchmark-dir` or `ACIDSLIDE_BENCHMARK_DIR` can select an explicit corpus.

```bash
uv sync --extra dev --locked
uv run acidslide validate ../benchmark/deck/gold/acidslide-v1-gold.pptx
uv run acidslide grade ../submission.pptx --tier 3 \
  --artifact-context ./local-artifact-context.json --format json
uv run acidslide grade ../submission.pptx --tier 3 \
  --artifact-context ./local-artifact-context.json --format html -o report.html
```

Output formats are `text`, `json`, and standalone `html`. Use `--artifacts DIR` to retain `diff-slide-NN.png` visual diagnostics. Incomplete verification exits with status `2` and is always reported as `eligible: false`.

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
export ACIDSLIDE_TRUSTED_GENESIS_SHA256='sha256:<published-genesis-index-hash>'
export ACIDSLIDE_RELEASE_STATE_PATH='/var/lib/acidslide/release-head-v1.json'
export ACIDSLIDE_GRADER_SOURCE_PATH='/opt/acidslide/grader-source-tree.tar'
```

The verifier checks every index signature, sequence, predecessor hash, cohort binding, and effective
time from genesis through the packaged head, then atomically persists the highest accepted head
before returning it. A lower sequence, same-sequence alternate, fork, gap, premature head, or chain
whose final entry differs from `release-index.json` fails closed. Sequence-1 packages remain
supported; production deployments should still pin their published genesis explicitly.

Before accepting that head, the verifier also reconstructs the complete grader source inventory from
the repository `grader/` directory, packaged `benchmark/grader-source-tree.tar`, or the explicit
`ACIDSLIDE_GRADER_SOURCE_PATH`. It requires exact file membership, byte length, SHA-256, and execute
bits to match the canonical `grader-source-tree-manifest.json` and all signed scoring-manifest/cohort
bindings. Links, special files, path collisions, extras, omissions, and archive traversal fail closed.

See `ACIDSLIDE_OPENSPEC.md` in the repository root for the normative contract.
