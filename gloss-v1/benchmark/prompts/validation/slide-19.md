<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:418adf962d94466a9c9a0e2257ef6f17b83fee6964b017dd3d9ae757b39a6fce",
    "paraphrase-a": "sha256:4ae70b8280cdb45e511f8def414269d24b0c911b845153999737fb7392ee8d64",
    "paraphrase-b": "sha256:60cc142c319c146a2272d3d5bafe40078e40ba7b7833e115495e50baac89fdac"
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
- Canonical SHA-256: `418adf962d94466a9c9a0e2257ef6f17b83fee6964b017dd3d9ae757b39a6fce`
- Paraphrase A SHA-256: `4ae70b8280cdb45e511f8def414269d24b0c911b845153999737fb7392ee8d64`
- Paraphrase B SHA-256: `60cc142c319c146a2272d3d5bafe40078e40ba7b7833e115495e50baac89fdac`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
