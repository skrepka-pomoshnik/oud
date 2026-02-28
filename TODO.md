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
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.

P2 (Notation + formats)
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] Tablature formatting parity: configurable fret label policies (numeric/letter/custom labels), multi-digit fret collision rules, bass-label policies.
  - [ ] Add custom fret label mapping (user-defined alphabet/symbol set) with validation and export-safe fallback.
- [ ] Add Spanish tab support (Italian-like with inverted string order).
- [ ] Vocal/lyric FT3 parity (layered parser + renderer).
  - [ ] Add duet/vocal score integration: melody+lyrics rows per staff with shared system breaks.

P3 (Maintainability + advanced parity)
- [ ] Split `command_ops.py` into small domain modules with thin router.
- [ ] Buffer list / quick switch / prev-next buffer parity.
- [ ] Register-like macro/prompt buffers.
- [ ] Generic plugin protocol and plugin lifecycle cleanup.
- [ ] MEI import/export support.
- [ ] Export tablature as graphics formats.
- [ ] Add German tab support.
- [ ] Historical style presets (fonts/layouts per source).
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
- [ ] Conversion tests: `.tab/.ft3 -> model -> .tab/.ft3` goldens.
  - [ ] FT3 export/import goldens once FT3 writer exists.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` (supported subset).
  - [ ] Add `.mei` matrix cases when MEI import/export exists.
- [ ] LilyPond-inspired snippet regressions (synthetic): stem/beam behavior, polyphony, letter tablature formatting, slides/gliss, harmonics.

Reference-derived backlog (source-indexed, pending)

VITABS (`refs/VITABS`)
- [ ] Finish normal-mode motion/action split beyond core cursor moves (`h/j/k/l`, note-wise, visual-row jumps, `w/b/gg/G/$`, `f/F/t/T`, word search `* #`, `%`, mark jumps are extracted, and wrappers now share motion-target apply); several edit-triggered cursor moves (bar/rhythm advances plus insert-mode row-step/snap helpers) also use pure targets; migrate remaining edit-triggered cursor moves.
- [ ] Expand first-class range primitives (bar/chord) into multi-chord edit ranges and route remaining delete/change/yank/range commands through them (counted `:chord del/insert/yank/paste N`, counted bar yank/paste via `Nyy`/`p`, and counted `:bar del/yank/paste N` are in place).

tuitar (`refs/tuitar`)

LuteScribe (`refs/LuteScribe`)
- [ ] Add compound undo grouping API and use it for reflow, transforms, and multi-step commands (API is in place; local multi-step cell clears, counted `x`, and bar paste use transactional undo, but reflow/transform command families still need integration).
- [ ] Add partial undo snapshots (system/stave-scoped restore) to avoid full-score restore for local edits.
- [ ] Refine reflow by stave-wrap/system-wrap with whole-bar break candidates and preferred barline split points.
- [ ] Implement true multiple staves per system (duet score rendering and editing), beyond current `Lute 1 / Lute 2` metadata hint line.
- [ ] Keep canonical command storage and display formatting separate; audit view-only suppression/de-emphasis rules (e.g. redundant continue-flag display).
- [ ] Optional last-system padding/flourish display policy (visual-only, no content mutation).

luteconv / FT3 reverse-engineering (`refs/luteconv`, `refs/LuteScribe/Source/luteconv`)
- [ ] Decode remaining FT3 bar-record semantics: ties/slurs/holds, layout/system-break hints, and additional editorial markers.
- [ ] Decode/verify FT3 instrument/style/tuning fields that may exist outside current header/annotation extraction.
- [ ] Add explicit barre semantics import/rendering (avoid suppressing ambiguous open-string LH fingerings blindly).
- [ ] Add FT3 binary feature matrix docs/tests (which bar/note fields are decoded vs ignored).

MuseScore engraving (`refs/MuseScore/src/engraving`)
- [ ] Add `StaffType`-like tab style preset model (single policy object) for tab rendering toggles:
  duration-symbol repeat policy, minim style, stems-through/beside, on-lines/between-lines, upside-down, rests on tab, tab fingering visibility.
- [ ] Unify pitch<->string/fret transforms around a `StringData`-like service for both input and export (same rules for `convertPitch/getPitch/fret`).
- [ ] Add explicit tied-fret display policy options (MuseScore `ShowTiedFret` / `ParenthesizeTiedFret` analogue) and keep tie layout conditional on that policy.
- [ ] Add tab-specific stem geometry policy (through-staff vs beside-staff, minim-style stem shortening/slashing) separated from generic flag rendering.
- [ ] Add tab-specific dot placement policy (near stems vs near fret glyphs) with regression tests.
- [ ] Add tab fret-glyph metrics/cache layer (label bbox/offsets by style) so spacing uses measured label width, not ad hoc string length only.
- [ ] Add tab bass-prefix policy matrix (slashes/numbers/ledger behavior) modeled as style rules, not hardcoded per renderer branch.
- [ ] Add multi-voice tab collision precedence model (voice noteheads/frets, ties/slurs/gliss, ornaments) before implementing true polyphonic tab voices.
- [ ] Add MuseScore-style layout-invariant tests (no unlaid items / geometry sanity) for our renderer:
  row widths, cue visibility, right-edge alignment, no dropped sparse symbols after reflow/scale.
- [ ] Add edit-command undo grouping around complex operations (reflow, transpose/retune, split/merge) similar to `startCmd/endCmd` transactional edits.
- [ ] Study `src/engraving/tests/layoutelements_tests.cpp`, `parentheses_tests.cpp`, `partialtie_tests.cpp`, `spanners_tests.cpp`, `barline_tests.cpp` in more detail and port the most relevant scenarios to synthetic ASCII regressions.
