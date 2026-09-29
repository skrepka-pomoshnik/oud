# Editor UI fix plan

Status: active. Findings come from the 2026-09-27 UI audit: a code review of
`oud/editor`, `oud/presentation` and the Petrucci status/help renderers, plus
live tmux sessions at 80x24, 100x30 and 120x40. `TODO.md` tracks the phases;
this document holds the evidence and acceptance criteria.

The score viewer is mature because it renders the canonical Petrucci score.
Editing is not: it runs on a legacy grid model, with modal input and screen
chrome that grew by accretion. Phases are ordered by dependency. Each item is
done when its acceptance criterion has a regression test and the common gate
passes.

## Root causes

1. **Editing used a second score model.** The viewer renders `NotationScore`.
   The editor mutated `Piece.bars[].chords` plus sparse grid maps (`overrides`,
   `durations`, `dotted`, `slurs`, `ties`, `holds`, `glisses`) keyed by
   `(bar, string, col)` on a fixed `bar_width` grid, and the first edit in an
   imported bar flattened its chords into the grid. Since `C3` (2026-09-29)
   every typing edit goes through the chord transaction at exact onsets and the
   cursor is an onset. What remains: the grid maps are still read by about 40
   modules (`C4`), and slurs, ties, holds and ornaments still live in editor
   state instead of the model (`C17`).
2. **Petrucci owns editor chrome.** `render_piece` takes about 40 arguments,
   including `cmdline`, `searchline`, plugin rows and mode strings. Petrucci
   builds the status line (`rendering/system/status.py`) and owns the help text.
3. **Modes, keys and state are loosely typed.** Modes are bare strings. Keys are
   tuples spread across about ten binding records, and the `g`/`d`/`y` prefixes
   are hard-coded, so help cannot be generated and drifts from behaviour. The
   settings dict mixes user preferences, document properties and runtime paths.
4. **Commands pass through wrapper layers.** Most commands go through
   `tui/commands.py`, then `commands/dispatch.py`, then `handlers/*`, and every
   layer re-declares the handler.

## Phase 1: reproduced bugs

- [x] **Insert-mode `q` quits.** `q`/`Q` were bound to quit in insert mode, so
  French fret `q` (15) quit the editor. `r` always meant a rest, so fret `r`
  (16) was unreachable.
  Accept: in insert mode only Ctrl-C quits; `q` and `r` insert French frets; `z`
  inserts a rest in both styles.
- [x] **`:set` is disabled in the read-only viewer.** This blocked
  `:set scoreview=staff`, `lyricmode` and `showlyrics`, which the help
  advertises for the viewer, while `:dark` and `:hide` still worked.
  Accept: display settings apply in read-only scores; document settings (style,
  strings, tuning, time, key, tempo, bass courses, metadata, presets) report a
  precise read-only diagnostic.
- [x] **`:set` rewrites the whole settings dict into `./config.toml`.** This
  includes the open file's path, tuning, meter and tempo. Any `config.toml` in
  the working directory, even another tool's file, was read and overwritten.
  Exports and `:play` rewrote the file too.
  Accept: only changed preference keys persist. Document and runtime keys stay
  in the session. A missing config is created under
  `$XDG_CONFIG_HOME/oud/` (default `~/.config/oud/`), never in the working
  directory. A working-directory `config.toml` is used only when it has a
  `[settings]` table. A file with other top-level tables is never rewritten.
  Exports and playback persist nothing.
- [x] **Esc takes about one second.** curses kept the default escape delay.
  Accept: the TUI sets a 25 ms escape delay unless the user set `ESCDELAY`.
- [x] **No-op edits mark the buffer modified.** `x` on an empty cell set
  `modified` with nothing to undo.
  Accept: a clear that changes nothing leaves `modified` and the undo stack
  unchanged.
- [x] **`gj` adds a bass course without undo.**
  Accept: undo restores the course count and tuning; redo reapplies them.
- [x] **Save As keeps showing the old name.** After `:w other.tab` on a native
  TAB, the status line still showed the source name while the write target
  moved.
  Accept: the status name follows the established write target of native
  documents.
