<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:e9e56ffdd74f021765cd9a933503fda3103fc5e91d4cff56259d39463654b631",
    "paraphrase-a": "sha256:7b0854475062ae55fffa19786de5a6bb5045a56d6889e1d4f169577849385b1f",
    "paraphrase-b": "sha256:0f3a275cb5359c2aa184bd9763dd86e5d8af96f4aa48171f3d5e9bb456ffb1c3"
  },
  "record_id": "acidslide-prompt-validation-slide-13",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 13,
  "status": "pending"
}
-->
# Slide 13 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `e9e56ffdd74f021765cd9a933503fda3103fc5e91d4cff56259d39463654b631`
- Paraphrase A SHA-256: `7b0854475062ae55fffa19786de5a6bb5045a56d6889e1d4f169577849385b1f`
- Paraphrase B SHA-256: `0f3a275cb5359c2aa184bd9763dd86e5d8af96f4aa48171f3d5e9bb456ffb1c3`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
