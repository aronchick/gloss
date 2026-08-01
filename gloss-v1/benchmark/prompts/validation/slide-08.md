<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:e866e978bed297c7c8926ab870f1fc51e301af39a0da49f81937affbec46153d",
    "paraphrase-a": "sha256:07e2da94a5358691e5e36c79652f3c1461b8d55d0770a0e38d05b36718c1bf8a",
    "paraphrase-b": "sha256:daed4faf5e5946d0cc09bf761e4ce16f99c9c46e56fc159aa23a4422805963dc"
  },
  "record_id": "gloss-prompt-validation-slide-08",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 8,
  "status": "pending"
}
-->
# Slide 08 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `e866e978bed297c7c8926ab870f1fc51e301af39a0da49f81937affbec46153d`
- Paraphrase A SHA-256: `07e2da94a5358691e5e36c79652f3c1461b8d55d0770a0e38d05b36718c1bf8a`
- Paraphrase B SHA-256: `daed4faf5e5946d0cc09bf761e4ce16f99c9c46e56fc159aa23a4422805963dc`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
