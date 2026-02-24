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
  - [ ] Add `:set tabnotation=minimal|full` preset switch (thin router only; no duplicated renderer).
  - [ ] Define preset table (which `show*` / stem / beam / rest / cue options are toggled together).
  - [ ] Ensure preset application is idempotent and can be overridden per-option after preset.
  - [ ] Add regression tests that preset changes visible rows/cues and still preserves note/flag alignment.
- [ ] Flag styles parity: English grid beams and continental flags.
- [ ] Beamify algorithm for grouped beams and partial beams.
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Ornaments and signs: LH/RH fingerings, arpeggio/separee, rests/dynamics/fermata/coda/repeats.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] Tablature formatting parity: configurable fret label policies (numeric/letter/custom labels), multi-digit fret collision rules, bass-label policies.
  - [ ] Split fret-label formatting policy from renderer placement (`format_fret` + width/collision policy).
  - [ ] Add configurable multi-digit fret spacing policy (tight / separated / collision-safe).
  - [ ] Add configurable bass-label policy matrix (numeric / slash / tuning / hidden when unused).
  - [ ] Add tests for `1-2-12` style separation in Italian mode and no accidental glyph merging.
- [ ] Tablature tie/slur/gliss parity: tied-note visibility/parenthesize cues and follow-up behavior across system breaks.
  - [ ] Model tied-note display policy (`hide`, `show`, `parenthesize`) for continued notes.
  - [ ] Handle tie-followed-by-slur/gliss notehead display cues explicitly.
  - [ ] Add system-break regressions for tied note visibility and cue placement.
  - [ ] Add collision tests for gliss/slur lines against fret glyphs and parentheses.
- [ ] MusicXML notation parity: fermata/fingering/pluck + richer barline/repeat/time symbols.
- [ ] Add Spanish tab support (Italian-like with inverted string order).
- [ ] Configurable time-signature rendering style (symbol vs numeric/full cue for `C`/`O` and fractions).
  - [ ] Add setting (`timesigstyle` or similar): `symbol|numeric|fraction`.
  - [ ] Map `C/O` to numeric cues (`4/4`,`3/4`) when requested.
  - [ ] Keep in-staff cue placement and no-overlap guarantees across styles.
  - [ ] Add regressions for system-start and mid-system meter changes in each style.
- [ ] LilyPond tab parity audit matrix: map supported/unsupported TabStaff features and track parity status per feature.
  - [ ] Create `DOCS` parity table: feature, status (`done/partial/missing`), notes, tests.
  - [ ] Cover core areas first: formatting, stems/beams, ties/slurs/gliss, polyphony, tunings, rests/time cues.
  - [ ] Link each parity row to test files (or TODO item if untested).

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
  - [ ] Add explicit assignment policy object/settings (minimum fret, max stretch, restrain open strings).
  - [ ] Respect forced string input while handling impossible/negative fret cases deterministically.
  - [ ] Add diagnostics/warnings path for impossible placements (do not silently mis-render).
  - [ ] Add synthetic assignment tests for constrained chord placement.
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
  - [ ] Add fullscreen-width synthetic cases with alternating system row counts (bass rows appear/disappear).
  - [ ] Add `scrollmode=smooth|page` behavior assertions for same fixtures.
  - [ ] Add `beatsnap=off|soft` navigation-map consistency checks.
- [ ] Rendering matrix tests (synthetic): mixed durations/chords, collisions, bass rows on/off, all spacing modes.
  - [ ] Build a reusable synthetic bar/system factory (durations, rows, dots, ties/slurs, meter changes).
  - [ ] Matrix over `justify` (`compact/smart/stretch/edge`) and `beatsnap` (`off/soft`).
  - [ ] Matrix over `flagstyle` (standard/board/englishgrid/continental/italian/thin/capirola).
  - [ ] Assert invariants first (alignment/no lonely stems/no overflow), snapshots second.
- [ ] Layout/spacing tests: per-bar width allocation, row alignment, right-justify behavior, beat-snap (`off/soft`) fill/trim behavior.
  - [ ] Per-system width accounting: sum(bar widths + gaps) exactly matches usable width.
  - [ ] Right-edge padding invariant (`|` at width-2) under all layouts.
  - [ ] Left/right trim invariants for `beatsnap=soft` (no fake empty trailing beat, no introduced left slack on beat-aligned bars).
  - [ ] At least one `-` before right `|` when staff content exists.
- [ ] Conversion tests: `.tab/.ft3 -> model -> .tab/.ft3` goldens.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` (supported subset).
- [ ] Geometry tests: multi-digit frets, tick spacing, stem-through-staff, ties/slides on notes/chords.
  - [ ] Multi-digit fret width/collision cases (`10/11/12`) in Italian and French/letter modes.
  - [ ] Dot and flag-tail placement cases (dotted 16th/32nd near dense groups).
  - [ ] Time-cue overlap cases in auftact area (`C/O/3`) with dense first beats.
- [ ] Import fixtures: 7th/8th-course fretted notes, multi-section TAB, no-break header/body, meter changes mid-system.
- [ ] Property/fuzz parser tests for malformed flags/rhythms/whitespace.
- [ ] LilyPond-inspired snippet regressions (synthetic): stem/beam behavior, polyphony, letter tablature formatting, slides/gliss, harmonics.
  - [ ] `stem-and-beam-behavior` analogue: stem direction/beam shape options in tab rows.
  - [ ] `polyphony-in-tablature` analogue: two voices, independent rhythms, same staff.
  - [ ] `letter-tablature-formatting` analogue: same music rendered in numeric vs letter formatting.
  - [ ] `slides/gliss/harmonics` analogues: cue/collision placement and visibility rules.
- [ ] LilyPond-style visual regression workflow (optional): snapshot/signature diff for ASCII renderer outputs across known cases.
  - [ ] Define canonical ASCII snapshot normalization (trim volatile header/status/cursor/playback marks).
  - [ ] Add snapshot update/check script for selected synthetic cases.
  - [ ] Optional structural “signature” diff (onset columns, flag columns, row widths) before full snapshot diff.
