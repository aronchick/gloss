<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:1b6d34909a8dd6ef996e67a0f683692e67b507bfa21e9099ab9486ed64e6651e",
    "paraphrase-a": "sha256:49d4de1acb350a4f5c2f767ff6fe2b2644d2abecc45298fe729ae26b9daf0e53",
    "paraphrase-b": "sha256:8a5c892bf119932f222bd35ee2e1a8b903cbd4f7b56fa8d6a5b867c0601f174d"
  },
  "record_id": "acidslide-prompt-validation-slide-02",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 2,
  "status": "pending"
}
-->
# Slide 02 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `1b6d34909a8dd6ef996e67a0f683692e67b507bfa21e9099ab9486ed64e6651e`
- Paraphrase A SHA-256: `49d4de1acb350a4f5c2f767ff6fe2b2644d2abecc45298fe729ae26b9daf0e53`
- Paraphrase B SHA-256: `8a5c892bf119932f222bd35ee2e1a8b903cbd4f7b56fa8d6a5b867c0601f174d`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
