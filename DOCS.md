# OUD Docs

This document describes the current feature set, common use cases, and day-to-day usage.

## 1) What OUD Is

`oud` is a terminal (curses) editor for lute tablature with:

- Vim-like editing model (`normal` / `insert` / `command` / `search`).
- TAB and FT3 import.
- TAB and ASCII export.
- MIDI and LilyPond export.
- Minimal dependency runtime.

## 2) Run and Open Files

Run from project root:

```bash
python3 -m oud.app
python3 -m oud.app examples/example.ft3
python3 -m oud.app examples/example.tab
```

Also supported wrappers:

```bash
python3 app.py
python3 app.py examples/example.ft3
```

## 3) Modes

- `normal`: navigation + editor commands.
- `insert`: write frets/rests/durations.
- `:` command prompt: ex-like commands.
- `/` search prompt: search command history style.
- `help`/`info` modes: docs/status pages.
- `plugin` mode: remote/source browsing plugins.

## 4) Key Profiles

Set with:

```text
:set keys=vim
:set keys=vim+arrows
:set keys=casual
:set keys=casual+arrows
```

### Vim profile (core)

- Move: `h j k l` (cell/row step)
- Row jump: `J` / `K` (next/previous rendered row, preserves row offset)
- Insert: `i` or `Enter`
- Replace once: `r`
- Delete note: `x` (`[count]x` supported)
- Undo/redo: `u` / `Ctrl-r`
- Bar add/remove: `o O` and `+ -`
- Help: `?`
- Command: `:`
- Search: `/`

### Vim parity currently implemented

- Char find: `f F t T`, repeat `;` and reverse `,`
- Word search: `*` / `#`, repeat `n` / `N`
- Match jump: `%`
- Marks: `m{char}`, jump with `' {char}` / `` ` {char}``

### Casual profile (core)

- Move: arrows or `w a s d`
- Bar step: `,` / `.`
- Insert/delete bar: `Insert` / `Delete`
- Help: `F1`

## 5) Entering Notes

## 5.1 French tablature

- Frets by letters (`a..`), with historical mapping rules.
- Bass shorthand in insert mode: `/a`, `//a`, `///a` (configured bass availability applies).
- Rest in insert mode: `r`.

## 5.2 Italian tablature

- Frets by numbers (`0..9` + `x`).
- Multi-fret input: `,10` .. `,24` (when `italianmultifret=on`).
- Optional alternate duration hotkeys via `;1..7`.

## 5.3 Durations

French insert-mode digit mapping:

- `1 -> 1` (whole)
- `2 -> 2` (half)
- `3 -> 4` (quarter)
- `4 -> 8` (eighth)
- `5 -> 16`
- `6 -> 32`
- `7 -> 64`

Italian mode keeps numeric fret entry and supports duration with `Ctrl+1..7` or `;1..7`.

Durations are tracked per onset column and rendered according to current flag style/redundancy settings.

## 6) Core Commands

## 6.1 File and session

- `:e <path>` open file
- `:w [path]` write TAB
- `:wa [path]` / `:wascii [path]` / `:writeascii [path]` write ASCII snapshot/export
- `:wq`, `:x` write + quit
- `:q!` force quit

## 6.2 Metadata

- `:title <text>`
- `:subtitle <text>`
- `:author <text>`
- `:composer <text>`
- `:footnote <text>`
- `:header` insert header template

## 6.3 Score editing

- `:bar add|before|after|del`
- `:stave break|join|new|del`
- `:chord add|del`
- `:time <sig|auto>`
- `:barline thin|thick|double|hidden|pale`
- `:repeat none|start|end|dots`
- `:orn <char>|clear`
- `:annot <text>|clear`
- `:highlight on|off`
- `:slur start|end|clear`
- `:tie start|end|clear`
- `:hold start|end|clear`
- `:verify`
- `:tool reflow|gridflags|flagstyle|comments`

## 6.4 Export and playback

- `:midi [path]` export MIDI
- `:play [bar] [tempo]` play from bar
- `:midicmd [path]` show actual external playback command
- `:lilypond [path]` export LilyPond
- `:pdf` compile PDF from LilyPond

## 6.5 Helpers

- `:source [path]` view source in `less`
- `:plugins` open plugin list
- `:info` show current file/settings page

## 7) Settings (`:set`)

`key=value` tokens can be chained in one command:

```text
:set style=french spacingmode=auto spacingfill=compact
```

### Commonly used keys

- Layout: `spacing`, `spacingmode`, `spacingfill`, `barsperline`, `maxbars`, `maxchords`, `bargap`, `linelen`
- Rendering: `flagstyle`, `flagstems`, `flagredundant`, `showdur`, `showextras`, `showtactus`, `grid`
- Notation/meta: `style`, `strings`, `time`, `key`, `measures`, `measuresstep`, `countdots`
- Tuning/view: `tuning`, `bassstrings`, `basslabels`, `showtuning`, `tuninglabels`, `italianorient`, `italianmultifret`, `viewinvert`, `frenchc`
- Playback: `soundfont`, `midipatch`, `midigate`, `tempo`
- Input profile: `keys`

Notes:
- `barsperline=0` means auto.
- `barpad` controls left/right inner padding inside bars.

## 8) Plugin System (Current)

- Open plugin menu with `:plugins` or `gp` in normal mode.
- Current plugin set includes lute music browsing/downloading support.
- In plugin view:
  - `j/k` move selection
  - `l` or `Enter` open
  - `h` back
  - `d` download
  - `/` filter/search
  - `gg` / `G` top/end

## 9) Typical Workflows

## 9.1 Edit an existing FT3/TAB, export PDF

1. Open: `:e file.ft3`
2. Edit in `insert` mode (`i`)
3. Check bar rhythm: `:verify`
4. Export LilyPond: `:lilypond out.ly`
5. Build PDF: `:pdf`

## 9.2 Fast TAB cleanup and reflow

1. Open file
2. Run `:tool comments`
3. Adjust wrap/settings with `:set spacingmode=auto ...`
4. Reflow stave breaks via `:tool reflow`
5. Save `:w`

## 9.3 MIDI playback debugging

1. Set synth values:
   - `:set soundfont=/path/file.sf2 midipatch=24 tempo=90`
2. Inspect command:
   - `:midicmd out.mid`
3. Play from current/selected bar:
   - `:play 12 100`

## 10) Current Limits (Important)

- Primary UI is TUI/curses only (Qt backend is future work).
- Some advanced historical symbols/layouts are partial or pending.
- Import is best-effort for proprietary formats (FT3/JT* semantics vary).
- Horizontal fit is actively tuned; some edge spacing/render scenarios are still under refinement.

## 12) Status and Info Split

- Main status bar keeps live editing context only (bar/beat, duration, time).
- Path/file metadata is intentionally moved to `:info` to keep editing status compact.

## 11) Architecture Map

- `oud/core/`: model, parsers, time/tuning/render utilities.
- `oud/editor/`: state + editing ops + command ops + undo/redo.
- `oud/tui/`: input/prompt/controller/main loop.
- `oud/ui/`: framebuffer adapter + render/layout mapping.
- `oud/exports/`: TAB/LilyPond/MIDI exporters.
- `oud/plugins/`: plugin implementations.

Entry points:

- `/Users/s/Documents/Python/frnm/app.py` -> `/Users/s/Documents/Python/frnm/oud/app.py`
- `/Users/s/Documents/Python/frnm/cli.py` -> `/Users/s/Documents/Python/frnm/oud/cli.py`
