<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:94506f9d83d614409de9a11206400cac10d6a584a167b2d80a17eabe570de158",
    "paraphrase-a": "sha256:0bae34b314b72591e6f4531c9e1a40e2baf5e660beb8277daa188dbd7bb6df3d",
    "paraphrase-b": "sha256:dcd0f32ae1b1a60cc53c9e8d91678f97e1c1f6d852f776e8a6ec9df4c4544d01"
  },
  "record_id": "gloss-prompt-validation-slide-06",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 6,
  "status": "pending"
}
-->
# Slide 06 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `94506f9d83d614409de9a11206400cac10d6a584a167b2d80a17eabe570de158`
- Paraphrase A SHA-256: `0bae34b314b72591e6f4531c9e1a40e2baf5e660beb8277daa188dbd7bb6df3d`
- Paraphrase B SHA-256: `dcd0f32ae1b1a60cc53c9e8d91678f97e1c1f6d852f776e8a6ec9df4c4544d01`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
