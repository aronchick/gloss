<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:69711e77502102776aae817c7417faad5d3ae0ea8e29c823554cbc27c5b989d9",
    "paraphrase-a": "sha256:86adb541d0961cefeb3d1388cdc4d6fea1f989d1485bb6dafbc5043d177204a7",
    "paraphrase-b": "sha256:943121b317a29b1be5cf83776833d3c0c8e25aef6176f3d1bdefd3e8d4e72e05"
  },
  "record_id": "gloss-prompt-validation-slide-20",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 20,
  "status": "pending"
}
-->
# Slide 20 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `69711e77502102776aae817c7417faad5d3ae0ea8e29c823554cbc27c5b989d9`
- Paraphrase A SHA-256: `86adb541d0961cefeb3d1388cdc4d6fea1f989d1485bb6dafbc5043d177204a7`
- Paraphrase B SHA-256: `943121b317a29b1be5cf83776833d3c0c8e25aef6176f3d1bdefd3e8d4e72e05`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
