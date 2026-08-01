<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:96be78cb3c8dccc172c44d798bb5dd130d1cb4a12fc43a58558ba60f3c4a3a78",
    "paraphrase-a": "sha256:36c8bea21060c4f7dd81a62a362874701df2b1f515aa78bc4d75f6b289647e55",
    "paraphrase-b": "sha256:7993bd23f91504878095ecea7b3ce083d0db8722d09070953b91339f8c2c4c5d"
  },
  "record_id": "gloss-prompt-validation-slide-03",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 3,
  "status": "pending"
}
-->
# Slide 03 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `96be78cb3c8dccc172c44d798bb5dd130d1cb4a12fc43a58558ba60f3c4a3a78`
- Paraphrase A SHA-256: `36c8bea21060c4f7dd81a62a362874701df2b1f515aa78bc4d75f6b289647e55`
- Paraphrase B SHA-256: `7993bd23f91504878095ecea7b3ce083d0db8722d09070953b91339f8c2c4c5d`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
