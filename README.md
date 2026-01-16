# oud

Minimal curses editor for Renaissance lute tablature.

## Run

```
python3 app.py examples/example.ft3
```

## Controls

- `h/j/k/l` move
- `i` insert mode, `esc` normal mode
- `r` replace one cell
- `:` command mode, `?` help

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
```
