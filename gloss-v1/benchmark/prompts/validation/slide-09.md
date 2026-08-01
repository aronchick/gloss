<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:cc1018986b55a19e65571bd98c655ec5ef17fecc67b5fdbb603b166ceea4105a",
    "paraphrase-a": "sha256:4e3bc89c034c3e30d369d77f26f5ab59d5a28c824fd85400d3b41d09158a5acd",
    "paraphrase-b": "sha256:fbe4c623ab0c71c16a3fb7072394b36d2bd8b1e47fcee91a42cee0cb2d07e83e"
  },
  "record_id": "gloss-prompt-validation-slide-09",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 9,
  "status": "pending"
}
-->
# Slide 09 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `cc1018986b55a19e65571bd98c655ec5ef17fecc67b5fdbb603b166ceea4105a`
- Paraphrase A SHA-256: `4e3bc89c034c3e30d369d77f26f5ab59d5a28c824fd85400d3b41d09158a5acd`
- Paraphrase B SHA-256: `fbe4c623ab0c71c16a3fb7072394b36d2bd8b1e47fcee91a42cee0cb2d07e83e`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
