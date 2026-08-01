<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:f3f58d4dcefac89e165b5280f1a77628acd801f7d2b7b8d0dece0e2fec81b336",
    "paraphrase-a": "sha256:de58051338911a84bdcde6df2f1846ed914fddab7b66beefebb14c9c6fadbeb4",
    "paraphrase-b": "sha256:b8a864c1c3665f5826ed381b4171dd7d63e6900ced5dee0ee59daebf0a568538"
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
- Canonical SHA-256: `f3f58d4dcefac89e165b5280f1a77628acd801f7d2b7b8d0dece0e2fec81b336`
- Paraphrase A SHA-256: `de58051338911a84bdcde6df2f1846ed914fddab7b66beefebb14c9c6fadbeb4`
- Paraphrase B SHA-256: `b8a864c1c3665f5826ed381b4171dd7d63e6900ced5dee0ee59daebf0a568538`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
