<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:c43ff38821bdfa4e2f5cae337cd25f55099529eaeeb8eefe8a3fd2bffb771728",
    "paraphrase-a": "sha256:31dfd3b632acc2607437ff382621e2e507b56b763682a43d1d5f754ebcbc426e",
    "paraphrase-b": "sha256:fb47db9262f1dc3f481527b83c61473729936fd181c47f9c18142f67cc42bfa8"
  },
  "record_id": "acidslide-prompt-validation-slide-12",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 12,
  "status": "pending"
}
-->
# Slide 12 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `c43ff38821bdfa4e2f5cae337cd25f55099529eaeeb8eefe8a3fd2bffb771728`
- Paraphrase A SHA-256: `31dfd3b632acc2607437ff382621e2e507b56b763682a43d1d5f754ebcbc426e`
- Paraphrase B SHA-256: `fb47db9262f1dc3f481527b83c61473729936fd181c47f9c18142f67cc42bfa8`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
