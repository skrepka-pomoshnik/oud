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

One production module remains above 1,000 physical lines:

| Module | Baseline | Intended split |
|---|---:|---|
| `petrucci/view_model.py` | 1,068 | width planning, source projection, tuning labels, rendered bar records |

FT3 import now separates metadata, tablature, note records, score assembly,
text rows, and duration normalization. LilyPond separates common projection,
tablature, vocal, and document/process ownership; MIDI separates projection,
byte encoding, file assembly, and player runtime. The four former oversized
test modules are split by behavior, with every test module below the ceiling.

## Complexity

The enforced ceiling is 7. The baseline currently contains 157 over-limit
functions, including suppressed findings. The former normal-mode and Petrucci
render dispatchers now delegate to focused command, movement, system, rhythm,
staff, and cue modules without over-limit coordinator functions. The highest
remaining findings include `oud.editor.undo_ops.apply_action` (53),
`oud.importers.ft3.load_ft3` (44), `oud.exports.export_tab.export_tab` (35),
and `oud.importers.tab.parse_tab_lines_data` (30).

Ruff 0.16 also exposes 31 legacy production call surfaces with more than five
positional parameters. Each suppression is function-local and carries its
replacement boundary inline. Retire these with typed request or policy records
when splitting the owning renderer/exporter; do not replace them with per-file
ignores or pass-through wrappers.

Retirement order follows ownership and risk:

1. Split `petrucci/view_model.py` along its existing projection and display boundaries.
2. Decompose the remaining high-complexity editor, importer, and export functions.
3. Replace legacy positional render/export surfaces with typed request records.
4. Retire remaining local findings, lowering `architecture-debt.json` after each verified change.

An entry is retired only after focused regressions and the full quality gate
pass. Moving code without reducing ownership or complexity does not count.
