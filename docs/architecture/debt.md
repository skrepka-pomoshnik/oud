# Architecture limits

The architecture quality check enforces the current tree directly. It rejects
functions above complexity 7, modules above 1,000 physical lines, package
directories with more than seven direct Python entities, and UI-independent
modules importing curses or oud.presentation.tui.

There is no historical debt baseline. A violation is a current failure and must
be fixed rather than recorded as an exception.

## Package boundaries

Every Python package under oud and petrucci is limited to seven direct Python
modules or child packages. tests/test_package_structure.py enforces the limit
repository-wide and locks the two public root shapes. Petrucci owns six
directional domains: adapters, core data, engraving, input, rendering, and
terminal presentation. Oud groups runtime presentation separately from playback
and plugin services; LilyPond, MIDI, and FT3 each own their internal
subpackages.

The former oud.core package mixed file import, playback, plugin records, and
editor assignment policy without a coherent owner. It has been removed:

- FT3, TAB, and MusicXML readers live in oud.importers;
- playback cursor/timeline contracts live in oud.services.playback;
- plugin transport records live in oud.services.plugins.model;
- tablature pitch assignment lives in oud.editor.editing.tab.assignment;
- Petrucci is a top-level package and imports no oud module.

Editor state transitions and viewport/history logic import neither curses nor
oud.presentation.tui; terminal input, loop, and screen adaptation remain under
oud.presentation.tui and oud.presentation.ui.

## Module ownership

FT3 import separates metadata, tablature, note records, score mapping, imported
score layers, text rows, and duration normalization. LilyPond separates common
projection, tablature, vocal, and document/process ownership. MIDI separates
projection, byte encoding, file assembly, and player runtime.

The score importer keeps its public entry point in oud.importers.ft3.score;
imported-score assembly and lyric matrix handling live in
oud.importers.ft3.score_layers. Test files are split by behavior rather than
kept as oversized catch-all modules.

## Enforcement

scripts/checks/architecture_debt.py runs Ruff's C901 check with --ignore-noqa
and scans module size and dependency boundaries. scripts/quality.sh runs it
before Ruff, formatting, typing, and tests. There are no local complexity
suppressions or baseline entries to retire.
