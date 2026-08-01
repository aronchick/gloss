<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:934cebc8dd47287bb3011f4b63c89a826dbf65a2028b57e6bd6b5499eb4fae90",
    "paraphrase-a": "sha256:7b12626839284e7317b0ec7b8458ac2f02a2e828603613eb090629c7ca9dfe24",
    "paraphrase-b": "sha256:389445e7dbe67b5311bf5a9f4cd8aa0ab86ae563161bb455dc858811b58caaba"
  },
  "record_id": "gloss-prompt-validation-slide-10",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 10,
  "status": "pending"
}
-->
# Slide 10 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `934cebc8dd47287bb3011f4b63c89a826dbf65a2028b57e6bd6b5499eb4fae90`
- Paraphrase A SHA-256: `7b12626839284e7317b0ec7b8458ac2f02a2e828603613eb090629c7ca9dfe24`
- Paraphrase B SHA-256: `389445e7dbe67b5311bf5a9f4cd8aa0ab86ae563161bb455dc858811b58caaba`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
