# Architecture debt

Baseline: 2026-07-19. This is active debt, not an exemption from review.
`tools/check_architecture_debt.py` scans through every `noqa`, and CI rejects a
new function above complexity 7, a higher score for an existing function, a new
module above 1,000 physical lines, or growth in an existing oversized module.
The exact machine-readable baseline is `architecture-debt.json`.

## Package boundaries

The former `oud.core` package mixed file import, playback, plugin records, and
editor assignment policy without a coherent owner. It has been removed:

- FT3, TAB, and MusicXML readers live in `oud.importers`;
- playback cursor/timeline contracts live in `oud.playback`;
- plugin transport records live in `oud.plugins.model`;
- tablature pitch assignment lives in `oud.editor.tab_assignment`;
- Petrucci is a top-level package and imports no `oud` module.

Editor state transitions and viewport/history logic import neither `curses` nor
`oud.tui`; terminal input, loop, and screen adaptation remain under `oud.tui`
and `oud.ui`. The architecture gate checks this dependency direction directly.

The old paths are intentionally unsupported. Adding forwarding modules would
restore two canonical paths and hide incomplete migrations.

## Oversized modules

Five production modules remain above 1,000 physical lines:

| Module | Baseline | Intended split |
|---|---:|---|
| `oud/importers/ft3.py` | 1,769 | container scan, record decode, staff assembly, normalization |
| `oud/exports/lilypond.py` | 1,384 | document/header, tablature, notation/lyrics, subprocess workflow |
| `oud/importers/_ft3_text.py` | 1,175 | row tokenization, classification, lyric assembly, record facade |
| `oud/exports/midi.py` | 1,097 | event collection, SMF encoding, playback command/process |
| `petrucci/view_model.py` | 1,068 | width planning, source projection, tuning labels, rendered bar records |

Four test modules are also oversized: `tests/test_ui_render_split.py` (1,954),
`tests/test_lilypond.py` (1,197), `tests/test_editor.py` (1,183), and
`tests/test_tui_commands_exec.py` (1,164). Split them by public behavior as the
corresponding production ownership is clarified; do not create numbered test
fragments.

## Complexity

The enforced ceiling is 7. The baseline currently contains 166 over-limit
functions, including suppressed findings. The highest-risk dispatchers are
`oud.editor.normal_actions.handle_normal` (87),
`petrucci.render_system.render_systems` (70),
`oud.editor.undo_ops.apply_action` (53), `oud.importers.ft3.load_ft3` (44),
`oud.exports.export_tab.export_tab` (35), and
`oud.importers.tab.parse_tab_lines_data` (30).

Retirement order follows ownership and risk:

1. Decompose the remaining renderer and editor dispatchers without changing output.
2. Split FT3 scanning, decoding, assembly, and normalization behind one `load_ft3` facade.
3. Separate LilyPond and MIDI model projection from serialization and process execution.
4. Retire remaining local findings, lowering `architecture-debt.json` after each verified change.

An entry is retired only after focused regressions and the full quality gate
pass. Moving code without reducing ownership or complexity does not count.
