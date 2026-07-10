# oud

Minimal curses editor for Renaissance lute tablature.

Current import/export focus:

- `.tab` editing and writing
- `.ft3` import with tab, vocal, lyric, and mixed-score views
- MIDI, LilyPond/PDF, MusicXML, and ASCII export

![oud editing a real FT3 score in the terminal](https://raw.githubusercontent.com/skrepka-pomoshnik/oud/main/docs/oud-tui.svg)

## Docs

- User/developer usage reference: `DOCS.md`
- Release checklist: `RELEASING.md`

## Credits

Format cues for `.tab` parsing are inspired by luteconv (GPLv3).

The tablature files in `lutemusic/` and most files in `examples/` are typesettings
by Sarge Gerbode from [lutemusic.org](https://www.lutemusic.org), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — see
`lutemusic/README.md`. They are not covered by this project's GPL-3.0 license.

## Install

```
pip install .        # or: uv sync
```

Requires Python 3.11+. This installs the `oud` command. No runtime
dependencies beyond the standard library; MIDI playback optionally uses
`fluidsynth` or `timidity` if installed.

Importer release smoke tests can scan a local tree or a bounded temporary
sample from lutemusic.org:

```
python3 scripts/corpus_smoke.py lutemusic
python3 scripts/corpus_smoke.py --fetch-lutemusic 250 \
  --lutemusic-url https://browse.lutemusic.org/tabs/composers/
```

## Run

```
oud examples/example.ft3
# or straight from a checkout:
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

## Petrucci typesetting library

`oud.petrucci` is the reusable character-cell typesetting layer behind the TUI.
It owns the score model, tablature policies, spacing, vocal/note-staff engraving,
and framebuffer renderer without requiring editor state:

```python
from oud.petrucci import Bar, Chord, Note, Piece, TypesetOptions, typeset_text

piece = Piece(
    title="Fantasia",
    bars=[Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)])])],
)
print(typeset_text(piece, options=TypesetOptions(width=80, height=20)))
```

`typeset_piece` also returns fixed-size frame lines, per-cell style attributes,
and logical-to-display cursor maps for embedding in another terminal UI. Legacy
`oud.core` and `oud.ui` rendering imports remain compatible for this alpha.

## Commands

```
:w [path]       write .tab
:wa [path]      write ascii
:e <path>       open
:help           open help in less
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
:dark / :light  force dark/light color theme (:set theme=auto follows terminal)
```

## FT3 Support

- All 35 bundled FT3 files load without warnings or unknown staffs.
- Tab, vocal/lyric, mixed-score, playback, and LilyPond paths are covered.
- FT3 is import-only. Save edits as TAB or export to MusicXML/LilyPond/MIDI.
- Undocumented binary details are preserved but not guessed.

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
soundfont = "~/soundfonts/my-soundfont.sf2"
midipatch = 24
```

## Rest rendering

Rests are shown as `_.` in the staff.

## Architecture (quick)

- `oud/petrucci/` reusable score model and tab/note character-cell typesetting
- `oud/core/` FT3/TAB/MusicXML parsing and import semantics
- `oud/editor/` state, ops, undo/redo, commands
- `oud/tui/` input, controller, viewport
- `oud/ui/` curses adapter and compatibility imports
- `oud/exports/` tab/ly/midi exporters
- `oud/plugins/` self-contained plugins

Entry points:
- `app.py` (root wrapper) → `oud/app.py`
- `cli.py` (root wrapper) → `oud/cli.py`
