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

## DOCUMENTATION

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

## EXAMPLES

```
oud examples/triste.tab
# or straight from a checkout:
uv run oud examples/triste.tab
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

### VIEW A GENERATED LILYPOND PDF

Generated files belong under the ignored `build/` tree:

```bash
mkdir -p build/lilypond
uv run oud convert examples/triste.tab build/lilypond/triste.pdf -f
xdg-open build/lilypond/triste.pdf  # Linux
# open build/lilypond/triste.pdf   # macOS
```

For the Dowland benchmark:

```bash
uv run python scripts/corpus/fetch.py tests/fixtures/ft3/manifests/ft3-regression.json
uv run oud convert tests/fixtures/ft3/corpus/05_can_she_excuse/can_she_excuse.ft3 \
  build/lilypond/can-she-excuse.pdf -f
```

## CONTROLS

Vim-like:

- `h/j/k/l` move one cell/row
- `J/K` jump to next/previous rendered row (same bar offset)
- `i` insert mode, `esc` normal mode
- `r` replace one cell (normal); in insert mode `z` enters a rest and letters/digits are frets
- `:` command mode, `?` help
- `x` delete note (normal mode), space clears in insert mode
- `o/O` add bar after/before, `+/-` delete bar
- `yy` copy bars, `p/P` paste after/before, `gb` add a configured bass course
- `:pdf` builds a PDF (no single-key shortcut)


Casual: 

- `w/a/s/d` or arrows move
- `W/S` jump to the previous/next rendered row
- `,` / `.` prev/next bar
- `Home/End` move to the bar edges; `PgUp/PgDn` scroll
- `Insert` add bar, `Delete` delete bar
- `Ctrl-Z/Ctrl-Y` undo/redo
- `Ctrl-C` quit like `q` (press again to discard unsaved edits); cancels prompts and closes pages
- `F1` help

## COMMANDS

```
:w [path]       save as .musicxml (default) or .tab; first write opens a prefilled Save As
:wa [path]      export ascii without marking the score saved
:e <path>       open
:help           open help in less
:midi [path]    export midi
:play [bar]     play from bar (1-based)
:play loop [n]  loop current bar or active visual range n times (default 2)
:set playbackscroll=off  disable score following during playback (default on)
:lilypond [path] export lilypond
:pdf [path]     export LilyPond and compile PDF under build/lilypond by default
:midicmd [path] show midi command
:source [path]  view file with less
:set maxbars=.. limit bars per system
:set measures=system   number each displayed system
:set measures=every measuresstep=10
:set barsperline=0   auto bars/row
:set layout=packed|spread|auto justify=stretch|center|compact|smart|edge
:set completion=fzf  use system fzf for fuzzy path ranking (default: prefix)
:dark / :light  force dark/light color theme (:set theme=auto follows terminal)
```

Command and search prompts own the complete bottom row. In commands that take
a path, such as `:e examples/`, Tab completes a unique path or displays every
matching file and directory. `completion=fzf` uses non-interactive system
`fzf --filter`; if `fzf` is unavailable, Oud reports it and uses prefix matching.

`:set` changes apply immediately. Preference keys (theme, keys, layout, flags, …)
are saved to `$XDG_CONFIG_HOME/oud/config.toml` (default `~/.config/oud/`), or to
a `config.toml` in the working directory when that file already has a
`[settings]` table. Document properties (`style`, `strings`, `tuning`, `time`,
`key`, `tempo`, `bassstrings`) apply to the open score only; their new-document
defaults can be edited in the config file. Oud refuses to rewrite a config file
that contains anything other than its `[settings]` table.

## ARCHITECTURE

- `petrucci/` reusable top-level score model, tab/note input contracts, and character-cell typesetting
- `oud/importers/` FT3/TAB/MusicXML parsing and import semantics
- `oud/editor/` state, ops, undo/redo, commands
- `oud/presentation/tui/` input, controller, viewport
- `oud/presentation/ui/` curses adapter
- `oud/exports/` TAB, ASCII, LilyPond/PDF, MIDI, and MusicXML exporters
- `oud/services/plugins/` self-contained plugins

Entry point: `oud` -> `oud.presentation.app:main`.

## CREDITS

- [LilyPond](https://lilypond.org/) is the PDF engraving backend; its regression suite informs publication tests.
- [MuseScore](https://musescore.org/) provides MusicXML interoperability and engraving-test references.
- [luteconv](https://github.com/LukeEmmet/luteconv) provides GPLv3 `.tab` parsing and conversion precedents.
- [FluidSynth](https://www.fluidsynth.org/) and [TiMidity++](https://sourceforge.net/projects/timidity/) are optional MIDI players.
- [fzf](https://github.com/junegunn/fzf) optionally ranks command-line path completions.

The external FT3 test manifests reference typesettings by Sarge Gerbode from
[lutemusic.org](https://www.lutemusic.org), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); see
`tests/fixtures/ft3/README.md`. Their payloads are ignored by Git and are not covered by
this project's GPL-3.0 license.

## LICENSE

See `LICENSE`.
