<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:3a466f16ec13919f6009bb9c938b96b7b18b4950127856d38669e4a9584f5d95",
    "paraphrase-a": "sha256:e32d92ba37bcfc1c59820f983b5638272815be17133566981d4734b03c2dd9dc",
    "paraphrase-b": "sha256:a36ae71f60bca2fc0189fb4a2f4f4e6c80b147402dfbb10252899ae51e573e78"
  },
  "record_id": "gloss-prompt-validation-slide-18",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 18,
  "status": "pending"
}
-->
# Slide 18 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `3a466f16ec13919f6009bb9c938b96b7b18b4950127856d38669e4a9584f5d95`
- Paraphrase A SHA-256: `e32d92ba37bcfc1c59820f983b5638272815be17133566981d4734b03c2dd9dc`
- Paraphrase B SHA-256: `a36ae71f60bca2fc0189fb4a2f4f4e6c80b147402dfbb10252899ae51e573e78`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
