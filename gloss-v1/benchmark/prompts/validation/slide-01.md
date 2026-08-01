<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:3c0f4ea5275558de541aa8cd75111b29fc4736e72b15bd45695e68c28d84510f",
    "paraphrase-a": "sha256:fff8e3cfc9f66a952cc5ea90cb264e8389d93eda34ba4d92342be5a84c987fc9",
    "paraphrase-b": "sha256:496225024c0e08cf9d6de53a73a279d4518de75dcd2b305f73c2f5a43a452734"
  },
  "record_id": "gloss-prompt-validation-slide-01",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 1,
  "status": "pending"
}
-->
# Slide 01 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `3c0f4ea5275558de541aa8cd75111b29fc4736e72b15bd45695e68c28d84510f`
- Paraphrase A SHA-256: `fff8e3cfc9f66a952cc5ea90cb264e8389d93eda34ba4d92342be5a84c987fc9`
- Paraphrase B SHA-256: `496225024c0e08cf9d6de53a73a279d4518de75dcd2b305f73c2f5a43a452734`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
