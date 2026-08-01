<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:285a00376bd518bef4125df2166023099fe8bc3aefa7def2828ce7484897268e",
    "paraphrase-a": "sha256:5762ef4e1caaaa84204c9e7b6bb0c505a1a7aea99bbe035b9683e5a8efc0e9ca",
    "paraphrase-b": "sha256:621455b4003dd2da7207bfb1349ce1f94f772f8ff24ed30e70a88d6a21cea7c4"
  },
  "record_id": "gloss-prompt-validation-slide-20",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 20,
  "status": "pending"
}
-->
# Slide 20 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `285a00376bd518bef4125df2166023099fe8bc3aefa7def2828ce7484897268e`
- Paraphrase A SHA-256: `5762ef4e1caaaa84204c9e7b6bb0c505a1a7aea99bbe035b9683e5a8efc0e9ca`
- Paraphrase B SHA-256: `621455b4003dd2da7207bfb1349ce1f94f772f8ff24ed30e70a88d6a21cea7c4`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
