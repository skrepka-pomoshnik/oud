# OUD Docs

This document describes the current feature set, common use cases, and day-to-day usage.

## 1) What OUD Is

`oud` is a terminal (curses) editor for lute tablature with:

- Vim-like editing model (`normal` / `insert` / `command` / `search`).
- TAB and FT3 import.
- TAB and ASCII export.
- MIDI and LilyPond export.
- Vocal note-staff and lyric rendering for supported FT3 text records.
- Read-only mixed and polyphonic FT3 import with per-staff focus.
- Minimal dependency runtime.

## 2) Run and Open Files

Run from project root:

```bash
python3 -m oud.presentation.app
python3 -m oud.presentation.app examples/triste.tab
```

From a checkout:

```bash
uv run oud
uv run oud examples/triste.tab
```

Non-interactive commands use stdout for primary output and stderr for
diagnostics. Existing output files are refused unless `-f` is explicit:

```bash
uv run oud ascii score.ft3 --bars 1:8
uv run oud convert score.ft3 score.musicxml
uv run oud convert score.ft3 score.pdf
printf '%s\n' '-C' 'b' '0a-----' 'e' \
  | uv run oud convert - - --input-format tab --format lilypond
```

`-` supports TAB input and TAB, ASCII, LilyPond, or MusicXML output. Binary MXL,
MIDI, and PDF output requires a path. PDF conversion writes the companion `.ly`
atomically and preserves it when compilation fails.

## 3) Modes

- `normal`: navigation + editor commands.
- `insert`: write frets/rests/durations.
- `:` command prompt: ex-like commands.
- `/` go-to-bar prompt: type a 1-based bar number and press Enter.
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
- Bar add/remove: `o O` and `+ -`; copy `yy`, paste after/before `p` / `P`
- Add a configured bass course: `gb` (undoable)
- Help: `F1` / `gh` (page) or `?` (in less); both show the same text, generated for the active key profile
- Command: `:`
- Go to bar: `/` then a bar number
- Read-only score viewport: `K` / `J` move one system and `[` / `]` jump to the previous/next section or source page without moving the logical cursor. `PgUp` / `PgDn` scroll whole viewport pages.

Normal-mode numeric prefixes are limited to 999 with a visible notice. Counted
movement stops at score boundaries, and movement in a read-only viewer never
creates a new bar.

### Vim parity currently implemented

- Char find: `f F t T`, repeat `;` and reverse `,`
- Word search: `*` / `#`, repeat `n` / `N`
- Match jump: `%`
- Marks: `m{char}`, jump with `' {char}` / `` ` {char}``

### Casual profile (core)

- Move: arrows or `w a s d`
- Row jump: `W` / `S` (previous/next rendered row; viewport-only in read-only scores)
- Bar step: `,` / `.`
- Bar edge: `Home` / `End`; viewport scroll: `PgUp` / `PgDn`
- Insert/delete bar: `Insert` / `Delete`
- Undo/redo: `Ctrl-Z` / `Ctrl-Y` (`u` / `Ctrl-R` remain available)
- Char-find repeat: `;` forward. Reverse repeat is vim-only (`,`), like `dd`; in casual keys `,`/`.` step bars and `[`/`]` jump sections/pages in read-only scores
- Help: `F1`

## 5) Entering Notes

The cursor rests on an event of the bar (a chord, a single note, or a rest) or
on the bar's append slot after its last event. A bar that already fills its
meter has no append slot. `h`/`l` step one event, however densely the bar is
drawn, so a bar of sixteenths or thirty-seconds is visited event by event.

In insert mode:

- A fret on the append slot adds an event with the current duration; if it would
  not fit in the bar's meter, it goes to the next bar. The cursor moves on.
- A fret on an event sets that course's note and keeps the event's duration and
  the other courses. To build a chord, step back onto the event (`h` or an arrow)
  and type on another course.
- `z` adds a rest, or turns the event under the cursor into a rest.
- A duration key or `.` changes the event under the cursor, or the event just
  typed when the cursor is on the append slot, and becomes the current duration.
- `x`, `Space`, `Backspace` and `Delete` remove the course's note; an event left
  without notes, or a rest, is removed and later events move earlier.
- `R` (replace mode) changes existing notes only and does not move.

Every keystroke that edits is one undo step. The status row shows the bar, the
beat from the event's onset and the bar's own meter, and `len:` with the duration
of the event under the cursor (the current typing duration on the append slot).

## 5.1 French tablature

- Frets by letters (`a..`), with historical mapping rules.
- Bass shorthand in insert mode: `/a`, `//a`, `///a` (configured bass availability applies).
- Rest in insert mode: `z` (both styles). Every letter `a`..`t` except `j` is a French fret, including `q` and `r`.
- Only `Ctrl-C` quits from insert mode; `Esc` returns to normal mode.

