<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:51b388342d0563450e15aad40ae0a584625ebdb159416146d4d9c1d1722898ee",
    "paraphrase-a": "sha256:89c290deea5eafe5a6de472eb2b284a0768838744f33281dc17d77f40a9c1462",
    "paraphrase-b": "sha256:3e149ffa5ba801474a59aebbeef7d87803a17391f1b5e1e1b36c0423de3738c9"
  },
  "record_id": "acidslide-prompt-validation-slide-19",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 19,
  "status": "pending"
}
-->
# Slide 19 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `51b388342d0563450e15aad40ae0a584625ebdb159416146d4d9c1d1722898ee`
- Paraphrase A SHA-256: `89c290deea5eafe5a6de472eb2b284a0768838744f33281dc17d77f40a9c1462`
- Paraphrase B SHA-256: `3e149ffa5ba801474a59aebbeef7d87803a17391f1b5e1e1b36c0423de3738c9`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
