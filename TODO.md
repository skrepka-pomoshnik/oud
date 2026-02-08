# TODO

refs:
- tab -- use features and ideas, but do not use the code
- luteconv -- reuse freely (GPLv3)

Goal
Recreate a curses TUI lute tab editor with vim-like controls, FT3/TAB read/write, MIDI + LilyPond/MusicXML export. Keep it unix-way, layered, and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.10 only
- macOS/Linux
- pure curses, minimal deps

P0 (Critical: correctness + UX breakage)
- [ ] Fix `J/K` row movement: jump to visually corresponding bar/column on next/prev system with no drift.
- [ ] Enforce strict note/flag alignment invariant: every rendered stem/beam column must have at least one note under it.
- [ ] Remove note slippage across rhythm groups (e.g., 8th and 16th groups must not visually merge).
- [ ] Fix playback `^` mapping under all spacing modes so marker never teleports backward.
- [ ] Keep bars filling terminal width without broken inter-bar gaps in `stretch`/`smart`.
- [ ] Add regression tests for all above using real FT3 fixtures (Lachrimae, Forlorne, Frog).

P1 (Core architecture + stable editing)
- [ ] UI state slices: split player/menu/prompt/view state into small structs with explicit reducers.
- [ ] Playback timeline contract: one canonical time->(bar,col) mapping shared by MIDI and UI highlight.
- [ ] Incremental TAB parser pass: reparse only changed ranges and expose stable AST deltas.
- [ ] Reflow by chord-wrap threshold: whole-bar breaks only, per-system chord cap.
- [ ] Rhythm rendering rule: show duration only on change; dotted markers stay on onset and never overwrite glyphs.
- [ ] Bass course entry: slash shorthand (`/ // ///`) and numeric bass labels.
- [ ] Inline bass display: extra courses as in-place rows only when used.
- [ ] Tuning presets for renaissance/baroque lute families.
- [ ] Course-shift keep-pitch edit ops (move across strings with fret recompute).
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Transpose tablature and convert between tunings.

P2 (Notation + formats)
- [ ] Flag styles parity: English grid beams and continental flags.
- [ ] Beamify algorithm for grouped beams and partial beams.
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Ornaments and signs: LH/RH fingerings, arpeggio/separee, rests/dynamics/fermata/coda/repeats.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] MusicXML import/export support.
- [ ] MusicXML import parser (`.musicxml -> Piece/Bar/Chord/Note`) with tablature technical tags.
- [ ] MXL package support (`.mxl` read/write).
- [ ] MusicXML notation parity: fermata/fingering/pluck + richer barline/repeat/time symbols.
- [ ] MusicXML conversion goldens from local `.tab/.ft3` fixtures only.
- [ ] Add Spanish tab support (Italian-like with inverted string order).

P3 (Maintainability + advanced parity)
- [ ] Split `command_ops.py` into small domain modules with thin router.
- [ ] Buffer list / quick switch / prev-next buffer parity.
- [ ] Register-like macro/prompt buffers.
- [ ] Generic plugin protocol and plugin lifecycle cleanup.
- [ ] MEI import/export support.
- [ ] Export tablature as graphics formats.
- [ ] Add German tab support.
- [ ] Historical style presets (fonts/layouts per source).
- [ ] Page layout options (orientation, paper, margins, spacing, indents).
- [ ] Selection mode (`v`) and loop playback for selection/range.
- [ ] View invert with correct controls.
- [ ] Tools parity: remove comments, grid flag style, global reflow.

P4 (Optional)
- [ ] Mouse support.
- [ ] Qt GUI backend adapter over renderer/controller core.

Testing backlog
- [ ] Navigation regressions for `J/K` on uneven rows and mixed spacing modes.
- [ ] Alignment regressions: no lonely stems/beams, no cross-group slippage, duration/flag columns match note onsets.
- [ ] Rendering matrix tests: mixed durations/chords, collisions, bass rows on/off, all spacing modes.
- [ ] Layout/spacing tests: per-bar width allocation, row alignment, right-justify behavior.
- [ ] Conversion tests: `.tab/.ft3 -> model -> .tab/.ft3` goldens.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` (supported subset).
- [ ] Geometry tests: multi-digit frets, tick spacing, stem-through-staff, ties/slides on notes/chords.
- [ ] Import fixtures: 7th/8th-course fretted notes, multi-section TAB, no-break header/body.
- [ ] Property/fuzz parser tests for malformed flags/rhythms/whitespace.
