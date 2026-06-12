# TODO

Goal
Publish on GitHub as a usable alpha: a solid viewer for most lutemusic.org tablature, plus alpha-quality editing. Curses TUI lute tab editor with vim-like controls, FT3/TAB read/write, MIDI + LilyPond/MusicXML export. Keep it unix-way, layered, and suckless.
Keep a running `DONE.md` log of completed work.

Constraints
- Python 3.11+
- macOS/Linux
- pure curses, zero runtime dependencies

P0 (fix immediately)
- [ ] `.tab` import: malformed or partially saved files silently load as an empty piece (strict parser returns None, legacy fallback yields 0 bars, no warning). Emit an import warning and keep whatever content is recoverable.
- [ ] Triage the import warnings across the local lutemusic corpus (13/43 files warn): each warning class must either be decoded (see P1) or degrade gracefully with no visual damage in the viewer.

P1 (publication blockers)

Viewer — support most lutemusic.org tabs:
- [ ] Readonly viewer parity for mixed/multi-part FT3 scores: `lutemusic/05_can_she_excuse/can_she_excuse_4_part.ft3` still imports as unknown staves (the only local corpus file without a usable view).
- [ ] Decode remaining FT3 bar-record semantics: ties/slurs/holds, volta/endings, and still-unclassified header bits beyond repeats/double bars/system breaks (5/43 corpus files warn about extra bar header markers).
- [ ] Vocal/lyric FT3 parity: finish duet/vocal integration with shared system breaks and shared playback mapping (7/43 corpus files warn that vocal details may be omitted).
- [ ] Normalize remaining multi-verse raw FT3 vocal-text variants (`now_o_now`/`felice`-like cases) beyond current row-preserving decode. Symptom: `lutemusic/01_felice_fu_quel_anon.ft3` renders a blank staff at width 100 — inflated lyric rows make every bar wider than the screen, so the system packer drops all bars.
- [ ] Wide-corpus smoke test: batch-load a few hundred lutemusic.org files (importer must never crash; count and classify warnings). Keep it as a repeatable script in `scripts/`.

Editing — alpha quality:
- [ ] Reflow/transform undo integration: use compound undo grouping for multi-step commands (transpose/retune/reflow).
- [ ] Manual alpha pass of the full edit loop on a real piece (enter, correct, save, export, reopen); file each paper cut found here.

Publication mechanics:
- [ ] Add a screenshot or asciicast to README (the first thing visitors look at).
- [ ] Fill `[project.urls]` in pyproject.toml with the repository URL; verify the `oud` name is free on PyPI before any package release (rename the package if taken).
- [ ] Decide whether the existing git history (personal email in commits) is fine to publish; rewriting or squashing history is only practical before the repo goes public.
- [ ] First push checklist: commit `uv.lock`, `.github/workflows/ci.yml`, `lutemusic/README.md`; confirm CI green on ubuntu + macos.

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
