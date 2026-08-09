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

No production or test module remains above 1,000 physical lines. Petrucci width
planning and tuning-label projection now live separately from rendered bar
source projection.

FT3 import now separates metadata, tablature, note records, score assembly,
text rows, and duration normalization. LilyPond separates common projection,
tablature, vocal, and document/process ownership; MIDI separates projection,
byte encoding, file assembly, and player runtime. The four former oversized
test modules are split by behavior, with every test module below the ceiling.

## Complexity

The enforced ceiling is 7. The baseline currently contains 124 over-limit
functions, including suppressed findings. The former normal-mode and Petrucci
render dispatchers now delegate to focused command, movement, system, rhythm,
staff, cue, and undo-action modules without over-limit coordinator functions.
FT3 loading now has explicit metadata, body-decoding, and finalization phases;
TAB export has separate header, event-projection, and serialization ownership.
Petrucci score validation, layout validation, collision scanning, and tuning
parsing now delegate to focused domain operations below the complexity ceiling.
The highest remaining findings include `oud.editor.insert_actions.handle_insert`
(31), `oud.tui.input.complete_command_text` (31), and
`oud.importers.tab.parse_tab_lines_data` (30).

The debt checker compares findings by module and function identity, with the
recorded score as a maximum. Lower scores are improvements ready for baseline
retirement; only higher scores or additional same-name findings are regressions.

Ruff 0.16 also exposes 31 legacy production call surfaces with more than five
positional parameters. Each suppression is function-local and carries its
replacement boundary inline. Retire these with typed request or policy records
when splitting the owning renderer/exporter; do not replace them with per-file
ignores or pass-through wrappers.

Retirement order follows ownership and risk:

1. Decompose the remaining high-complexity editor, importer, and export functions.
2. Replace legacy positional render/export surfaces with typed request records.
3. Retire remaining local findings, lowering `architecture-debt.json` after each verified change.

An entry is retired only after focused regressions and the full quality gate
pass. Moving code without reducing ownership or complexity does not count.
