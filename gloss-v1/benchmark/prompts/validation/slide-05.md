<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:183dd1123fb9642d86d6d51ae66920da318a07ac87b08ca68ebbf095e7d091e1",
    "paraphrase-a": "sha256:997a63080d96f6d20b66eb6a062c3a7613d13221fdbb7310e6ef46bd68aac0a6",
    "paraphrase-b": "sha256:fa1cc0f38276963ddd14b0b71a8c2a1836e2e0a93a29a3c444c495a062e5305e"
  },
  "record_id": "gloss-prompt-validation-slide-05",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 5,
  "status": "pending"
}
-->
# Slide 05 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `183dd1123fb9642d86d6d51ae66920da318a07ac87b08ca68ebbf095e7d091e1`
- Paraphrase A SHA-256: `997a63080d96f6d20b66eb6a062c3a7613d13221fdbb7310e6ef46bd68aac0a6`
- Paraphrase B SHA-256: `fa1cc0f38276963ddd14b0b71a8c2a1836e2e0a93a29a3c444c495a062e5305e`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
