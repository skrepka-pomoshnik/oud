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

P1 (Core architecture + stable editing)
- [ ] Incremental TAB parser pass: reparse only changed ranges and expose stable AST deltas.
- [ ] Course-shift keep-pitch edit ops (move across strings with fret recompute).
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Transpose tablature and convert between tunings.

P2 (Notation + formats)
- [ ] Tablature full-notation preset bundle (LilyPond-like): coherent enable/disable for stems/beams/dots/rests/ties/slurs/tuplet cues.
  - [x] Add preset interaction tests for user overrides after preset + preset reapply precedence (documented behavior).
  - [x] Add preset matrix tests across `flagstyle` families (standard/board/englishgrid/continental).
  - [x] Cover ties/slurs/rests in `tabnotation=full` with synthetic regressions.
  - [ ] Add tuplet cue support + integrate it into `tabnotation=full`.
- [x] Flag styles parity: English grid beams and continental flags.
- [ ] Beamify algorithm for grouped beams and partial beams.
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Ornaments and signs:
  - [x] Repeats and repeat-word signs (`dc/ds/fine/coda/tocoda/...`).
  - [x] Rest entry/render in tablature (`r` insert mode, ASCII/TUI visibility).
  - [x] FT3 LH/RH fingerings + basic ornaments import and TUI display toggles.
  - [x] Manual bar-level dynamics (`:dynamic`) and fermata (`:fermata`) cues in TUI.
  - [ ] Arpeggio/separee signs (entry + rendering).
  - [ ] Richer sign export parity (LilyPond/MusicXML): dynamics/fermata/fingerings/pluck.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] Tablature formatting parity: configurable fret label policies (numeric/letter/custom labels), multi-digit fret collision rules, bass-label policies.
  - [ ] Add configurable multi-digit fret spacing policy (tight / separated / collision-safe).
  - [ ] Add configurable bass-label policy matrix (numeric / slash / tuning / hidden when unused).
  - [ ] Add tests for `1-2-12` style separation in Italian mode and no accidental glyph merging.
- [ ] Tablature tie/slur/gliss parity: tied-note visibility/parenthesize cues and follow-up behavior across system breaks.
  - [x] Handle tie-followed-by-slur/gliss notehead display cues explicitly.
  - [x] Add system-break regressions for tied note visibility and cue placement.
  - [x] Add broader collision tests for gliss/slur lines against fret glyphs and parenthesized noteheads (including system-break cases).
- [ ] MusicXML notation parity: fermata/fingering/pluck + richer barline/repeat/time symbols.
- [ ] FT3 -> LilyPond/PDF export parity track: preserve imported FT3 semantics in `.ly`/PDF output.
  - [ ] Export imported FT3 fingerings/ornaments (when present) to LilyPond tablature annotations.
  - [ ] Export FT3 repeat/barline markers with correct LilyPond barline/repeat constructs across real corpus cases.
  - [ ] Export FT3 meter changes (`C/O/fractions`) with configurable style mapping parity.
  - [ ] Add real-file FT3 -> `.ly` smoke matrix (parse + export) and `:pdf` command integration checks.
- [ ] Add Spanish tab support (Italian-like with inverted string order).
- [ ] LilyPond tab parity audit matrix: map supported/unsupported TabStaff features and track parity status per feature.
  - [ ] Keep `DOCS` parity table current as features land (status + linked tests).
  - [ ] Add “acceptance examples” column (synthetic case names) for faster regression triage.

P3 (Maintainability + advanced parity)
- [ ] Split `command_ops.py` into small domain modules with thin router.
- [ ] Buffer list / quick switch / prev-next buffer parity.
- [ ] Register-like macro/prompt buffers.
- [ ] Generic plugin protocol and plugin lifecycle cleanup.
- [ ] MEI import/export support.
- [ ] Export tablature as graphics formats.
- [ ] Add German tab support.
- [ ] Historical style presets (fonts/layouts per source).
- [ ] LilyPond parity: tablature assignment constraints (`minimumFret` / stretch / forced string) as explicit edit/engrave policies.
  - [ ] Wire core assignment policy into edit ops (course-shift keep-pitch / transpose) instead of ad-hoc placement.
  - [ ] Route export/engrave pitch->string fallback through assignment policy for deterministic behavior across formats.
  - [ ] Surface assignment diagnostics/warnings in TUI (`:verify` / status / info) when placement is impossible.
  - [ ] Replace temporary preset conversion bridge (`oud/editor/preset_convert.py`, 3rd-string-only shift) with assignment-policy based transpose/course-shift.
