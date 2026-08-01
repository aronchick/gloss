<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:ba8e51e1becddfd40e2f2a02c5161a1caa09481255fcb9ff586f6b32ff866245",
    "paraphrase-a": "sha256:c00f3398a053de3f9ac2b9a34697a8cb4eebefaf90ee1e73bc878ba24cd58081",
    "paraphrase-b": "sha256:e37739606bb0dd690de9ac19cd76c51d2a95f3310d46c2c4e1c4b18d00474ac4"
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
- Canonical SHA-256: `ba8e51e1becddfd40e2f2a02c5161a1caa09481255fcb9ff586f6b32ff866245`
- Paraphrase A SHA-256: `c00f3398a053de3f9ac2b9a34697a8cb4eebefaf90ee1e73bc878ba24cd58081`
- Paraphrase B SHA-256: `e37739606bb0dd690de9ac19cd76c51d2a95f3310d46c2c4e1c4b18d00474ac4`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
