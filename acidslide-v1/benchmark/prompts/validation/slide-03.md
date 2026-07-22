<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:86ffb3b47398d048539e659e88a0c1074152a51f212aec16acebdc3b6db755c5",
    "paraphrase-a": "sha256:cfa6e7d59aeb1822335d49595aaa1ef1b578ee57acc21a3ae189a89ebc92bdf3",
    "paraphrase-b": "sha256:2c79103ad8a03c15347de27c56e1b003e0da8c4d9a4f56254dd52d01d729b054"
  },
  "record_id": "acidslide-prompt-validation-slide-03",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 3,
  "status": "pending"
}
-->
# Slide 03 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `86ffb3b47398d048539e659e88a0c1074152a51f212aec16acebdc3b6db755c5`
- Paraphrase A SHA-256: `cfa6e7d59aeb1822335d49595aaa1ef1b578ee57acc21a3ae189a89ebc92bdf3`
- Paraphrase B SHA-256: `2c79103ad8a03c15347de27c56e1b003e0da8c4d9a4f56254dd52d01d729b054`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