- [ ] LilyPond parity: polyphonic TabVoice behavior and collision handling for independent voices on one tab staff.
  - [ ] Represent multiple voices in one bar/system without destroying shared rhythm alignment.
  - [ ] Define collision precedence (voice noteheads, flags, ties/slurs, ornaments).
  - [ ] Add navigation rules for voice-dense rows (visual move vs note-wise move).
  - [ ] Add synthetic polyphony regressions (2 voices, mixed durations, crossings).
- [ ] Page layout options (orientation, paper, margins, spacing, indents).
- [ ] Selection mode (`v`) and loop playback for selection/range.
- [ ] View invert with correct controls.
- [ ] Tools parity: remove comments, grid flag style, global reflow.

P4 (Optional)
- [ ] Mouse support.
- [ ] Qt GUI backend adapter over renderer/controller core.

Testing backlog
- [ ] Navigation regressions for `J/K` on uneven rows and mixed spacing modes (including visible-row targeting under hidden bass rows).
  - [x] Add fullscreen-width synthetic cases with alternating system row counts (bass rows appear/disappear).
- [ ] Rendering matrix tests (synthetic): mixed durations/chords, collisions, bass rows on/off, all spacing modes.
  - [ ] Build a reusable synthetic bar/system factory (durations, rows, dots, ties/slurs, meter changes).
  - [ ] Matrix over `justify` (`compact/smart/stretch/edge`) and `beatsnap` (`off/soft`).
  - [ ] Matrix over `flagstyle` (standard/board/englishgrid/continental/italian/thin/capirola).
  - [ ] Assert invariants first (alignment/no lonely stems/no overflow), snapshots second.
- [ ] Layout/spacing tests: per-bar width allocation, row alignment, right-justify behavior, beat-snap (`off/soft`) fill/trim behavior.
  - [x] Per-system width accounting: sum(bar widths + gaps) exactly matches usable width.
  - [x] Right-edge padding invariant (`|` at width-2) under all layouts.
  - [x] Left/right trim invariants for `beatsnap=soft` (no fake empty trailing beat, no introduced left slack on beat-aligned bars).
  - [x] At least one `-` before right `|` when staff content exists.
- [ ] Conversion tests: `.tab/.ft3 -> model -> .tab/.ft3` goldens.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` (supported subset).
- [ ] Geometry tests: multi-digit frets, tick spacing, stem-through-staff, ties/slides on notes/chords.
  - [ ] Time-cue overlap cases in auftact area (`C/O/3`) with dense first beats.
- [ ] Import fixtures: 7th/8th-course fretted notes, multi-section TAB, no-break header/body, meter changes mid-system.
- [ ] Property/fuzz parser tests for malformed flags/rhythms/whitespace.
- [ ] LilyPond-inspired snippet regressions (synthetic): stem/beam behavior, polyphony, letter tablature formatting, slides/gliss, harmonics.
  - [ ] `stem-and-beam-behavior` analogue: stem direction/beam shape options in tab rows.
  - [ ] `polyphony-in-tablature` analogue: two voices, independent rhythms, same staff.
- [x] LilyPond-style visual regression workflow (optional): snapshot/signature diff for ASCII renderer outputs across known cases.
  - [x] Define canonical ASCII snapshot normalization (trim volatile header/status/cursor/playback marks).
  - [x] Add snapshot update/check script for selected synthetic cases.
  - [x] Optional structural “signature” diff (onset columns, flag columns, row widths) before full snapshot diff.
