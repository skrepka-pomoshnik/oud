# OUD(1)

## NAME

`oud` - terminal editor and viewer for Renaissance lute tablature

## DISCLAIMER

This project is vibe-coded. Treat its documented format boundaries and quality gates as the source of truth, and preserve source files when testing import or export behavior.

## SYNOPSIS

```text
oud [FILE]
```

## DESCRIPTION

Minimal curses editor for Renaissance lute tablature.

Current import/export focus:

- `.tab` editing and writing
- `.ft3` import with tab, vocal, lyric, and mixed-score views
- MIDI, LilyPond/PDF, MusicXML, and ASCII export

![oud editing a real FT3 score in the terminal](https://raw.githubusercontent.com/skrepka-pomoshnik/oud/main/docs/oud-tui.svg)

## Docs

- [User and developer guide](docs/user-guide.md)
- [FT3 reverse-engineering notes](docs/ft3-format.md)
- [Release checklist](docs/releasing.md)
- [Documentation map](docs/README.md)

## QUICK START

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

## MIDI soundfont

Set your SoundFont in `config.toml`:

```
soundfont = "~/soundfonts/my-soundfont.sf2"
midipatch = 24
```
## Architecture overview

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

## Thanks

Format cues for `.tab` parsing are inspired by luteconv (GPLv3).

The tablature files in `lutemusic/` and most files in `examples/` are typesettings
by Sarge Gerbode from [lutemusic.org](https://www.lutemusic.org), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — see
`lutemusic/README.md`. They are not covered by this project's GPL-3.0 license.

## FILES

- `docs/README.md` - documentation map
- `docs/user-guide.md` - detailed usage and workflows
- `docs/ft3-format.md` - reverse-engineered FT3 format notes
- `docs/releasing.md` - release procedure
- `scripts/quality.sh` - shared local and CI quality gate

## DEVELOPMENT

```bash
uv sync --dev
./scripts/quality.sh
```

The gate runs Ruff linting, Ruff formatting checks, project-scoped Ty, pytest with coverage, and the corpus smoke test.

## LICENSE

See `LICENSE`.
