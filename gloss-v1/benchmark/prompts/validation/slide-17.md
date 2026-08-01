<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:4616dafa273ff38e505a39387f0fa32618e549593d6209e5a8d6571c4a30f63e",
    "paraphrase-a": "sha256:bac6c6544f907f53ec1a678cf3272a7969ea5c831684d2ab17f7e1d693a5b506",
    "paraphrase-b": "sha256:c06f26f233b0eafc00a2f6e56d12fcfae64686705d6f696e249f3c5d468b475a"
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
- Canonical SHA-256: `4616dafa273ff38e505a39387f0fa32618e549593d6209e5a8d6571c4a30f63e`
- Paraphrase A SHA-256: `bac6c6544f907f53ec1a678cf3272a7969ea5c831684d2ab17f7e1d693a5b506`
- Paraphrase B SHA-256: `c06f26f233b0eafc00a2f6e56d12fcfae64686705d6f696e249f3c5d468b475a`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
