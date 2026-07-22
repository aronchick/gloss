<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:5eefdbce232c0e666065c907020c0ea650014444ed431c67be8cde436b10ad50",
    "paraphrase-a": "sha256:89987a71046da3d440aa6e096b0125478a4ccbac36c0e56d2f9b07ac2396a78d",
    "paraphrase-b": "sha256:402c1979168b71c643ab180d7c6357a112f191ff5d2b37fca80ee45b8971d0cd"
  },
  "record_id": "acidslide-prompt-validation-slide-20",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 20,
  "status": "pending"
}
-->
# Slide 20 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `5eefdbce232c0e666065c907020c0ea650014444ed431c67be8cde436b10ad50`
- Paraphrase A SHA-256: `89987a71046da3d440aa6e096b0125478a4ccbac36c0e56d2f9b07ac2396a78d`
- Paraphrase B SHA-256: `402c1979168b71c643ab180d7c6357a112f191ff5d2b37fca80ee45b8971d0cd`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
