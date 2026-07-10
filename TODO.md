# TODO

Goal
Publish on GitHub as a usable alpha: a solid viewer for most lutemusic.org tablature, plus alpha-quality editing. Curses TUI lute tab editor with vim-like controls, FT3/TAB read/write, MIDI + LilyPond/MusicXML export. Keep it unix-way, layered, and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.11+
- macOS/Linux
- pure curses, zero runtime dependencies

P0 (fix immediately)
- [x] `.tab` import: malformed/empty files show a persistent import warning and cannot replace the active score; partially saved files retain recoverable bars and report the missing end marker.
- [x] Triage the bundled lutemusic corpus: 36/36 supported files load, all formerly warned content is represented, and the release smoke pass reports zero errors and zero warnings.

P1 (publication blockers)

Viewer — support most lutemusic.org tabs:
- [x] Readonly viewer parity for bundled mixed/multi-part FT3 scores: header-boundary staff markers and empty note records are preserved as note staves; `can_she_excuse_4_part.ft3` and `unquiet_thoughts_4-part.ft3` render without unknown staves.
- [x] Decode all bar-header semantics observed in the bundled corpus: repeats, double bars, system breaks, and the redundant `0x20` repeat-boundary modifier. Isolated unknown marker combinations still warn; unconfirmed FT3 tie/slur/hold and volta storage is post-alpha reverse engineering.
- [x] Vocal/lyric FT3 viewer parity: structured and recovered text is represented in note/lyric/comment staves, systems share layout, and playback markers use the shared render mapping without partial-support warnings.
- [x] Normalize multi-verse raw FT3 vocal-text display: auto layout caps an oversized text lane to the viewport and never drops the only bar; `felice` remains visible at width 100 and `now_o_now` retains its recovered verses.
- [x] Wide-corpus smoke test: batch-load a few hundred lutemusic.org files (importer must never crash; count and classify warnings). Repeatable local/live scanner: `scripts/corpus_smoke.py`.

Editing — alpha quality:
- [x] Reflow/transform undo integration: use compound undo grouping for multi-step commands (transpose/retune/reflow).
- [x] Alpha pass of the full edit loop on a real piece (enter, correct, save, MIDI/LilyPond export, reopen), preserved as `tests/test_release_workflow.py`.

Publication mechanics:
- [x] Add a screenshot or asciicast to README (generated from the real renderer by `scripts/render_readme_screenshot.py`).
- [x] Fill `[project.urls]` in pyproject.toml; PyPI `oud` endpoint returned 404 on 2026-07-10. Recheck immediately before first upload because names are not reserved.
- [x] Keep existing git history: audit found only local-host/placeholder/blank emails, not a personal mailbox requiring a rewrite.
- [ ] Confirm GitHub Actions green on macOS. Required first-push files are already tracked on `origin/main`; the private Actions API is not observable without authentication.

P2 (post-publication features)
- [ ] Multiple staves per system: add/delete/reorder.
- [ ] Merge/split staves into separate voices.
- [ ] Incremental TAB parser pass: reparse only changed ranges and expose stable AST deltas.
- [ ] Bring duet/mixed-score playback marker onto the same minimal overlay path as single-staff playback.
- [ ] Publish renderer cursor display maps from the duet view too (it currently falls back to the editor-side approximation, so duet h/l movement can stall like single-staff used to).
- [ ] Slur/line styles: up/down, vertical/diagonal, thickness controls.
- [ ] Double/halve rhythm values and normalization at barlines/intervals.
- [ ] Tablature formatting parity: configurable fret label policies, multi-digit fret collision rules, bass-label policies.
- [ ] Add custom fret label mapping with validation and export-safe fallback.
- [ ] Add Spanish tab support.
- [ ] Continue corpus verification for FT3 metadata aliases if new files expose instrument/style/tuning outside current header extraction.
- [ ] Reverse-engineer binary FT3 tie/slur/hold and volta/ending storage once confirmed fixtures or a format reference are available.
- [ ] LilyPond output parity: export imported non-tab staves (vocal-only, mixed vocal+lute, raw note-staff cases) instead of warning-only fallback.
- [ ] LilyPond output parity: improve native handling of vocal rests/accidentals, FT3 extras, and page/system layout controls.

P3 (maintainability + advanced parity)
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

P4 (optional)
- [ ] Mouse support.
- [ ] Qt GUI backend adapter over renderer/controller core.
- [ ] Optional last-system padding/flourish visual policy.

Testing backlog
- [ ] Conversion goldens: `.tab/.ft3 -> model -> .tab/.ft3`.
- [ ] FT3 export/import goldens once FT3 writer exists.
- [ ] Conversion matrix tests for `.ft3/.tab/.musicxml/.mei` supported subsets.
- [ ] Add `.mei` matrix cases when MEI import/export exists.
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
