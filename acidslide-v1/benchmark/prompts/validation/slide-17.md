<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:80ad70a1f59d10f8d6f6b4b1c69c1c2b3abd84100891994b0332480cabc829c9",
    "paraphrase-a": "sha256:4176bc52f51ef82dc5af787394d5c992f344a251b45d74b18317537ab64c3a54",
    "paraphrase-b": "sha256:32767b82411995b57e745fe2dd3731ac4adfad16b941b7a017db85a0eaaf0bd9"
  },
  "record_id": "acidslide-prompt-validation-slide-17",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 17,
  "status": "pending"
}
-->
# Slide 17 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `80ad70a1f59d10f8d6f6b4b1c69c1c2b3abd84100891994b0332480cabc829c9`
- Paraphrase A SHA-256: `4176bc52f51ef82dc5af787394d5c992f344a251b45d74b18317537ab64c3a54`
- Paraphrase B SHA-256: `32767b82411995b57e745fe2dd3731ac4adfad16b941b7a017db85a0eaaf0bd9`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
