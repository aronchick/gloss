<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:46bb8770a220a60a0bb4b9a8a1262463ef635b06680fe4c507b87d7e1ab3631f",
    "paraphrase-a": "sha256:2b16e02e855649da83cff3521ffc465672cd10871fcc03d43400946b3a8934dc",
    "paraphrase-b": "sha256:66c857fd4c81366f25ac3f88d50755b48fe17a428b3c1a6d851091431b5dc3ac"
  },
  "record_id": "gloss-prompt-validation-slide-15",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 15,
  "status": "pending"
}
-->
# Slide 15 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `46bb8770a220a60a0bb4b9a8a1262463ef635b06680fe4c507b87d7e1ab3631f`
- Paraphrase A SHA-256: `2b16e02e855649da83cff3521ffc465672cd10871fcc03d43400946b3a8934dc`
- Paraphrase B SHA-256: `66c857fd4c81366f25ac3f88d50755b48fe17a428b3c1a6d851091431b5dc3ac`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
