<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:57896c563e2761dd90eea8b40e94511cb6d80c710be8a68e6e8c5eee94c4f2a6",
    "paraphrase-a": "sha256:1af4c47a917b2e536b2f1ad95773b5a5e35f047c623524aa3c9a4fb580a0a9ea",
    "paraphrase-b": "sha256:54f7f24199f5874161a1e25530f1dbbf4e5f0d31dddf82e307933c8f75222c9d"
  },
  "record_id": "acidslide-prompt-validation-slide-09",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 9,
  "status": "pending"
}
-->
# Slide 09 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `57896c563e2761dd90eea8b40e94511cb6d80c710be8a68e6e8c5eee94c4f2a6`
- Paraphrase A SHA-256: `1af4c47a917b2e536b2f1ad95773b5a5e35f047c623524aa3c9a4fb580a0a9ea`
- Paraphrase B SHA-256: `54f7f24199f5874161a1e25530f1dbbf4e5f0d31dddf82e307933c8f75222c9d`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
