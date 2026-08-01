<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:dea5a19bec385644f739415d44b6c7b9ff45ee3c0b455e1078ea1e4432e70adf",
    "paraphrase-a": "sha256:f93a21e44317dfa7c6731f945b297615dee34432a107dc35fa4ef256f4e87bed",
    "paraphrase-b": "sha256:19a2cc9a8ec61fd6c3c19abbb91bd3d7d6c35f6219bc52bd523c6f0e709135a3"
  },
  "record_id": "gloss-prompt-validation-slide-11",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 11,
  "status": "pending"
}
-->
# Slide 11 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `dea5a19bec385644f739415d44b6c7b9ff45ee3c0b455e1078ea1e4432e70adf`
- Paraphrase A SHA-256: `f93a21e44317dfa7c6731f945b297615dee34432a107dc35fa4ef256f4e87bed`
- Paraphrase B SHA-256: `19a2cc9a8ec61fd6c3c19abbb91bd3d7d6c35f6219bc52bd523c6f0e709135a3`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
