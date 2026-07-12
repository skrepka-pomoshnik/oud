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
- `.ft3` import with editable tab-only projections and read-only vocal, lyric, duet, and mixed-score views
- MIDI, LilyPond/PDF, MusicXML, and ASCII export

FT3 is import-only. Editing a tab-only FT3 creates an explicit TAB write target and never changes the source. FT3 scores containing non-TAB or duet layers open read-only so visible material cannot disappear on save.

![oud editing a tablature score in the terminal](https://raw.githubusercontent.com/skrepka-pomoshnik/oud/main/docs/oud-tui.svg)

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

FT3 integration payloads are external. Fetch the fixed, checksum-verified
manifests, then scan the local cache:

```
python3 scripts/fetch_ft3_corpus.py \
  corpus/ft3-regression.json corpus/ft3-random-75.json
python3 scripts/corpus_smoke.py lutemusic
```

## Run

```
oud examples/si_par_souffrir.tab
# or straight from a checkout:
uv run oud examples/si_par_souffrir.tab
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
:w [path]       write .tab (first write prompts for Save As)
:wa [path]      export ascii without marking the score saved
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
- `oud/ui/` curses adapter
- `oud/exports/` tab/ly/midi exporters
- `oud/plugins/` self-contained plugins

Entry point: `oud` -> `oud.app:main`.

## Thanks

Format cues for `.tab` parsing are inspired by luteconv (GPLv3).

The external FT3 test manifests reference typesettings by Sarge Gerbode from
[lutemusic.org](https://www.lutemusic.org), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); see
`lutemusic/README.md`. Their payloads are ignored by Git and are not covered by
this project's GPL-3.0 license.

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
