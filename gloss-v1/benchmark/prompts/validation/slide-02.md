<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:398939d56c99f44b33907b01a8075ef535005a419bc7d04e0fb84326e381c5fb",
    "paraphrase-a": "sha256:78154bc2925a7381973eba99e5958409b222bd9873664f57e458b02f5e83588e",
    "paraphrase-b": "sha256:4b801c10fa0f9bec4fb71aa7d9c33fa05b02baee6eee56e80dcf998ad4a97636"
  },
  "record_id": "gloss-prompt-validation-slide-02",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 2,
  "status": "pending"
}
-->
# Slide 02 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `398939d56c99f44b33907b01a8075ef535005a419bc7d04e0fb84326e381c5fb`
- Paraphrase A SHA-256: `78154bc2925a7381973eba99e5958409b222bd9873664f57e458b02f5e83588e`
- Paraphrase B SHA-256: `4b801c10fa0f9bec4fb71aa7d9c33fa05b02baee6eee56e80dcf998ad4a97636`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
