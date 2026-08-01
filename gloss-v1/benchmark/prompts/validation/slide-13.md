<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:382821283a568690e30b6ffa51916a7ad61229593e7f58391488519629991278",
    "paraphrase-a": "sha256:e09abd58869e5fa99b2d2c2d55f31a3b32ac1703887e47993b3161b5855c8eb9",
    "paraphrase-b": "sha256:44bcde5d8ddd81749c543166dbc23280ca55985ed57cebda36c2728fc0934642"
  },
  "record_id": "gloss-prompt-validation-slide-13",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 13,
  "status": "pending"
}
-->
# Slide 13 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `382821283a568690e30b6ffa51916a7ad61229593e7f58391488519629991278`
- Paraphrase A SHA-256: `e09abd58869e5fa99b2d2c2d55f31a3b32ac1703887e47993b3161b5855c8eb9`
- Paraphrase B SHA-256: `44bcde5d8ddd81749c543166dbc23280ca55985ed57cebda36c2728fc0934642`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
