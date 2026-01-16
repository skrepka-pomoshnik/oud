# TODO

refs: 
tab -- use features and ideas, but do not use the code!
luteconv - reuse freely its gpl3

Recreate curses tui lute tab editor with vim like controls and ability to read fronimo files and possible midi and lilypond export. Possibly unix-way and suckless as possible, as nnn or vi.

Constraints
- Python 3.13 only, macOS/Linux.
- Pure curses, minimal deps.

- [x] [p1] no horizontal scroll only vertical scroll, when you go to the left you go to the next row, all is adaptive to term width
- [x] [p1] more vim like orientation through the bars, bars like words, rows like lines, etc
- [x] [p1] better 1 2 3 4 5 as 1 1/2 1/4 etc for french tabs and buttons like w h e etc for italian
- [] [p1] playmidi inside the score from the choosen bar, option to choose tempo for the score, make midi timbre more lute like

I/O and exports
- [ ] [p2] LilyPond export: generate headers (title/composer), tuning, time sig, barlines, repeats.
- [ ] [p2] LilyPond export: ornaments/slurs/ties/holds mapping or graceful omit.

Renaissance tablature basics
- [ ] [p2] Bass course entry: slash shorthand (/ // ///) and numeric bass labels (7-13 or 1-7).
- [ ] [p2] Flag styles: English grid beams vs continental single flags.
- [ ] [p2] Tuning presets for 7–13 course lutes and baroque tunings; show in header.

Maintainability (suckless)

Packaging + docs
- [ ] [p2] Add `pyproject.toml` for future pip release metadata.
- [ ] [p2] Add short `README.md` with ASCII usage/demo.
- [ ] [p2] Add `LICENSE` (GPL-3.0).

Tab utility parity (notation + layout ideas)
- [ ] [p3] Embedded command lines in source (line begins with -) and per-system overrides.

Fronimo parity (settings + workflow)
- [ ] [p1] Time signature entry and validation; quick set to modern signatures.
- [ ] [p1] Rhythmic value entry flow (numeric input + auto-advance) with dotting.
- [ ] [p1] Verify measure length and rebeam notes (validation + auto-fix hints).
- [ ] [p1] Measure displacement and bar spacing controls (packed vs spread).
- [ ] [p2] Section/title/subtitle/footnote fields with per-section settings.
- [ ] [p2] Page layout: gaps between systems, title/subtitle, staff/lyrics.
- [ ] [p2] Font profile presets (notation/tab/text/title/lyrics/bar #).
- [ ] [p2] Bar numbering options (base, first marked, box, per-staff/per-group).
- [ ] [p2] Footnote and editorial note tools (markers, placement, y-offset).
- [ ] [p2] Ornament editor and toggles (prefix/postfix ornaments).
- [ ] [p2] Slur/tie editor (shape, endpoints, thickness).

LuteScribe parity (features + workflow)
- [ ] [p1] Stave wrap/reflow: set max chords per stave and auto reflow.
- [ ] [p1] Insert/delete chord items; insert bar line; insert common TAB commands.
- [ ] [p1] Stave operations: insert break, join with next, insert new stave, delete stave.
- [ ] [p1] Headers editor: insert common header commands; edit title/author.
- [ ] [p1] Visual formatting: tab editable symbols (hotkey f) symbols for flags and tab letters; hide redundant flag markers.
- [ ] [p2] Pad last stave with flourish/spacing for nicer last line.
- [ ] [p2] Import compatibility notes for TAB/FT3/JTXML (read flags, ornaments, headers, time sigs).
- [ ] [p2] Export/preview pipeline: PDF preview, print, recent files list.
- [ ] [p2] Tools: remove comments, set grid flag style, reflow all.
- [ ] [p2] Playback window: play piece/selection/stave with instrument + tempo defaults.
