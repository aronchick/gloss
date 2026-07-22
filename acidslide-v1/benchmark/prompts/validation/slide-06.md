<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:a1d035b57f759fe162ee1707ddf316b886a24f217f5677b878973198e0127592",
    "paraphrase-a": "sha256:bff711a0a508c5a64c399ee06d61317302fdc4a682f99034d77df377926d3bf9",
    "paraphrase-b": "sha256:b72d32e1fe636cd80a7fd03255887a33a445b1a38e64f8f73cd7cda8036b7018"
  },
  "record_id": "acidslide-prompt-validation-slide-06",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 6,
  "status": "pending"
}
-->
# Slide 06 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `a1d035b57f759fe162ee1707ddf316b886a24f217f5677b878973198e0127592`
- Paraphrase A SHA-256: `bff711a0a508c5a64c399ee06d61317302fdc4a682f99034d77df377926d3bf9`
- Paraphrase B SHA-256: `b72d32e1fe636cd80a7fd03255887a33a445b1a38e64f8f73cd7cda8036b7018`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
