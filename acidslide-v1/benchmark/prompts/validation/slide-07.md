<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:558958a1925810b8ffad53d07ae297675916d14d757f829ac005e99ada4a0210",
    "paraphrase-a": "sha256:c7cbe77cbbb83b82b1f1fa797518ab0fe7d75bc067bbb4e4ded27efd08a2cd3f",
    "paraphrase-b": "sha256:d1618f9b2471681712bc415b6d31d5329ac0f2b4beb110bf8ef39b3c7b65a618"
  },
  "record_id": "acidslide-prompt-validation-slide-07",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 7,
  "status": "pending"
}
-->
# Slide 07 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `558958a1925810b8ffad53d07ae297675916d14d757f829ac005e99ada4a0210`
- Paraphrase A SHA-256: `c7cbe77cbbb83b82b1f1fa797518ab0fe7d75bc067bbb4e4ded27efd08a2cd3f`
- Paraphrase B SHA-256: `d1618f9b2471681712bc415b6d31d5329ac0f2b4beb110bf8ef39b3c7b65a618`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
