# Supported behavior

This matrix describes behavior exercised by the automated suite. It is not a
claim of general FT3 or Fronimo parity. `Partial` means the listed workflow is
useful for the tested corpus but known format or engraving coverage remains.

| Area | Behavior | Status | Evidence |
| --- | --- | --- | --- |
| Editing | Deterministic tablature mutation, rendering, and export sequence | Supported | `tests/test_petrucci_operation_sequence.py::test_operation_sequence_is_deterministic_across_render_and_exports` |
| Terminal proof | Curated solo, vocal, and mixed-score rendering | Supported | `tests/test_petrucci_feature_corpus.py::test_curated_render_exports_and_tab_reopen_match_goldens` |
| Terminal proof | Vocal-only canonical score frame | Supported | `tests/test_petrucci_piece_view.py::test_vocal_only_typeset_piece_uses_canonical_score_frame` |
| Terminal proof | Two-voice duet score with staff labels and brace | Supported | `tests/test_ui_render_split.py::test_render_duet_score_view_both_shows_two_staff_labels_and_brace` |
| FT3 import | Read and semantically audit the fixed 514-score compatibility corpus | Partial | `tests/test_ft3_corpus_manifest.py::test_fixed_random_payloads_load_without_semantic_audit_failures` |
| Publication export | LilyPond and MIDI remain deterministic for a mixed operation sequence | Partial | `tests/test_petrucci_operation_sequence.py::test_operation_sequence_is_deterministic_across_render_and_exports` |
| Compatibility | General FT3 or Fronimo parity | Unsupported | - |
| FT3 output | Native FT3 save | Unsupported | - |
| Page layout | Fronimo-compatible page engraving controls | Unsupported | - |
| Authoring | Fronimo templates | Unsupported | - |
| Output | Direct printing | Unsupported | - |

Unsupported behavior fails explicitly or is absent from the interface; it is
not emulated by silently dropping source information. Publication export is
separate from the terminal proof renderer and does not require an SVG geometry
layer.
