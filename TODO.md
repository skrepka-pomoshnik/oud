# TODO

Goal
Recreate a curses TUI lute tab editor with vim-like controls, FT3/TAB read/write, MIDI + LilyPond/MusicXML export. Keep it unix-way, layered, and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.10+
- macOS/Linux
- pure curses, minimal deps

P1 (Core architecture + stable editing)
- [ ] Incremental TAB parser pass: reparse only changed ranges and expose stable AST deltas.
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Finish normal-mode motion/action split so remaining edit-triggered moves use pure motion targets.
- [ ] Expand bar/chord range primitives and route remaining delete/change/yank/range commands through them.
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
- [ ] Split `command_ops.py` into small domain modules with thin router.
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
- [ ] Selection mode (`v`) and loop playback for selection/range.
- [ ] Tools parity: remove comments, grid flag style, global reflow.

P4 (Optional)
- [ ] Mouse support.
- [ ] Qt GUI backend adapter over renderer/controller core.
- [ ] Optional last-system padding/flourish visual policy.

Testing backlog
- [ ] Conversion goldens: `.tab/.ft3 -> model -> .tab/.ft3`.
- [ ] FT3 export/import goldens once FT3 writer exists.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` supported subsets.
- [ ] Add `.mei` matrix cases when MEI import/export exists.
- [ ] Synthetic snippet regressions for stems/beams, polyphony, letter tablature formatting, slides/gliss, harmonics.
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
