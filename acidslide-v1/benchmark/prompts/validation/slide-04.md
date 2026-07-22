<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:1cc1a7b72a0780e13a564111e6e1a30e53e818fdd7d53675f3d20a84fbe03b1f",
    "paraphrase-a": "sha256:a6c7257409407e1b45a96c4e4c2cffeea6d76e504fdfd1fcebe7bef568df432e",
    "paraphrase-b": "sha256:c54515c9433ad0ae980433c9834d0061cf322dd36c471e0917e512f0df796205"
  },
  "record_id": "acidslide-prompt-validation-slide-04",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 4,
  "status": "pending"
}
-->
# Slide 04 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `1cc1a7b72a0780e13a564111e6e1a30e53e818fdd7d53675f3d20a84fbe03b1f`
- Paraphrase A SHA-256: `a6c7257409407e1b45a96c4e4c2cffeea6d76e504fdfd1fcebe7bef568df432e`
- Paraphrase B SHA-256: `c54515c9433ad0ae980433c9834d0061cf322dd36c471e0917e512f0df796205`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
