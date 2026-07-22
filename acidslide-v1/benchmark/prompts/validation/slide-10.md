<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:006bf8acf3a012f34c9d01aa24431d63bb1194d128736eab3fd1c3553352fabf",
    "paraphrase-a": "sha256:388f3c97af5824d60fa4bb73d5d162a05967b0c220b0429ee9d3b07a0b43f6ad",
    "paraphrase-b": "sha256:5054c2987457d83c0bf514be43f125dee7917bb262ad0219a83f925a975279a5"
  },
  "record_id": "acidslide-prompt-validation-slide-10",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 10,
  "status": "pending"
}
-->
# Slide 10 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `006bf8acf3a012f34c9d01aa24431d63bb1194d128736eab3fd1c3553352fabf`
- Paraphrase A SHA-256: `388f3c97af5824d60fa4bb73d5d162a05967b0c220b0429ee9d3b07a0b43f6ad`
- Paraphrase B SHA-256: `5054c2987457d83c0bf514be43f125dee7917bb262ad0219a83f925a975279a5`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
