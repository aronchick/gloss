<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:aaccdd6f2695aa115d95e995dd8a854d5d51acbe9f8af8146e329c8382942c07",
    "paraphrase-a": "sha256:3de26c4f298a0ea045c1cbfa437544cc9e1985e052bb7aa56b919429d83572fe",
    "paraphrase-b": "sha256:5fa3c2ef1bce7a73657bfb976acbc1fb480f60b1a5b17802144f6596a78f7076"
  },
  "record_id": "acidslide-prompt-validation-slide-15",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 15,
  "status": "pending"
}
-->
# Slide 15 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `aaccdd6f2695aa115d95e995dd8a854d5d51acbe9f8af8146e329c8382942c07`
- Paraphrase A SHA-256: `3de26c4f298a0ea045c1cbfa437544cc9e1985e052bb7aa56b919429d83572fe`
- Paraphrase B SHA-256: `5fa3c2ef1bce7a73657bfb976acbc1fb480f60b1a5b17802144f6596a78f7076`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
