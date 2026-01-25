# TODO

refs:
tab -- use features and ideas, but do not use the code!
luteconv - reuse freely its gpl3

Goal
Recreate curses TUI lute tab editor with vim-like controls, FT3/TAB read, MIDI + LilyPond export. Keep it unix-way and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.10 only, macOS/Linux, pure curses, minimal deps.

P1 (Suckless + Maintainable Core)
- [ ] Action-dispatch helpers: reuse a single action-map pattern in key handlers.
- [ ] Single command surface: move TUI command logic into editor ops only.
- [ ] Simplify editor actions: split normal/insert handlers into smaller pure helpers.

P2 (Core Features)
- [ ] Cursor helpers: centralize clamp/offset logic in controller utils.
- [ ] Message constants: reduce inline strings, standardize status wording.
- [ ] Declarative layout map: define screen regions and row offsets in one place.
- [ ] TUI test coverage: ui/tui modules at 100% coverage (render + input + commands). (started: tui/controller tests)
- [ ] Playback animation: highlight current bar/column while MIDI is playing.
- [ ] Vim keyset parity.
- [ ] Bars per line/system: limit bars per row (0 = auto).
- [ ] View invert option: reverse row order while keeping controls correct.
- [ ] LilyPond export: headers, tuning, time sig, barlines, repeats.
- [ ] LilyPond export: ornaments/slurs/ties/holds mapping or omit.
- [ ] Bass course entry: slash shorthand (/ // ///) and numeric bass labels (7-13 or 1-7).
- [ ] Inline bass display: show extra courses as in-place rows (e.g. `---` / `-a-` under staff) instead of full extra lines.
- [ ] Inline bass labels: numeric (preferred) and slash styles, editable rows.
- [ ] Flag styles: English grid beams vs continental single flags.
- [ ] Tuning presets for 7-13 course lutes and baroque tunings; show in header.
- [ ] Ornaments: left-hand signs, right-hand arpeggio/separee, fingering signs, rest/dynamics/fermata/coda/repeats.
- [ ] Slur/line styles: up/down, vertical/diagonal, adjustable thickness.
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Transpose tablature up/down; convert between tunings.
- [ ] Double/halve rhythm values; normalize rhythm signs to barlines/intervals.
- [ ] Reprise support: repeat/da capo markers and render cues.
- [ ] MusicXML import/export support (see refs).

P3 (Advanced + Parity)
- [ ] Plugin protocol: generic plugin interface (root_items/open/download/help_path).
- [ ] Export tablature as graphics in multiple formats.
- [ ] Export tablature/transcription to MEI.
- [ ] Add German/Spanish tab support.
- [ ] Style presets: historical tablature fonts/layouts per source.
- [ ] Text blocks: font/size/color for annotations and captions.
- [ ] End-of-piece arabesques and grace notes.
- [ ] Bracket styles: curved/square/none; parts export per staff.
- [ ] Page orientation/paper sizes; margins/indents/spacing controls.
- [ ] Layout presets: named layouts that reuse the declarative layout map.
- [ ] Selection mode (`v`) for range operations and exports.
- [ ] Loop playback for selection or bar range.
- [ ] Caption and page-numbering options.
- [ ] Fronimo metadata parsing: footnote/source/editor/comment, section annotations, key/type/difficulty/ensemble/part.
- [ ] Tools: remove comments, set grid flag style, reflow all.
- [ ] Playback window: play piece/selection/stave with instrument + tempo defaults.

P4 (Optional / Nice-to-have)
- [ ] Mouse support.
- [ ] GUI backend: Qt adapter using renderer ops + controller actions.
