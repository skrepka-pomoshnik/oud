# TODO

Goal
Recreate a curses TUI lute tab editor with vim-like controls, FT3/TAB read/write, MIDI + LilyPond/MusicXML export. Keep it unix-way, layered, and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.10+
- macOS/Linux
- pure curses, minimal deps

P0 (Edit-mode bugs — verified 2026-06-12, fix first)
- [x] French insert mode cannot enter frets `e/h/q/s/t/w`: `duration_value()` letter aliases (w/h/q/e/s/t) intercept them before `_handle_insert_char`. Drop the lowercase letter duration aliases (README documents digits 1-7) or gate them behind a setting.
- [x] `q` in insert mode with an unmodified buffer sets "Duration 4" instead of quitting: `_handle_quit` returns False to mean "exit app" but `dispatch_actions` reads False as "unhandled" and falls through to the duration map.
- [x] First keystroke in a chord bar is irreversible: `_flatten_chords_to_grid` clears `bar.chords`/`bar.notes` and writes overrides/durations/dotted with no undo record. Undo leaves the bar flattened with leftover grid data. Affects every FT3-loaded bar.
- [x] One insert keystroke produces two undo steps (separate `override` + `duration_col` actions). Wrap each keystroke's side effects (flatten, override, duration, auto-advance) in one undo group — the `undo_group` machinery already exists.
- [x] `x` on an empty column deletes a note from the nearest chord: `chord_index_at_col` nearest-match fallback lets `clear_cell`/`set_chord_note` target a chord the cursor is not on. Require an exact slot match for destructive ops.
- [x] Chord column geometry still has multiple display mappings: edit-side slots now use the same raw `chord_positions` contract as render/flatten/status paths; `visual_cursor_map` remains a display-only scaling layer for visual navigation, with dense playback marker monotonicity preserved.
- [x] `:e`/open leaks previous-file state: undo/redo stacks, annotations, ornaments, slurs/ties/holds/glisses, highlights, stave_breaks, marks, and `modified` all survive `cmd_open`. Undo after open corrupts the new piece. Reset all per-file layers in one place.
- [x] Multi-bar delete double-shifts stave breaks: `delete_bar` already reindexes `stave_breaks`, then `_cmd_bar_delete`/`cmd_stave` re-shift ({6} becomes {2} instead of {4} after deleting 2 bars). Remove the manual re-shift.
- [x] `glisses` and `marks` are not reindexed by `insert_bar`/`delete_bar`/`snapshot_bar`/yank/paste, unlike slurs/ties/holds — bar edits desync gliss rendering and mark jumps.
- [x] Count handling is inconsistent: `dd` ignores the count and leaves `count_prefix` stale (so `2dd` deletes one bar, then the 2 applies to the next motion); `yy` consumes it; `3x` steps by raw grid cell, not note slot. Word-search/match/mark handlers never clear the count.
- [x] Undo/redo do not restore cursor position, and always set `modified = True` even when undoing back to the saved state.

P0 (Edit-mode clunkiness)
- [x] Remove dead chord-branch code in insert handlers: flatten always precedes, so every `bar.chords` path in `_handle_insert_note`/`_handle_insert_fret_value`/`_apply_duration_key`/`_handle_insert_bass_slash` is unreachable (~150 duplicated lines across 4 copies).
- [x] Up to three implicit cursor moves happen per keystroke (`advance_if_overflow`, snap-to-previous-time-slot, snap-to-chord-slot) before the edit lands — typing feels teleporty. Make auto-advance predictable and apply at most one snap.
- [x] Deduplicate the post-insert advance (`steps = 2 if grid == on else 1; move_right`) repeated in 4 handlers.
- [x] Visual mode is yank-only; add delete/change over the selection.
- [x] Decide the long-term model: short-term P0 keeps structured import bars at the file boundary and flattens to grid overlays on first edit; a single canonical per-bar event store is deferred to the architecture backlog rather than mixed into bug fixes.

P1 (Core architecture + stable editing)
- [ ] Incremental TAB parser pass: reparse only changed ranges and expose stable AST deltas.
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [x] Finish normal-mode motion/action split so remaining edit-triggered moves use pure motion targets.
- [x] Expand bar/chord range primitives and route remaining delete/change/yank/range commands through them.
- [ ] Reflow/transform undo integration: use compound undo grouping for multi-step commands.
- [ ] Bring duet/mixed-score playback marker onto the same minimal overlay path as single-staff playback.

