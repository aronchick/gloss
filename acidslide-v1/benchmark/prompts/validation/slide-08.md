<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:f9e89d1564b307475a5eac1bf51b502838f4894dee14f1238c6463326f3df4a7",
    "paraphrase-a": "sha256:0707bf6e52ff4d18ec84857517c0d9d69c2afa4b1b42c567828fb2127b77bceb",
    "paraphrase-b": "sha256:d929df4103244a6fdd9b47d3813dd1986df1e5ad34b21f5eed0cf6beee046018"
  },
  "record_id": "acidslide-prompt-validation-slide-08",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 8,
  "status": "pending"
}
-->
# Slide 08 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `f9e89d1564b307475a5eac1bf51b502838f4894dee14f1238c6463326f3df4a7`
- Paraphrase A SHA-256: `0707bf6e52ff4d18ec84857517c0d9d69c2afa4b1b42c567828fb2127b77bceb`
- Paraphrase B SHA-256: `d929df4103244a6fdd9b47d3813dd1986df1e5ad34b21f5eed0cf6beee046018`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
