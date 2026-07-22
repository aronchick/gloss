<!-- acidslide-prompt-validation-v1
{
  "authors": [],
  "pairwise_similarity_diagnostics": [],
  "prompt_hashes": {
    "canonical": "sha256:1c343788be39b16eeacc5f669794a8187608f0c037c631081f8d52066c013666",
    "paraphrase-a": "sha256:df9fbec40ead118b8266767a0d2c6fe34df32c2a4bbc4f622606a365a2e0e539",
    "paraphrase-b": "sha256:a91058ab785b02e919cf9ecba6d8a43a0e68dd4504953582f4eaa202bd45e3aa"
  },
  "record_id": "acidslide-prompt-validation-slide-14",
  "round_id": null,
  "schema_version": "1.0",
  "slide": 14,
  "status": "pending"
}
-->
# Slide 14 prompt validation

- Prompt contract status: complete
- Canonical/paraphrase hard-constraint parity: pass
- Canonical SHA-256: `1c343788be39b16eeacc5f669794a8187608f0c037c631081f8d52066c013666`
- Paraphrase A SHA-256: `df9fbec40ead118b8266767a0d2c6fe34df32c2a4bbc4f622606a365a2e0e539`
- Paraphrase B SHA-256: `a91058ab785b02e919cf9ecba6d8a43a0e68dd4504953582f4eaa202bd45e3aa`
- Independent-author convergence: not run
- Required blinded author count: 3
- Mandatory assertion pass status: pending for all 3 implementations
- Structural similarity: diagnostic only; no release threshold
- Release gate: blocked until three clean-context authors independently build the slide and every mandatory assertion passes for every implementation; any failed assertion or author disagreement requires prompt/oracle revision and a fresh blinded round

The static record verifies that literal text, asset filenames, colors, dimensions, percentages, rotations, and multilingual strings are preserved across all three prompt variants. It does not claim authoring convergence or gold-deck fidelity, and structural similarity cannot override a missed requirement.
