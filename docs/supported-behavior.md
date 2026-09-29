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

## Historical notation constructs

What Oud and Petrucci do with each construct of historical sources, as of
2026-09-29. `Supported` means the construct is read, kept, and rendered or
exported by the tested path. `Partial` means part of its meaning is kept.
`Unsupported` means the construct is not modelled: the source data is not
interpreted, and a file that contains it is read through the modern model or
its record is left in the FT3 source. Enforcement (rejecting such constructs
visibly) is `TODO.md` `C13`; this table is the documented boundary until then.
This is not a claim of general mensural, neumatic, or chant support.

| Construct | Status | What is kept | Evidence |
| --- | --- | --- | --- |
| Mensuration signs (`C`, `C\|`, ...) | Partial | The written sign and its effective meter, as separate records; no perfection, imperfection, or alteration | `tests/test_source_model.py::test_source_document_separates_written_signs_from_meaning` |
| Proportion signs (`3:2`) | Partial | The written proportion and its ratio; terminal layout keeps exact onsets | `tests/test_source_model.py::test_source_document_separates_written_signs_from_meaning`, `tests/test_petrucci_proportional_layout.py::test_proportional_layout_uses_exact_columns_without_respacing` |
| Common time and cut time | Supported | Read from FT3 and rendered as common and cut time | `tests/test_petrucci_piece_adapter.py::test_piece_adapter_preserves_ft3_chords_voices_ornaments_endings_and_cut_time` |
| Repeats and first/second endings | Supported | Read from FT3 and rendered in the terminal | `tests/test_ft3.py::test_parse_bar_decodes_ft3_second_ending_flag`, `tests/test_petrucci_terminal.py::test_safe_terminal_distinguishes_repeat_barlines` |
| Fermatas | Supported | Kept and rendered above the staff | `tests/test_petrucci_terminal.py::test_terminal_paints_endings_ornaments_and_fermatas_in_reserved_rows` |
| Tuplets | Supported | Written ratio and value; one bracket per group | `tests/test_petrucci_layout.py::test_tuplet_ratio_recovers_the_written_note_value` |
| Grace notes | Partial | Kept as grace events; no size change | `tests/test_petrucci_piece_adapter.py::test_piece_adapter_preserves_irregular_grace_tuplet_slur_and_mid_score_changes` |
| Treble and bass clefs, key signatures | Supported | Rendered with key-aware accidentals | `tests/test_petrucci_layout.py::test_key_signatures_use_separate_conventional_treble_and_bass_positions` |
| Dots as modern augmentation | Supported | Dotted values in the model, kept through a MusicXML round trip | `tests/test_musicxml_roundtrip.py::test_everything_oud_models_survives` |
| C clefs (alto, tenor) | Unsupported | - | - |
| Coloration | Unsupported | - | - |
| Ligatures | Unsupported | - | - |
| Perfection, imperfection, alteration | Unsupported | - | - |
| Dot of division or perfection | Unsupported | Treated as augmentation | - |
| Musica ficta | Unsupported | - | - |
| Custos | Unsupported | - | - |
| Interpreted onset and duration under a mensuration | Unsupported | - | - |
| Alternative editorial interpretations of one source | Unsupported | - | - |
| Neumes, chant, `gabc` | Unsupported | Out of scope (see `TODO.md`) | - |

Unsupported behavior fails explicitly or is absent from the interface; it is
not emulated by silently dropping source information. Publication export is
separate from the terminal proof renderer and does not require an SVG geometry
layer.