P2 (Notation + formats)
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] Tablature formatting parity: configurable fret label policies, multi-digit fret collision rules, bass-label policies.
- [ ] Add custom fret label mapping with validation and export-safe fallback.
- [ ] Add Spanish tab support.
- [ ] Vocal/lyric FT3 parity: finish duet/vocal integration with shared system breaks and shared playback mapping.
- [ ] Normalize remaining multi-verse raw FT3 vocal-text variants (`now_o_now`/`felice`-like cases) beyond current row-preserving decode.
- [ ] Decode remaining FT3 bar-record semantics: ties/slurs/holds and still-unclassified header bits beyond repeats/double bars/system breaks, including volta/endings if FT3 encodes them.
- [ ] Continue corpus verification for FT3 metadata aliases if new files expose instrument/style/tuning outside current header extraction.
- [ ] LilyPond output parity: export imported non-tab staves (vocal-only, mixed vocal+lute, raw note-staff cases) instead of warning-only fallback.
- [ ] LilyPond output parity: improve native handling of vocal rests/accidentals, FT3 extras, and page/system layout controls.

P3 (Maintainability + advanced parity)
- [x] Slim or remove the `command_ops.py` re-export shim (the split into domain modules is done; pure wrappers are now explicit compatibility exports).
- [ ] Buffer list / quick switch / prev-next buffer parity.
- [ ] Register-like macro/prompt buffers.
- [ ] Generic plugin protocol and plugin lifecycle cleanup.
- [ ] Partial undo snapshots (system/stave-scoped restore).
- [ ] True multiple-staves-per-system editing beyond duet hint rendering.
- [ ] Keep canonical command storage and display formatting separate; audit view-only suppression/de-emphasis rules.
- [ ] Unify pitch<->string/fret transforms around one shared service for input and export.
- [ ] Add tab fret-glyph metrics/cache layer so spacing uses measured label width.
- [ ] Add multi-voice tab collision precedence model before true polyphonic tab voices.
- [ ] Add German tab support.
- [ ] Historical style presets (fonts/layouts per source).
- [ ] MEI import/export support.
- [ ] Export tablature as graphics formats.
- [ ] Page layout options (orientation, paper, margins, spacing, indents).
- [x] Loop playback for selection/range (visual `v`/`V` delete/change exists).
- [x] Tools parity: remove comments, grid flag style, global reflow.

P4 (Optional)
- [ ] Mouse support.
- [ ] Qt GUI backend adapter over renderer/controller core.
- [ ] Optional last-system padding/flourish visual policy.

Testing backlog
- [x] Keep `test_midi_command_fluidsynth_with_soundfont_darwin` macOS-only because it depends on an author-local macOS SoundFont path.
- [x] Regression tests for the P0 edit-mode bugs above (flatten+undo round-trip, `x` exact-slot, `:e` state reset, stave-break shift, count semantics).
- [ ] Conversion goldens: `.tab/.ft3 -> model -> .tab/.ft3`.
- [ ] FT3 export/import goldens once FT3 writer exists.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` supported subsets.
- [ ] Add `.mei` matrix cases when MEI import/export exists.
- [x] Synthetic snippet regressions for stems/beams, polyphony, letter tablature formatting, slides/gliss, harmonics.
- [ ] Layout-invariant tests: row widths, cue visibility, right-edge alignment, no dropped sparse symbols after reflow/scale.
- [ ] Mixed-score FT3 regressions: synthetic raw-prefix-plus-tab-suffix cases, barline-only prefix records, and vocal/lyrics alignment invariants.
- [ ] Port more relevant engraving/layout scenarios from reference suites into synthetic ASCII regressions.

Reference-driven backlog

FT3 / luteconv / LuteScribe
- [ ] Continue reverse-engineering mixed-score raw note/barline records for richer imported non-tab staves and better raw text-score decode.
- [ ] Improve system/stave-wrap reflow with whole-bar break candidates and preferred barline split points.

MuseScore engraving
- [ ] Add transaction-style edit grouping around complex operations (reflow, transpose/retune, split/merge).

General
- [ ] Review remaining reference repos (`VITABS`, `tuitar`, `LuteScribe`, `MuseScore`) only for missing behavior still not mapped here.
