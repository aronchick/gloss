<!-- gloss-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:e114750708bb759b186732535c60e893d34eb3dac4b420930218e1536292686b",
    "paraphrase-a": "sha256:272a2766cdd5fad1d205579eac1f36c099f71481e6774e62bf09ae0f7a74f8b5",
    "paraphrase-b": "sha256:5f03620af74ab850bf6da5eee47980e3f11a1680067867a1bd82c4c54fb03926"
  },
  "record_id": "gloss-prompt-validation-slide-15",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 15,
  "status": "pending"
}
-->
# Slide 15 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `e114750708bb759b186732535c60e893d34eb3dac4b420930218e1536292686b`
- Paraphrase A SHA-256: `272a2766cdd5fad1d205579eac1f36c099f71481e6774e62bf09ae0f7a74f8b5`
- Paraphrase B SHA-256: `5f03620af74ab850bf6da5eee47980e3f11a1680067867a1bd82c4c54fb03926`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
