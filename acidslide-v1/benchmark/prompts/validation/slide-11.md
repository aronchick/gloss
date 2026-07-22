<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:d2d0f303ddd4a8923cdf6988918505b37fbecb8d7f4e96cfbc29940010d36b89",
    "paraphrase-a": "sha256:a27edb91242b06f49cae2446ee1783538aff62a039ed8a9bf3f6e4ac2f0bda77",
    "paraphrase-b": "sha256:d2b337f3c595acd9b99dcd8946a3b6246617e1381462d5a1d1ddde84f298e3b4"
  },
  "record_id": "acidslide-prompt-validation-slide-11",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 11,
  "status": "pending"
}
-->
# Slide 11 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `d2d0f303ddd4a8923cdf6988918505b37fbecb8d7f4e96cfbc29940010d36b89`
- Paraphrase A SHA-256: `a27edb91242b06f49cae2446ee1783538aff62a039ed8a9bf3f6e4ac2f0bda77`
- Paraphrase B SHA-256: `d2b337f3c595acd9b99dcd8946a3b6246617e1381462d5a1d1ddde84f298e3b4`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
