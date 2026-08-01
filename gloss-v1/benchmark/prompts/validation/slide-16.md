<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:55ca0d63d13be5ca86db79eaafb04e56ccc82994a4018dc2b1bf250ab44d5f4c",
    "paraphrase-a": "sha256:66b91d460391074a63c6dc3cde2bea03b0cb94f7ab23a669eabcfc537f5ef96b",
    "paraphrase-b": "sha256:3fd3179603711c86e774a274efa7d5920a90922612399cf8e8e63ab1294d0990"
  },
  "record_id": "gloss-prompt-validation-slide-16",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 16,
  "status": "pending"
}
-->
# Slide 16 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `55ca0d63d13be5ca86db79eaafb04e56ccc82994a4018dc2b1bf250ab44d5f4c`
- Paraphrase A SHA-256: `66b91d460391074a63c6dc3cde2bea03b0cb94f7ab23a669eabcfc537f5ef96b`
- Paraphrase B SHA-256: `3fd3179603711c86e774a274efa7d5920a90922612399cf8e8e63ab1294d0990`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
