<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:30d72528b5c55c9875dbc27f083dd96c100227895659f492fb662bb9b0e03c16",
    "paraphrase-a": "sha256:d2c5f029585936e95f1918bef1d897e8236a3f61addf84634ae4cd7138abb158",
    "paraphrase-b": "sha256:bb47493f69bc94239b10aa3234ac33082075b7ed9017da37a4f574bcba16434c"
  },
  "record_id": "gloss-prompt-validation-slide-14",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 14,
  "status": "pending"
}
-->
# Slide 14 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `30d72528b5c55c9875dbc27f083dd96c100227895659f492fb662bb9b0e03c16`
- Paraphrase A SHA-256: `d2c5f029585936e95f1918bef1d897e8236a3f61addf84634ae4cd7138abb158`
- Paraphrase B SHA-256: `bb47493f69bc94239b10aa3234ac33082075b7ed9017da37a4f574bcba16434c`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
