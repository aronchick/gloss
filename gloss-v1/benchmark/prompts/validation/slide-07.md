<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:8f9c8900a4728681c32e82beea6ea51856f3d4ec63bdf2d9c4ffb203850693e9",
    "paraphrase-a": "sha256:35af578801b5b4a3e76715b0ad7654e8025454658bf68e7bfbfe0fd0c607d7cf",
    "paraphrase-b": "sha256:66bb25b6d1ffcac8f80547b0d041bed5604018676adbe8084567faaa4213d80a"
  },
  "record_id": "gloss-prompt-validation-slide-07",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 7,
  "status": "pending"
}
-->
# Slide 07 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `8f9c8900a4728681c32e82beea6ea51856f3d4ec63bdf2d9c4ffb203850693e9`
- Paraphrase A SHA-256: `35af578801b5b4a3e76715b0ad7654e8025454658bf68e7bfbfe0fd0c607d7cf`
- Paraphrase B SHA-256: `66bb25b6d1ffcac8f80547b0d041bed5604018676adbe8084567faaa4213d80a`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
