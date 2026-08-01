<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:ed99ade6772a7ff66bc99437abda1951ccf8ee0763cd9d6013fe80b783b46c9d",
    "paraphrase-a": "sha256:4996474870537b4f35c6eaea0daacf8ca73f4fb78091efbdcbad4d7e68388efe",
    "paraphrase-b": "sha256:558738b5c07952357c511f7029538086ac5463d1a084d1807aa57d63443f56f4"
  },
  "record_id": "gloss-prompt-validation-slide-19",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 19,
  "status": "pending"
}
-->
# Slide 19 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `ed99ade6772a7ff66bc99437abda1951ccf8ee0763cd9d6013fe80b783b46c9d`
- Paraphrase A SHA-256: `4996474870537b4f35c6eaea0daacf8ca73f4fb78091efbdcbad4d7e68388efe`
- Paraphrase B SHA-256: `558738b5c07952357c511f7029538086ac5463d1a084d1807aa57d63443f56f4`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
