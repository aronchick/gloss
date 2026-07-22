<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:1ca475aa23be5d7d3b0f8d03fc17e2b78c1886cc5a532d57aebc3f98ed71e2c2",
    "paraphrase-a": "sha256:c1b661d7de888e80b1468c0638bac17e9200c57dbffe7f3f1b85bbd9862dfe3b",
    "paraphrase-b": "sha256:c4ce2b8794ebe8d91c1cdd3fafd46aafe0347e347f3752ef194ec6898252919b"
  },
  "record_id": "acidslide-prompt-validation-slide-16",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 16,
  "status": "pending"
}
-->
# Slide 16 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `1ca475aa23be5d7d3b0f8d03fc17e2b78c1886cc5a532d57aebc3f98ed71e2c2`
- Paraphrase A SHA-256: `c1b661d7de888e80b1468c0638bac17e9200c57dbffe7f3f1b85bbd9862dfe3b`
- Paraphrase B SHA-256: `c4ce2b8794ebe8d91c1cdd3fafd46aafe0347e347f3752ef194ec6898252919b`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
