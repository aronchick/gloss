<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:fd9ca84995214fab8981ee570120b943184312c1a4d217a011d1e2966b425193",
    "paraphrase-a": "sha256:dc98ef41cd217fe83b82e9083d7a5da94aa58600f4cb81828b98e30cbe8a3d0d",
    "paraphrase-b": "sha256:69723c2a7ac42754147b2ffbebb2b2f20e456d9bd0f2b219ba1ddca309fb6f64"
  },
  "record_id": "gloss-prompt-validation-slide-16",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 16,
  "status": "pending"
}
-->
# Slide 16 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `fd9ca84995214fab8981ee570120b943184312c1a4d217a011d1e2966b425193`
- Paraphrase A SHA-256: `dc98ef41cd217fe83b82e9083d7a5da94aa58600f4cb81828b98e30cbe8a3d0d`
- Paraphrase B SHA-256: `69723c2a7ac42754147b2ffbebb2b2f20e456d9bd0f2b219ba1ddca309fb6f64`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
