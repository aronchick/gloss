<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:48ce312215ea5dd2301719001fd72474946b252390643ee92a84574f49a3055b",
    "paraphrase-a": "sha256:df76e61dbd7598ff28c485a4fef4ada465f3028b37d973f12c76cdf7172230e0",
    "paraphrase-b": "sha256:e0e6cd11769f75eae8aedc33d4c85aa2fb8d181f0afd7459fc147e2311492493"
  },
  "record_id": "acidslide-prompt-validation-slide-01",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 1,
  "status": "pending"
}
-->
# Slide 01 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `48ce312215ea5dd2301719001fd72474946b252390643ee92a84574f49a3055b`
- Paraphrase A SHA-256: `df76e61dbd7598ff28c485a4fef4ada465f3028b37d973f12c76cdf7172230e0`
- Paraphrase B SHA-256: `e0e6cd11769f75eae8aedc33d4c85aa2fb8d181f0afd7459fc147e2311492493`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
