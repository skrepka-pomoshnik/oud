# oud

Minimal curses editor for Renaissance lute tablature.

## Run

```
python3 app.py examples/example.ft3
```

## Controls (vim)

- `h/j/k/l` move
- `i` insert mode, `esc` normal mode
- `r` replace one cell
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

## Commands

```
:w [path]       write .tab
:wa [path]      write ascii
:e <path>       open
:midi [path]    export midi
:play [bar]     play from bar (1-based)
:lilypond [path] export lilypond
:pdf            export lilypond + compile pdf
:midicmd [path] show midi command
:source [path]  view file with less
:set maxbars=.. limit bars per system
```

## Tuning order

Tuning strings are written low → high, e.g. `g2c3f3a3d4g4`.

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
