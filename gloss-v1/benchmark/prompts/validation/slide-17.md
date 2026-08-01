<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:d70b572f05883784463f07e5a7d6fcdba76b222f8ce0f8b102df2eea6f2cd659",
    "paraphrase-a": "sha256:4343198e7ec173c9141864a9c076dd82b7e04ebefc9a12a219a5d25786000420",
    "paraphrase-b": "sha256:0e10d5bbb3d1ae9e71a01d121b5b892671b6419c753a8c9a24bc93e764d0ec65"
  },
  "record_id": "gloss-prompt-validation-slide-17",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 17,
  "status": "pending"
}
-->
# Slide 17 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `d70b572f05883784463f07e5a7d6fcdba76b222f8ce0f8b102df2eea6f2cd659`
- Paraphrase A SHA-256: `4343198e7ec173c9141864a9c076dd82b7e04ebefc9a12a219a5d25786000420`
- Paraphrase B SHA-256: `0e10d5bbb3d1ae9e71a01d121b5b892671b6419c753a8c9a24bc93e764d0ec65`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