- [x] **Visual mode reports itself twice** (`visual  VISUAL`).
  Accept: the mode is shown once.
- [x] **Help and docs drift from behaviour.**
  - French durations are `1..7` = 1, 2, 4, 8, 16, 32, 64, not `1 2 4 8 6 3`.
  - Italian "Ctrl+1..7" were really raw Ctrl-A..Ctrl-G bytes, and Ctrl-C
    collided with quit. `;1..;7` is the only Italian duration path.
  - `f`/`F` were documented as flag style and "letters"; they are find-char.
  - `/` goes to a bar number; it is not a search.
  - README and the guide documented `spacingmode`/`spacingfill`, which do not
    exist; the keys are `layout` and `justify`.

  Accept: help is generated from the action table (Phase 2), and README, the
  user guide and the man page name only existing keys and settings.
- [x] **Rests were written as notes.** The grid stored a rest as the override
  `r`. TAB export wrote it as fret `r`, and MIDI played it as fret 16.
  Accept: rests use the non-fret marker `_`. TAB export writes a flag-only line,
  and playback advances time over the rest.
- [x] **Replace mode stole fret letters.** In `R` mode, `h`/`k`/`l` (vim) and
  `a`/`d`/`w`/`s` (casual) moved the cursor, so those frets could not be typed.
  Accept: replace mode moves only with arrows, like insert mode.
- [x] **TAB import dropped flag-only rest lines.** Real TAB files (for example
  `examples/si_par_souffrir.tab`) encode rests as a bare rhythm flag. The
  importer discarded them, which shifted later onsets and lost the rests Oud
  writes. Layout helpers also filtered out chords without notes.
  Accept: flag-only lines import as rest chords that keep their time in layout
  and playback. The rest's flag is always drawn over an empty column, never
  hidden as redundant, and TAB rests survive save and reopen.
- [x] **Ctrl-C discarded unsaved edits.** In the real TUI, Ctrl-C arrived as
  SIGINT and exited with status 130, so the key-code-3 bindings were
  unreachable and running playback was not stopped.
  Accept: while waiting for keys, SIGINT is delivered as the Ctrl-C key, which
  follows the `q` rules: it asks once with unsaved changes. It cancels prompts,
  and closes pages and the plugin browser. Every loop exit, `:q` included,
  stops playback, and stopping reaps the player with a bounded wait before
  killing it.
- [x] **Empty bars were dropped on reopen.** A new score's empty bars were
  written as `b`/`Sc` blocks, but the importer discarded chord-less bars.
  Decision: a bar with chords or an explicit line (Oud writes `S…` in every bar)
  is a measure and is kept. Bare `b` lines alone remain barline layout, so
  hand-written files gain no spurious bars; repo TAB bar counts are unchanged.

## Phase 2: one action table

- [x] Add a `Mode` enum and use it at every mode transition.
- [x] Add a declarative table mapping (mode, key style, arrows) to key
  sequences and action IDs. Each action carries a help text, a group and a
  `mutates` flag. Multi-key sequences (`gg`, `dd`, `yy`) and character-argument
  actions (`f{c}`, `m{c}`) use one generic pending-sequence mechanism. The
  `pending_key`, `pending_find` and `pending_mark` special cases go away.
- [x] Enforce read-only in one place: the dispatcher refuses actions with
  `mutates=True` and reports `READ_ONLY_VIEWER`.
- [x] Generate the key sections of the in-app help and `:help` pager from the
  table for the active key style. Oud owns the help text; Petrucci only paints
  the page lines it receives.
- [x] Delete the unreachable `remap_*` plumbing. Those keys could never be
  loaded from the config or set with `:set`. Configurable keys return later as
  an explicit `[keys]` table built on action IDs.
- [x] Declare the command/search prompt, help/info/notes page and plugin browser
  bindings in the same table. The line editor and menu helper take their keys
  from it, and help lists every mode.
