<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:8c8fbe1a7ca1f5f4af7eaab91884cb28165531b11d41246e58caa9fed6659dbe",
    "paraphrase-a": "sha256:bff9a649c00839e7e0e8b498af66ac6e24a0078e95e3f8f070b1a3d1fee84ebb",
    "paraphrase-b": "sha256:b74bfd39b122a9c78e4532b36a9e267c08edfb70bd66a10849b7adb567829c80"
  },
  "record_id": "gloss-prompt-validation-slide-12",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 12,
  "status": "pending"
}
-->
# Slide 12 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `8c8fbe1a7ca1f5f4af7eaab91884cb28165531b11d41246e58caa9fed6659dbe`
- Paraphrase A SHA-256: `bff9a649c00839e7e0e8b498af66ac6e24a0078e95e3f8f070b1a3d1fee84ebb`
- Paraphrase B SHA-256: `b74bfd39b122a9c78e4532b36a9e267c08edfb70bd66a10849b7adb567829c80`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
