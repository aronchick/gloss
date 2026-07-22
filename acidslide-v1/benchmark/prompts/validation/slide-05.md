<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:8f9a7d82cfd6c687f55f14cd1addf8f2d2c00662aac21a499aa34b95ff12750c",
    "paraphrase-a": "sha256:2f8471d11d5c69e96cbec77703b66882d5cdba5c865a853ac55562a1eea6fc3c",
    "paraphrase-b": "sha256:a86474279d615df43241b1c3908a85ab5e6468d5b16cc5af99d41b0ca587db51"
  },
  "record_id": "acidslide-prompt-validation-slide-05",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 5,
  "status": "pending"
}
-->
# Slide 05 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `8f9a7d82cfd6c687f55f14cd1addf8f2d2c00662aac21a499aa34b95ff12750c`
- Paraphrase A SHA-256: `2f8471d11d5c69e96cbec77703b66882d5cdba5c865a853ac55562a1eea6fc3c`
- Paraphrase B SHA-256: `a86474279d615df43241b1c3908a85ab5e6468d5b16cc5af99d41b0ca587db51`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