- [x] Resolve the key collisions:
  - `[`/`]` only jump sections or pages (read-only scores). Casual find repeat
    is `;`. Reverse repeat is vim grammar (`,`), like `dd`.
  - `P` pastes bars before (like `o`/`O`). PDF builds only via `:pdf`, so a
    stray key cannot start LilyPond.
  - `gb` adds a bass course; `gj` is free again.

  Deliberate exceptions, each described in the generated help:
  - `J`/`K` move a rendered row; in a viewer the cursor is fixed, so the same
    "next system" scrolls.
  - `j`/`k` move a course; a viewer has no courses, so they move staff focus.
  - `Enter` enters insert mode and `I` opens info. Oud has no text lines, so
    vim's line meanings do not apply.
  - `M` toggles playback; it has no side effects beyond sound.

## Phase 3: editor chrome out of Petrucci

- [x] Add an Oud `StatusModel`: identity, position, mode, pending keys and
  count, message and level. It renders into fixed segments so the line does not
  jump, and it truncates by priority at 80 columns.
  Done: `oud/editor/services/screen/status.py`. Identity and position start at
  the left edge; pending keys, duration, and mode end at the right edge; the
  message sits between. Too-narrow rows drop identity, duration, pending keys,
  meter, and position in that order, then cut the message; the mode stays.
- [x] Replace the cryptic `M` meter marker with a named diagnostic segment
  (`meter 5/6`) and show it only in normal mode.
  Done as `meter:<length> of <meter>` (`meter:1/2 of 3/4`); it shows in every
  mode of the tablature view, not only in normal mode.
- [x] Show one position vocabulary across TAB and FT3 projections (`beat`, not
  `col`). `beat:k/n`, or `ev:k/n` for a meter with no beat structure.
- [x] Scroll the command prompt horizontally so a long prefilled Save As path
  stays editable at 80 columns. The prompt shows `<` and its end.
- [x] Move status, prompt, info, notes, plugin and help rendering out of
  `petrucci/rendering/api.py`. Petrucci returns the score frame only, and
  `render_piece` loses its editor-only arguments.
  Done: `oud/editor/services/screen` composes every frame. All 441 frames of a
  baseline (7 documents, 21 modes and states, 3 sizes) are identical in text,
  attributes, playback cache, and cursor maps.
- [x] Choose one help surface. The in-app overlay and the `less` pager show
  identical generated content (a test locks it for every key style).

## Phase 4: edit on onsets through the canonical model

- [x] The cursor becomes (bar, exact onset `Fraction`, course), with an
  explicit append slot. `l`/`h` step between onsets, not justified filler
  cells. The status beat comes from the onset and the bar's own meter.
  Done: `EditorState.cursor_onset`; `cursor_col` is derived. The renderer takes
  `cursor_event`, so dense bars (16ths, 32nds) are drawn exactly.
- [x] Route all insert, replace, delete, rest, dot and duration edits through
  `TabEditTransaction` / `apply_note_input`. The French letter path currently
  bypasses it; only Italian multi-fret uses it.
  Done: `oud/editor/editing/tab/typing.py`; `x` and visual delete too.
- [ ] Delete `_flatten_chords_to_grid`, the `overrides`/`durations`/`dotted`
  grid maps and float rhythm. Rhythm checks use `Fraction` and per-bar meters,
  including meter changes.
  Progress: `_flatten_chords_to_grid` and the float rhythm primitives are gone;
  the grid maps remain for readers until `C4`.
- [ ] Replace untyped `UndoAction(kind: str, data: dict)` with typed
  transaction records.
- [x] Make TAB save idempotent against its source: unchanged bars must not gain
  a repeated `S6/4` per system. Meter lines are written on the first bar, on a
  change, and on empty bars; every repo TAB file saves byte-identically after
  the first save.

## Phase 5: commands and state

- [ ] Replace the three command layers with one `CommandSpec` registry:
  handler, argument spec, read-only policy, completion and help line.
- [ ] Split `EditorState.settings` into typed user preferences, document
  properties and runtime state. `:set` routes to exactly one of them.
- [ ] Break `EditorState` into view, input-session, document and media records.

## Viewer notes (lower priority)

- [ ] At 120x40 in *Felice fu quel dì*, lute and soprano bars do not share
  horizontal bar positions within a system.
- [x] The `lute` staff label overwrites the start of the tablature staff.
- [x] The status line says `focus:Tab` while the staff label reads `lute`.
