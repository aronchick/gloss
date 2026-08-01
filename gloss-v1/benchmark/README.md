# Gloss v1 Benchmark Corpus

This directory contains the public, non-gold benchmark inputs: tier maps,
prompt variants, allowed assets, bundled fonts, and the weighted checklist.
Prompt-derived structural requirements are frozen before gold authoring.
Reference exports later become authoritative only for explicitly provenance-
linked visual assertions; gold OOXML never creates a scored requirement.

Start with [`prompts/DESIGNER_BRIEF.md`](prompts/DESIGNER_BRIEF.md): it is the
exact, copyable master prompt containing the deck-wide rules and all twenty slide instructions. Provide
it with the reference PNGs in `deck/exports/`, the approved assets, and the bundled
fonts. Do not provide the native gold deck to the system being tested.

## Integrity validation

From `gloss-v1/grader/` using the locked grader environment:

```bash
uv run python ../benchmark/validate_corpus.py
```

This validates prompt-set completeness and hard-constraint parity, checklist
schema/count/ID/severity/source balance, asset dimensions and hashes, and every
bundled font and license record. It does not claim independent-author prompt
convergence. To apply that release gate too:

```bash
uv run python ../benchmark/validate_corpus.py --release
```

Release mode is expected to fail until each file under `prompts/validation/`
records a completed independent-author convergence run. V1 accepts only the
primary asset bytes already pinned in the asset manifest; it does not add
gold-derived recompression hashes.

## Generated operator mutation fixtures

From `gloss-v1/grader/`, rebuild and execute the candidate fixture matrix:

```bash
uv run python ../benchmark/tools/build_mutation_fixtures.py
uv run python ../benchmark/tools/build_mutation_fixtures.py --check
```

The generated index, single-fault expectations, and execution report live in
`fixtures/mutations/`. They prove only that each configured automatic operator
can pass a positive input and detect its generated one-property mutation. They
are not independent prompt/reference/asset evidence, do not complete checklist
evidence or provenance, and do not freeze or approve any candidate assertion.

## Deterministic rebuild

`tools/build_corpus.py` regenerates prompt variants, validation records,
manifests, and checklist YAML from the authoritative authoring brief and local
files. It does not create or modify the gold deck, exports, fixtures, baselines,
or hosted-service data.
