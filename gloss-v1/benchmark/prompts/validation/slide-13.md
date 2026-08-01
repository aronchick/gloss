<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:10a757d7989017806ebeb0c38c420982354a889e47af266e048c37c9fb20399d",
    "paraphrase-a": "sha256:65a41f8cb4a48fbf437df1c8ba779e898ecc2fcac6365b356de9f269b63ef80f",
    "paraphrase-b": "sha256:0b816533f1d9ca8a0b37f69b4e4956f4d8a9b28a6aa9120962bd3543f79fb989"
  },
  "record_id": "gloss-prompt-validation-slide-13",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 13,
  "status": "pending"
}
-->
# Slide 13 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `10a757d7989017806ebeb0c38c420982354a889e47af266e048c37c9fb20399d`
- Paraphrase A SHA-256: `65a41f8cb4a48fbf437df1c8ba779e898ecc2fcac6365b356de9f269b63ef80f`
- Paraphrase B SHA-256: `0b816533f1d9ca8a0b37f69b4e4956f4d8a9b28a6aa9120962bd3543f79fb989`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
