<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:158b1f1412de235a48f184256483a630d9baba154b5e493306f46e8888bedbb2",
    "paraphrase-a": "sha256:cdcd5d715ecb6bea2c2e3c55ad5a89df900c7d7374e7263e12a98f12fa1d65f8",
    "paraphrase-b": "sha256:23bd62703614a6e0caa7e9a7a085779b6cf25865512a014952677b0224f8a26d"
  },
  "record_id": "acidslide-prompt-validation-slide-18",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 18,
  "status": "pending"
}
-->
# Slide 18 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `158b1f1412de235a48f184256483a630d9baba154b5e493306f46e8888bedbb2`
- Paraphrase A SHA-256: `cdcd5d715ecb6bea2c2e3c55ad5a89df900c7d7374e7263e12a98f12fa1d65f8`
- Paraphrase B SHA-256: `23bd62703614a6e0caa7e9a7a085779b6cf25865512a014952677b0224f8a26d`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
