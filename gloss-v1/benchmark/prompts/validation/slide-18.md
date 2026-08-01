<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:5f55790f0cc830703216a5031ea6cc5040efbbb45b9207c7e83ed67f620edf60",
    "paraphrase-a": "sha256:8964ca72cae3e9e3b44c2f17873bca9b548b4240fe1747ed2a040ffba5f3d4e7",
    "paraphrase-b": "sha256:0b228fc57017d0de56a93620e797f891ddbd722812cc07203b36b5c68517246e"
  },
  "record_id": "gloss-prompt-validation-slide-18",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 18,
  "status": "pending"
}
-->
# Slide 18 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `5f55790f0cc830703216a5031ea6cc5040efbbb45b9207c7e83ed67f620edf60`
- Paraphrase A SHA-256: `8964ca72cae3e9e3b44c2f17873bca9b548b4240fe1747ed2a040ffba5f3d4e7`
- Paraphrase B SHA-256: `0b228fc57017d0de56a93620e797f891ddbd722812cc07203b36b5c68517246e`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
