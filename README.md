# oud

Minimal curses editor for Renaissance lute tablature.

Current import/export focus:

- `.tab` and `.ft3` editing in TUI
- vocal note-staff + lyrics rendering for supported FT3 text records
- partial mixed-score FT3 import layer for non-tab note/barline/text staves

## Docs

- User/developer usage reference: `DOCS.md`

## Credits

Format cues for `.tab` parsing are inspired by luteconv (GPLv3).

## Run

```
python3 app.py examples/example.ft3
```

## Controls (vim)

- `h/j/k/l` move one cell/row
- `J/K` jump to next/previous rendered row (same bar offset)
- `i` insert mode, `esc` normal mode
- `r` replace one cell (normal), `r` rest (insert)
- `:` command mode, `?` help
- `x` delete note (normal mode), space clears in insert mode
- `o/O` add bar after/before, `+/-` delete bar

## Controls (casual)

- `w/a/s/d` move
- `,` / `.` prev/next bar
- `Insert` add bar, `Delete` delete bar
- `F1` help

## ASCII preview

```
 6|a--b--c--d--|e--f--g--a--|
 5|---------------0---------|
 4|---------2----------------|
 3|-----2--------------------|
 2|--------------------------|
 1|--------------------------|
```

ASCII note/lyric lanes are rendered from the same layout path as the TUI frame.

## Commands

```
:w [path]       write .tab
:wa [path]      write ascii
:e <path>       open
:midi [path]    export midi
:play [bar]     play from bar (1-based)
:play loop [n]  loop current bar or active visual range n times (default 2)
:lilypond [path] export lilypond
:pdf            export lilypond + compile pdf
:midicmd [path] show midi command
:source [path]  view file with less
:set maxbars=.. limit bars per system
:set measures=every measuresstep=10
:set barsperline=0   auto bars/row
:set spacingmode=packed|spread|auto spacingfill=stretch|center|compact|smart
```

## FT3 Support

- Structured FT3 vocal/lyric rows are imported and rendered in TUI.
- Raw non-tab FT3 note bars and barline-only bars are now classified into dedicated imported staffs instead of generic unknown blobs.
- Fully mixed non-tab FT3 scores are still partial: import layer exists, full readonly viewer parity is not finished yet.

## Status + Info

- Status bar shows: bar/beat, current duration, current time symbol.
- File path and technical metadata are in `:info`.

## Tuning order

Tuning strings are written low → high, e.g. `g2c3f3a3d4g4`.

## Duration keys (French insert mode)

- `1 -> 1` (whole)
- `2 -> 2` (half)
- `3 -> 4` (quarter)
- `4 -> 8` (eighth)
- `5 -> 16`
- `6 -> 32`
- `7 -> 64`

## LilyPond tablature

French tablature output uses `fret-letter-tablature-format` with default letter labels.
You can customize bass strings and labels in `config.toml`:

```
basstuning = "c2 d2 e2 fis2 g2"
fretlabels = "a b r d e f g h i k l"
```

## MIDI soundfont

Set your SoundFont in `config.toml`:

```
soundfont = "/Users/s/Library/Audio/Sounds/Banks/SC-55 SoundFont v1.2b.sf2"
midipatch = 24
```

## Rest rendering

Rests are shown as `_.` in the staff.

## Architecture (quick)

- `oud/core/` parsing, models, time/tuning/render utilities
- `oud/editor/` state, ops, undo/redo, commands
- `oud/tui/` input, controller, viewport
- `oud/ui/` curses rendering and layout
- `oud/exports/` tab/ly/midi exporters
- `oud/plugins/` self-contained plugins

Entry points:
- `app.py` (root wrapper) → `oud/app.py`
- `cli.py` (root wrapper) → `oud/cli.py`
