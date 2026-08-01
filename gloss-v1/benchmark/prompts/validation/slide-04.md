<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:cd652469a57e74d3b9778fe7df68da1f605a12124885379bb58eea5504ed44d7",
    "paraphrase-a": "sha256:9911587a2151ac90d9652e20be03a9ee319b8281542facf5d7fabf68e4576bf9",
    "paraphrase-b": "sha256:657c4ab556089e81b4311eef4fe5b3741957dcaba9c88460d1c4b7e2e709cf1a"
  },
  "record_id": "gloss-prompt-validation-slide-04",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 4,
  "status": "pending"
}
-->
# Slide 04 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `cd652469a57e74d3b9778fe7df68da1f605a12124885379bb58eea5504ed44d7`
- Paraphrase A SHA-256: `9911587a2151ac90d9652e20be03a9ee319b8281542facf5d7fabf68e4576bf9`
- Paraphrase B SHA-256: `657c4ab556089e81b4311eef4fe5b3741957dcaba9c88460d1c4b7e2e709cf1a`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
