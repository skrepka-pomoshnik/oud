# OUD Docs

This document describes the current feature set, common use cases, and day-to-day usage.

## 1) What OUD Is

`oud` is a terminal (curses) editor for lute tablature with:

- Vim-like editing model (`normal` / `insert` / `command` / `search`).
- TAB and FT3 import.
- TAB and ASCII export.
- MIDI and LilyPond export.
- Vocal note-staff and lyric rendering for supported FT3 text records.
- Partial mixed-score FT3 import layer for non-tab note/barline/text staves.
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
- `:wa [path]` / `:wascii [path]` write ASCII snapshot/export
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
- `:pause` stop active playback
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
- Rendering presets/cues: `tabnotation`, `timesigstyle`
- Notation/meta: `style`, `strings`, `time`, `key`, `measures`, `measuresstep`, `countdots`
- Tuning/view: `tuning`, `bassstrings`, `basslabels`, `showtuning`, `tuninglabels`, `italianorient`, `italianmultifret`, `viewinvert`, `frenchc`
- Playback: `soundfont`, `midipatch`, `midigate`, `tempo`
- Input profile: `keys`

Notes:
- `barsperline=0` means auto.
- `barpad` controls left/right inner padding inside bars.

## 7.1 Tonality and Accidentals

Tonal accidentals are centralized in [oud/core/key_signature.py](oud/core/key_signature.py).

- `normalize_key_signature_name()` accepts `GM`, `Dm`, `Bb major`, `f# minor`
- `key_signature_count()` returns the standard circle-of-fifths count
- `key_signature_accidentals()` returns the altered pitch classes for that tonality

Examples:

- `GM` -> `{"f": "#"}`
- `DM` -> `{"f": "#", "c": "#"}`
- `Fm` -> `{"b": "b", "e": "b", "a": "b", "d": "b"}`

This should be the single source of truth for tonal default accidentals in FT3 vocal parsing and future import/export paths.

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
- All bundled mixed/non-tab FT3 files have usable read-only views; unconfirmed proprietary notation details may still be omitted.
- Horizontal fit is actively tuned; some edge spacing/render scenarios are still under refinement.

## 12) Status and Info Split

- Main status bar keeps live editing context only (bar/beat, duration, time).
- Path/file metadata is intentionally moved to `:info` to keep editing status compact.
- Import warnings remain listed in `:info` after their transient status message fades.

## 11) Architecture Map

- `oud/petrucci/`: canonical score model, spacing policies, framebuffer, and tab/note renderer.
- `oud/core/`: file parsers and format-specific import semantics.
- `oud/editor/`: state + editing ops + command ops + undo/redo.
- `oud/tui/`: input/prompt/controller/main loop.
- `oud/ui/`: curses adapter plus compatibility paths for the former renderer modules.
- `oud/exports/`: TAB/LilyPond/MIDI exporters.
- `oud/plugins/`: plugin implementations.

Entry points:

- `app.py` -> `oud/app.py`
- `cli.py` -> `oud/cli.py`

## 12) FT3 Import Layer (Current)

FT3 import now has two layers:

- `Piece.bars`: the editable tablature projection used by the editor/TUI.
- `Piece.imported_score`: a read-oriented import layer for structured/non-tab FT3 content.

`imported_score` currently stores:

- `note` staffs from structured vocal rows and decoded `note-staff-raw` / `note-lyric-raw` bars
- `lyrics` staffs from structured lyric rows and decoded `note-lyric-raw` bars
- `comment` staffs from editorial FT3 text rows
- `barline` staffs from `barline-raw`
- `layout` staffs from non-musical score-settings records
- `unknown` only for future records that cannot be classified safely

This keeps represented FT3 material out of generic unknown blobs and drives the read-only mixed-score view. The bundled corpus currently produces no unknown staffs or import warnings.

## 13) Rendering Notes

- Lower vocal note staff now sits directly under the tablature staff; the extra spacer row was removed from bottom vocal layout.
- Melody playback redraw is event-driven, so the TUI no longer repaints the full frame on idle playback ticks.
- `^` playback marker remains visible even when melody rows are shown.

## 14) LilyPond Parity Audit (Current)

This is a practical parity tracker for LilyPond `TabStaff`-style features in the TUI/ASCII renderer.
Status values:

- `done`: implemented and covered by tests
- `partial`: usable, but missing options/edge cases
- `missing`: not implemented yet

