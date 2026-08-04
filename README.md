# OUD(1)

## NAME

`oud` - terminal editor and viewer for lute tablature

## DISCLAIMER

This project is vibe-coded, use it with care.

## SYNOPSIS

```text
oud [FILE]
oud ascii INPUT [-o OUTPUT] [--bars N|START:END] [-f]
oud convert INPUT OUTPUT [--format FORMAT] [-f]
```

## DESCRIPTION

Minimal curses editor for Renaissance lute tablature.

Current import/export focus:

- `.tab` editing and writing
- `.ft3` import with editable tab-only projections and canonical notation focus for read-only vocal and mixed scores
- MIDI, LilyPond/PDF, MusicXML, and ASCII export

FT3 is import-only. Editing a tab-only FT3 creates an explicit TAB write target and never changes the source. FT3 scores containing non-TAB or duet layers open read-only so visible material cannot disappear on save.

## Docs

- [User and developer guide](docs/user-guide.md)
- [FT3 format notes](docs/ft3-format.md)
- [Documentation map](docs/README.md)

## QUICK START

```
pip install .        # or: uv sync
```

Requires Python 3.11+. This installs the `oud` command. No runtime
dependencies beyond the standard library; MIDI playback optionally uses
`fluidsynth` or `timidity` if installed.

## Run

```
oud examples/si_par_souffrir.tab
# or straight from a checkout:
uv run oud examples/si_par_souffrir.tab
```

Non-interactive conversion infers the format from the output suffix and refuses
to replace an existing file unless `-f` is explicit:

```bash
oud ascii score.ft3 --bars 1:8
oud convert score.ft3 score.musicxml
oud convert score.ft3 score.pdf
printf '%s\n' '-C' 'b' '0a-----' 'e' | oud convert - - --input-format tab --format lilypond
```

Text formats can stream through `-`; MIDI, MXL, and PDF require a file. PDF
conversion keeps the generated `.ly` source when LilyPond is missing or fails.

## Controls

Vim-like:

- `h/j/k/l` move one cell/row
- `J/K` jump to next/previous rendered row (same bar offset)
- `i` insert mode, `esc` normal mode
- `r` replace one cell (normal), `r` rest (insert)
- `:` command mode, `?` help
- `x` delete note (normal mode), space clears in insert mode
- `o/O` add bar after/before, `+/-` delete bar


Casual: 

- `w/a/s/d` or arrows move
- `W/S` jump to the previous/next rendered row
- `,` / `.` prev/next bar
- `Home/End` move to the bar edges; `PgUp/PgDn` scroll
- `Insert` add bar, `Delete` delete bar
- `Ctrl-Z/Ctrl-Y` undo/redo
- `F1` help

## Commands

```
:w [path]       write .tab (first write prompts for Save As)
:wa [path]      export ascii without marking the score saved
:e <path>       open
:help           open help in less
:midi [path]    export midi
:play [bar]     play from bar (1-based)
:play loop [n]  loop current bar or active visual range n times (default 2)
:set playbackscroll=off  disable score following during playback (default on)
:lilypond [path] export lilypond
:pdf            export lilypond + compile pdf
:midicmd [path] show midi command
:source [path]  view file with less
:set maxbars=.. limit bars per system
:set measures=system   number each displayed system
:set measures=every measuresstep=10
:set barsperline=0   auto bars/row
:set spacingmode=packed|spread|auto spacingfill=stretch|center|compact|smart
:dark / :light  force dark/light color theme (:set theme=auto follows terminal)
```

## Architecture overview

- `petrucci/` reusable top-level score model, tab/note input contracts, and character-cell typesetting
- `oud/importers/` FT3/TAB/MusicXML parsing and import semantics
- `oud/editor/` state, ops, undo/redo, commands
- `oud/tui/` input, controller, viewport
- `oud/ui/` curses adapter
- `oud/exports/` TAB, ASCII, LilyPond/PDF, MIDI, and MusicXML exporters
- `oud/plugins/` self-contained plugins

Entry point: `oud` -> `oud.app:main`.

## Thanks

Format cues for `.tab` parsing are inspired by luteconv (GPLv3).

The external FT3 test manifests reference typesettings by Sarge Gerbode from
[lutemusic.org](https://www.lutemusic.org), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); see
`lutemusic/README.md`. Their payloads are ignored by Git and are not covered by
this project's GPL-3.0 license.

## LICENSE

See `LICENSE`.
