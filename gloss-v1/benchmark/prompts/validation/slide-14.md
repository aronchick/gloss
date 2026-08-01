<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:539c484fcf6c333a2d94ac808415702f1161d394f290b9b18dafff4a6b5616e5",
    "paraphrase-a": "sha256:9caea8e79d614565d25375b5ccb2533ff61dc4612f9e2ced9ab025b6b879f111",
    "paraphrase-b": "sha256:7c1052c58bae44fe3453344d622d47565b37f1e7aed29ef7c02c1954f3dc8f1c"
  },
  "record_id": "gloss-prompt-validation-slide-14",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 14,
  "status": "pending"
}
-->
# Slide 14 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `539c484fcf6c333a2d94ac808415702f1161d394f290b9b18dafff4a6b5616e5`
- Paraphrase A SHA-256: `9caea8e79d614565d25375b5ccb2533ff61dc4612f9e2ced9ab025b6b879f111`
- Paraphrase B SHA-256: `7c1052c58bae44fe3453344d622d47565b37f1e7aed29ef7c02c1954f3dc8f1c`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