| Feature area | Status | Notes | Tests | Acceptance examples (synthetic) |
|---|---|---|---|---|
| Tab notation preset bundle (`tabFullNotation`-like) | partial | `:set tabnotation=minimal|full` toggles coherent display bundle; synthetic regressions cover preset reapply behavior, flagstyle matrix, visible rest markers, and compact tuplet cue visibility under full notation. Richer tuplet/rest semantics still incomplete | `tests/test_tab_policy.py`, `tests/test_tui_commands_exec.py`, `tests/test_tab_parity_snippets.py` | `test_tab_snippet_tab_full_notation_preset_bundle`, `test_tab_snippet_tab_full_notation_keeps_rest_marker_visible`, `test_tab_snippet_tab_full_notation_shows_tuplet_cue` |
| Time-signature cue style (`C/O` vs numeric/fraction) | done | `:set timesigstyle=symbol|numeric|fraction`, in-staff cue shown at system start and meter changes | `tests/test_tab_policy.py`, `tests/test_ui_render_split.py`, `tests/test_tab_parity_snippets.py` | `test_tab_snippet_mid_system_meter_change_cue_fraction_style`, `test_tab_snippet_time_cue_dense_auftact_no_glue_c_o_3` |
| Tablature fret-label formatting policy split | done | formatter extracted into policy (`tab_policy.fret_label`) and reused by renderer | `tests/test_tab_policy.py` | `test_fret_label_french_and_italian`, `test_fret_label_french_alt_c` |
| String-row labels / bass-row visibility policy | partial | centralized policy for row ordering and per-system used-bass-row display; richer label policies still pending | `tests/test_tab_policy.py`, `tests/test_ui_render.py` | `test_system_display_indices_for_bars_hides_unused_bass_rows` |
| Stem/beam rendering in tab rows | partial | multiple flag styles (`standard`, `board`, `englishgrid`, `continental`, etc.) exist; alignment and collision regressions covered, but beamify/partials remain pending | `tests/test_tab_parity_snippets.py`, `tests/test_render_alignment_invariants.py`, `tests/test_render_matrix.py` | `test_tab_snippet_stem_beam_behavior_in_tablature_full_mode`, `test_tab_snippet_tab_full_notation_flagstyle_matrix_renders` |
| Ties/slurs/holds cue rows | partial | span rows render and align; configurable cue styles (`tiecuestyle`, `slurcuestyle`, `holdcuestyle`, `glisscuestyle`) exist. Continued tied-note noteheads support `show|hide|parenthesize` (`tienoteheads`) via fixed-width cue proxies (`(` / `)`) with shared-row collision precedence (parenthesize cues survive against tie/slur/hold/gliss span glyphs); system-break regressions and dense collision regressions exist. Richer follow semantics remain pending | `tests/test_tab_parity_snippets.py`, `tests/test_render.py`, `tests/test_tab_policy.py`, `tests/test_tui_commands_exec.py` | `test_tab_snippet_tie_followed_by_gliss_cues_survive_system_break_collisions`, `test_tab_snippet_slur_gliss_parenthesize_collision_regression_with_system_breaks` |
| Gliss/slides/harmonics | partial | configurable gliss cue row style (`glisscuestyle`) and shared-row cue collision precedence exist, with synthetic dense/system-break regressions that also preserve staff fret glyphs under cue pressure; true gliss/harmonic semantics and dedicated glyph rules are still incomplete | `tests/test_tab_parity_snippets.py`, `tests/test_render.py`, `tests/test_tab_policy.py`, `tests/test_tui_commands_exec.py` | `test_tab_snippet_slur_gliss_parenthesize_cues_do_not_clobber_dense_frets`, `test_build_bar_view_gliss_cue_style_variants_and_tie_parenthesize_fallback` |
| Repeats/barlines | partial | repeat markers/barline types are editable and render in score; synthetic parity snippets cover basic repeat glyphs, double barline rendering, and a small repeat/barline variant matrix | `tests/test_editor_commands.py`, `tests/test_ui_render.py`, `tests/test_tab_parity_snippets.py` | `test_tab_snippet_repeats_and_double_barline_render_without_breaking_staff`, `test_tab_snippet_repeat_and_barline_variant_matrix_renders` |
| FT3 -> LilyPond/PDF supported subset | done | exporter handles tab, vocal-only, mixed vocal+lute, raw note-staff, sparse lyric, and barline-only imports; preserves repeats, meter/key changes, system breaks, rests/accidentals, and supported FT3 extras. Unknown proprietary semantics remain out of scope rather than guessed | `tests/test_alpha_viewer.py`, `tests/test_lilypond.py`, `tests/test_tui_commands_exec.py` | `test_local_ft3_corpus_exports_to_lilypond`, `test_export_lilypond_aligns_sparse_imported_lyrics_by_source_bar`, `test_export_lilypond_emits_barline_only_imported_score` |
| Polyphonic TabVoice behavior | missing | no independent voice model/collision precedence yet | TODO `P3 LilyPond parity: polyphonic TabVoice behavior...` | n/a |
| Assignment constraints (`minimumFret`, stretch, forced string) | partial | pure assignment-policy module exists with diagnostics/tests; partially reused by temporary preset converter fallback; not yet wired into general edit/engrave placement paths | `tests/test_tab_assign_policy.py`, `tests/test_tui_commands_exec.py` | `test_assign_chord_pitches_max_stretch_constraint`, `test_cmd_set_guitar_partial_convert_negative_shift_uses_target_tuning_for_next_course` |

## 15) Petrucci Embedding API

`oud.petrucci` can typeset a score without constructing an editor or curses
window. `typeset_text(...)` returns clean terminal text; `typeset_piece(...)`
returns a `TypesetResult` containing the fixed-size `Frame` and cursor display
maps. `TypesetOptions` controls viewport size, bar width, settings, cursor, and
whether an editor-like status row is included.

The package is the authoritative implementation home for:

- score, bar, chord, note, melody, and lyric event dataclasses
- French/Italian tablature labels and notation policies
- rhythm flags, spacing, system packing, and text-lane layout
- tablature, vocal/lyric, and pitched note-staff character-cell rendering
- framebuffer snapshots and style attributes

Old `oud.core.*` model/render utility paths and `oud.ui.*` renderer paths are
module aliases to Petrucci for compatibility; new integrations should import
from `oud.petrucci`.