`Ctrl-C` follows `q` everywhere: with unsaved changes it asks once and quits on
the second press. It cancels the command, go-to-bar and plugin-search prompts
and closes help, info, notes and plugin pages. Every exit stops playback.

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

Italian mode keeps numeric fret entry; type `;` then `1`..`7` to set a duration.

Durations belong to events and are rendered according to the current flag style and redundancy settings.

## 6) Core Commands

## 6.1 File and session

- `:e <path>` open file
- `:w [path]` save; the extension picks the format: `.musicxml`/`.xml` (the default) or `.tab` (the original `tab` program's format, see `docs/tab-format.md`). New and imported documents prompt for a destination: `untitled.musicxml` for a new document, the source name with `.musicxml` for FT3 or TAB, and `name.oud.musicxml` for MusicXML that Oud did not write, so that file is never overwritten by default. `oud new.musicxml` or `oud new.tab` on a missing file pre-fills that name. Nothing is written until you confirm. MusicXML that Oud wrote reopens as a native document and `:w` saves back to it; `.tab` documents keep saving to their `.tab`.
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
- Playback follows the active score system by default; `:set playbackscroll=off` keeps the viewport fixed.
- `:lilypond [path]` export LilyPond
- `:pdf` compile PDF from LilyPond

## 6.5 Helpers

- `:source [path]` view source in `less`
- `:plugins` open plugin list
- `:info` show current file/settings page

## 7) Settings (`:set`)

`key=value` tokens can be chained in one command:

```text
:set style=french layout=auto justify=compact
```

### Persistence and read-only scores

Preference keys are saved to `$XDG_CONFIG_HOME/oud/config.toml` (default
`~/.config/oud/config.toml`). A `config.toml` in the working directory is used
instead only when it already contains a `[settings]` table. Only keys changed by
the command are written, and the file is replaced atomically. Oud refuses to
rewrite a config file containing other tables and reports "Settings applied but
not saved".

Document properties (`style`, `strings`, `tuning`, `time`, `key`, `tempo`,
`bassstrings`) change the open score for this session only. Edit them in the
config file to change new-document defaults. Exports and `:play` never write
settings.

Read-only scores accept display settings (`scoreview`, `showlyrics`,
`lyricmode`, `theme`, …). Document properties, metadata keys and the
`lute`/`guitar` presets are refused with a read-only diagnostic.

### Commonly used keys

- Layout: `spacing`, `layout`, `justify`, `barsperline`, `maxbars`, `maxchords`, `bargap`, `linelen`
- Rendering: `flagstyle`, `flagstems`, `flagredundant`, `showdur`, `showextras`, `showtactus`, `grid`
- Vocal display: `showmelody`, `showlyrics`, `lyricmode=first|current|all`, `lyricverse=N`, `vocalpos`
- Rendering presets/cues: `tabnotation`, `timesigstyle`, `scoreview=score|staff`
- Publication: `lilypond`, `lilypondversion=2.26|2.24`, `lyprofile=petrucci|classic`, `lynoteheads=classic|petrucci`, `lybarsperline`, `lysystemsperpage`, `lytabrhythm=minimal|full`, `lypapersize=letter|a4`, `lysourceheading=on|off`
- Notation/meta: `style`, `strings`, `time`, `key`, `measures`, `measuresstep`, `countdots`
- Tuning/view: `tuning`, `bassstrings`, `basslabels`, `showtuning`, `tuninglabels`, `italianorient`, `italianmultifret`, `viewinvert`, `frenchc`
- Playback: `soundfont`, `midipatch`, `midigate`, `tempo`, `playbackscroll`, `playverses`
- Input profile: `keys`

Notes:
- `barsperline=0` means auto.
- `lybarsperline=0` and `lysystemsperpage=0` use the publication planner. Dense
  multi-stanza scores default to four bars per system and two systems per page;
  positive values force explicit LilyPond limits.
- `barpad` controls left/right inner padding inside bars.
- `measures=system` labels the first bar of each displayed system; `every` uses `measuresstep`.
- `showlyrics=off` hides lyrics. `lyricmode=first` is the compact default; `current` displays the
  1-based stanza selected by `lyricverse`, while `all` displays every stanza.
- `scoreview=score` keeps every mapped notation and tablature staff in one layout; `j`/`k` moves the
  vertical focus through a tall score without moving the logical score cursor. `scoreview=staff`
  renders only the focused staff for compact reading.

## 7.1 Tonality and Accidentals

Tonal accidentals are centralized in [oud/importers/key_signature.py](oud/importers/key_signature.py).

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
  - `h` back, `q` / `b` / `Esc` / `Ctrl-C` close (or go up a level)
  - `d` download, `D` download a folder recursively
  - `/` search; `Enter` jumps to the match, `Esc` / `Ctrl-C` cancel
  - `gg` / `G` top/end, `?` plugin help

## 9) Typical Workflows

## 9.1 Edit a TAB or tab-only FT3 projection, export PDF

1. Open: `:e file.ft3`
2. Check the persistent document label. `FT3 EDIT:name.musicxml` is an editable projection with its suggested save target. FT3 scores with notation staffs (voices, lyrics) are editable too: you edit the tablature, bar inserts and deletes keep the other staffs aligned, and `:w name.musicxml` saves the tablature and the notation staffs (pitch, rhythm, rests, ties, lyrics; FT3 comment and layout rows stay in the source). Saving such a score to `.tab` is refused until `C15` adds a sidecar. `FT3 VIEW` (read-only) remains for duet scores, which keep two lute parts in one bar list, and for scores without tablature.
3. Edit in `insert` mode (`i`).
4. Check bar rhythm: `:verify`.
5. Save with `:w`; imported files prompt for a destination (MusicXML by default, or `.tab`) and leave the FT3 source unchanged.
6. Export LilyPond with `:lilypond out.ly` or build PDF with `:pdf`.

## 9.2 Fast TAB cleanup and reflow

1. Open file
2. Run `:tool comments`
3. Adjust wrap/settings with `:set layout=auto ...`
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
- FT3/JT* are proprietary import formats; support is validated against fixed external manifests rather than every historical producer version.
- The focused regression manifest and both fixed 75-file samples pass the unresolved-semantics audit without warnings (150 fixed external files total). This is not general FT3 or Fronimo parity; exact source engraving coordinates are reflowed.
- FT3 is import-only. Tab-only FT3 files expose an editable TAB projection; mixed, vocal, and duet scores are read-only until every visible layer can round-trip.
- The status line always distinguishes the source document from its confirmed TAB write target.
- Auto layout applies collision widths before justifying, keeps final/manual/capped systems at readable natural widths, and shows a clipped preview only when at least half of the next system fits.

## 12) Status and Info Split

- Main status bar keeps the short filename, modified marker, document/write mode, cursor location, and editing mode visible.
- `:info` retains full source and write-target paths plus detailed file metadata.
- For FT3 imports, `:info` also lists source format/page metadata and every imported staff; `:notes` includes editorial comments from non-focused staffs.
- Import warnings remain listed in `:info` after their transient status message fades.
- Important import and document notices remain in the status area until `:ack`; the document classification itself is always visible.
- In read-only mixed and duet scores, `j/k` (or `w/s` with casual keys) cycles the visible staff focus shown in the status line.

## 11) Architecture Map

- `petrucci/`: canonical score model, spacing policies, framebuffer, and tab/note renderer.
- `oud/importers/`: file parsers and format-specific import semantics.
- `oud/editor/`: layered editor domains; see `docs/editor-architecture.md`.
- `oud/presentation/tui/`: input/prompt/controller/main loop.
- `oud/presentation/ui/`: curses adapter.
- `oud/exports/`: TAB/LilyPond/MIDI exporters.
- `oud/services/plugins/`: plugin implementations.

Entry point: `oud` -> `oud.presentation.app:main`.

## 12) FT3 Import Layer (Current)

FT3 import now has two layers:

- `Piece.bars`: the editable tablature projection used by the editor/TUI.
- `Piece.imported_score`: a read-oriented import layer for structured/non-tab FT3 content.

`imported_score` stores semantic `note`, `lyrics`, `comment`, and `layout` staffs.
Typed source provenance (`note`, `note-lyrics`, `annotation-group`, and
`score-terminator`) is recorded once in `source_records`, separately from the
musical bars. Future unclassified records use `unknown` and fail the FT3 audit.

The read-only vocal-only viewer renders every mapped note staff in one compact
canonical score. The current `j`/`k` focus selects the voice used for cursor and
playback tracking without hiding the other voices. If the complete system is
taller than the terminal, rendering clips cleanly at the lower content border.
Compact score view omits repeated per-staff measure numbers and stems by default;
`:set showdur=on` restores stems when rhythmic detail is preferred over density.
Five-line spacing remains pitch-correct. Short terminals scroll within a system
to keep the focused voice complete and suppress partial neighboring staffs.
Playback marks the active note with `^`; vocal-only polyphony sends every mapped
voice to a separate MIDI channel while focus controls the tracked cursor.
Mixed scores retain focused tab/note/lyric views. LilyPond exports every mapped
voice. The bundled corpus produces no unknown staffs or import warnings.

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
| FT3 -> LilyPond/PDF supported corpus | done | exporter handles tab, vocal-only, mixed vocal+lute, and polyphonic note staffs; preserves repeats/endings, meter/key changes, explicit sections/pages, rests, accidentals, beams, fermatas, and decoded FT3 extras | `tests/test_alpha_viewer.py`, `tests/test_lilypond_vocal.py`, `tests/test_tui_commands_media.py` | `test_local_ft3_corpus_exports_to_lilypond`, `test_export_lilypond_emits_every_imported_polyphonic_staff`, `test_export_lilypond_preserves_imported_beams_and_fermata` |
| Polyphonic TabVoice behavior | missing | no independent voice model/collision precedence yet | TODO `P3 LilyPond parity: polyphonic TabVoice behavior...` | n/a |
| Assignment constraints (`minimumFret`, stretch, forced string) | partial | pure assignment-policy module exists with diagnostics/tests; partially reused by temporary preset converter fallback; not yet wired into general edit/engrave placement paths | `tests/test_tab_assign_policy.py`, `tests/test_tui_commands_exec.py` | `test_assign_chord_pitches_max_stretch_constraint`, `test_cmd_set_guitar_reassigns_removed_bass_course_under_target_tuning` |

## 15) Petrucci Embedding API

Petrucci has two entry paths:

- `typeset_piece(...)` preserves Oud tablature behavior.
- `typeset_score(...)` renders source-independent immutable notation records.
- `apply_note_input(...)` applies an atomic, source-independent note transaction.
- `apply_tab_mutation(...)` applies an atomic tablature transaction at exact onsets.

The canonical score result contains text, `ScoreLayout`, structural roles,
source IDs, `cells_for(id)`, and indexed `cells_for_many(ids)`. Consumers own selection, playback, grading,
colors, and terminal attributes; Petrucci does not expose result-state enums or
interpret caller state.

`NoteInputTransaction` supports notes, rests, chords, voices, persistent dotted
or tuplet durations, grace style, repitching, replacement, deletion, ties,
slurs, and lyrics. It returns a new immutable score, updated typing context, and
typed changes. Rejections carry a stable `NoteInputError.code`; the source score
is unchanged. This API imports no Oud editor, FT3, curses, or file-I/O module.

```python
from fractions import Fraction

from petrucci import (
    EventKind,
    GlyphMode,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    ScoreTypesetOptions,
    pitch_from_midi,
    typeset_score,
)

note = NotationEvent(
    "voice:bar:1:note:1",
    Fraction(0),
    Fraction(1, 4),
    EventKind.NOTE,
    (pitch_from_midi(60),),
)
score = NotationScore(
    "example",
    (NotationStaff("voice", (NotationMeasure("bar:1", 1, (note,)),)),),
)
result = typeset_score(
    score,
    options=ScoreTypesetOptions(width=80, height=24, glyph_mode=GlyphMode.SAFE),
)
for row, column in result.cells_for(note.id):
    pass  # apply caller-owned attributes here
```

Timed consumers can use `FlowEvent`. Timing is exact; events crossing a measure
are split and tied while `notation_ids_for(source_id)` retains source identity.

Use `layout_score(...)` once per score, layout width, metrics, and policy.
`typeset_layout(...)` repaints that immutable layout. For a moving horizontal
view, choose a wide `layout_width`, a narrower `width`, and update only
`x_offset`:

```python
from petrucci import ScoreTypesetOptions, typeset_layout

options = ScoreTypesetOptions(
    width=40,
    height=18,
    layout_width=160,
    x_offset=60,
)
frame = typeset_layout(layout, options=options)
```

`system_offset` selects the first vertically visible system. `EventLocation`,
`OnsetPosition`, clipping metadata, structural roles, and translated cell IDs
remain available without parsing glyph text. Pretty and safe modes preserve the
same identities and roles.

Use `layout_score_proportional(score, request)` when horizontal positions must
follow an exact whole-note origin and columns-per-whole scale. It preserves the
requested scale, reports timeline and engraved-box collisions, and retains
logical continuation geometry outside the viewport. Use
`project_written_pitch(...)` or `project_continuous_pitch(...)` for the matching
vertical coordinate. The two bounded layout caches own immutable layouts only;
painted frames and transient pitch samples are not cached. Call
`clear_layout_cache()` after replacing a score set when deterministic release is
required. See `docs/petrucci-voce-handoff.md` for signatures and a measured
lifecycle workload.

The canonical path supports notes, chords, rests, ledger lines, breve through
128th durations, dots, stems, flags/beams, key-aware accidentals, signatures and
changes, repeats and endings, tuplets, grace notes, ties/slurs, fermatas,
dynamics, ornaments, pitch labels, lyrics, measured wrapping, and viewport
translation.

Petrucci imports neither Oud application modules nor curses. Oud translates the
portable frame to curses only in its UI adapter. External programs should adapt
their records directly to `NotationScore` or `FlowEvent`; product integration is
owned by the consuming repository.

The former `oud.core.*` model/render and `oud.presentation.ui.*` renderer aliases were removed.
`petrucci` is the only public typesetting path.

## Timed flow scores

`FlowEvent` accepts either `midi_pitches` for sounding-pitch input or `written_pitches` when enharmonic spelling must be preserved. Set its optional `beam` to preserve a source-authored `BeamKind`; an explicit value, including `BeamKind.NONE`, takes precedence over `FlowBeamPolicy.METER`. Automatic beaming is disabled by default for compatibility; select `FlowBeamPolicy.METER` to group only events whose `beam` is `None` by simple or compound meter beats. A source-authored beam group that would be split across an inferred measure boundary is rejected rather than altered. `FlowScoreOptions` can set the initial clef and key signature.

Use `adapt_flow_events` for one fixed meter whose event times may cross inferred measure boundaries. Use `adapt_flow_measures` with `FlowMeasure` when boundaries are known, including pickups, short or irregular measures, meter changes, key changes, and clef changes. Measure-local event onset and duration values remain in units of that measure's active meter beat. An event crossing an explicit boundary is rejected rather than guessed or silently split.

## Transient pitch cues

`PitchCue` attaches a written pitch to an existing event ID or to an exact staff, measure, and event onset. Pass cues through `ScoreTypesetOptions.pitch_cues`. For a cached layout, call `typeset_layout(layout, score=score, options=...)`; changing cues repaints semantic cells with `ElementRole.PITCH_CUE` and does not run layout again or alter spacing. Cues outside the visible viewport are clipped.

## Upstream-derived quality coverage

Petrucci's typed note and tablature behavior is checked against translated invariants from the LilyPond 2.24.4 and MuseScore 4.6.0 software test suites. See `docs/upstream-notation-quality.md` for pinned sources, covered contracts, and explicit non-claims.
