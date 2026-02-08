# TODO

refs:
tab -- use features and ideas, but do not use the code!
luteconv - reuse freely its gpl3

Goal
Recreate curses TUI lute tab editor with vim-like controls, FT3/TAB read, MIDI + LilyPond export. Keep it unix-way and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.10 only, macOS/Linux, pure curses, minimal deps.

P2 (Core Features)
- [ ] Incremental TAB parser pass: reparse only changed bar/line ranges, not full document, and expose stable AST deltas.
- [ ] Rule pipeline for post-parse checks: pluggable lint/verify/convert rules over the same parsed model.
- [ ] UI state slices: split player/menu/prompt/view state into small structs with explicit reducers.
- [ ] Generic list-menu engine: shared `(items,index,offset,filter)` handler for plugins/files/help/buffers.
- [ ] Playback-cursor timeline contract: one time->(bar,col) source used by both MIDI playback and UI highlight.
- [x] Render packing invariant: no note/flag loss, no overlap, no hidden chord due to spacing mode.
- [ ] Reflow by chord-wrap threshold (TAB/LuteScribe style): whole-bar breaks only, per-system chord cap.
- [ ] Bass course entry: slash shorthand (/ // ///) and numeric bass labels (7-13 or 1-7).
- [ ] Inline bass display: show extra courses as in-place rows (e.g. `---` / `-a-` under staff) instead of full extra lines.
- [ ] Flag styles: English grid beams vs continental single flags.
- [ ] Beamify algorithm (TabCode-style): convert flagged runs into grouped beams with left/right partial beams.
- [ ] Rhythm rendering rule: show only duration changes; dotted markers follow onset note and never overwrite glyphs.
- [ ] Tuning presets for 7-13 course lutes and baroque tunings; show in header.
- [ ] Course-shift keep-pitch edit ops (TabCode idea): move note across courses while recomputing fret.
- [ ] Ornaments: left-hand signs, right-hand arpeggio/separee, fingering signs, rest/dynamics/fermata/coda/repeats.
- [ ] Slur/line styles: up/down, vertical/diagonal, adjustable thickness.
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Transpose tablature up/down; convert between tunings.
- [ ] Double/halve rhythm values; normalize rhythm signs to barlines/intervals.
- [ ] MusicXML import/export support (see refs).
- [ ] MusicXML import parser (`.musicxml -> Piece/Bar/Chord/Note`) with tablature technical tags.
- [ ] MXL package support (`.mxl` read/write with container.xml + mimetype).
- [ ] MusicXML conversion goldens built from local `.tab/.ft3` fixtures (no direct borrowed MusicXML fixtures).
- [ ] MusicXML notation parity: fermata/fingering/pluck + richer barline/repeat/time symbols.
- [x] Every TUI `:` command has at least one direct execution test.
- [x] TAB parser parity: handle multi-section files and missing header/body separator cleanly.

Testing (P2)
- [ ] Tab render tests (VexFlow parity): string->row mapping, flag/stem positions, dotted flags, beams/grid grouping, ties/slides, grace notes.
- [ ] Rendering matrix tests: cover mixed durations/chords, dotted flags, collisions, auto spacing (no lost notes/stems), multiple flag styles, bass rows on/off.
- [ ] Layout/spacing tests: per-bar width allocation, alignment across rows, mixed durations, right-justify behavior.
- [ ] Conversion tests (LuteScribe parity): .tab/.ft3 -> internal -> .tab/.ft3 golden files; parse/roundtrip on sample inputs.
- [ ] Conversion matrix tests (luteconv style): source x destination goldens for `.ft3/.tab/.tc/.musicxml/.mei` (subset to supported outputs).
- [ ] Geometry tests (VexFlow style): high-fret multi-digit widths, tick context spacing, stem-through-staff, tie/slide on single notes + chords.
- [ ] Import fixtures (LuteScribe style): 7th/8th-course fretted notes, multi-section TAB, no-break headers/body.
- [ ] Property/fuzz parser tests: malformed flags, repeated bars, mixed dotted rhythms, random whitespace/comments.
- [ ] Add Spanish tab support, its actually like italian tab, but inverted string order.

P3 (Advanced + Parity)
- [ ] Buffer list as lightweight quick menu (neatvi q).
- [ ] MEI import/export support (see refs).
- [ ] Split command_ops.py into small domain files (file I/O, score edits, tools, view) with a thin router.
- [ ] Vim parity: buffer list/quick switch (q menu), buffer aliases, previous buffer (~), next/prev buffer (+/-).
- [ ] Register-like macro/prompt buffers (neatvi-inspired): reusable command snippets for repetitive edit tasks.
- [ ] Plugin protocol: generic plugin interface (root_items/open/download/help_path).
- [ ] Export tablature as graphics in multiple formats.
- [ ] Export tablature/transcription to MEI.
- [ ] Add German tab support.
- [ ] Style presets: historical tablature fonts/layouts per source.
- [ ] Text blocks: font/size/color for annotations and captions.
- [ ] End-of-piece arabesques and grace notes.
- [ ] Bracket styles: curved/square/none; parts export per staff.
- [ ] Page orientation/paper sizes; margins/indents/spacing controls.
- [ ] Layout presets: named layouts that reuse the declarative layout map.
- [ ] Selection mode (`v`) for range operations and exports.
- [ ] Loop playback for selection or bar range.
- [ ] Caption and page-numbering options.
- [ ] Tools: remove comments, set grid flag style, reflow all.
- [ ] Playback window: play piece/selection/stave with instrument + tempo defaults.
- [ ] View invert option: reverse row order while keeping controls correct.
- [ ] Layout profile presets (LuteScribe/TAB inspired): wrap, flourish-padding, page/spacing presets with one command.

P4 (Optional / Nice-to-have)
- [ ] Mouse support.
- [ ] GUI backend: Qt adapter using renderer ops + controller actions.
