# DONE

Technical change log. Keep short, append newest on top.

## 2026-07-19
- Added a fourth fixed, one-time 63-file FT3 manifest with no URL or digest
  overlap, bringing the random compatibility corpus to 263 files. All 63 new
  files load and pass the semantic audit without warnings or unresolved values;
  two additional published PDFs confirm under-`v` and combined fingering bits.
- Split normal-mode dispatch, Petrucci staff/rhythm/system rendering, FT3 import,
  LilyPond and MIDI export, and four oversized test modules by responsibility.
  The enforced debt baseline is now 158 complex functions and one oversized
  module; the remaining work is tracked as P2 rather than a release blocker.
- Validation: no tracked FT3 payloads, architecture and isolated Petrucci wheel
  gates, Ruff, Ruff format, Ty, and 1,300 tests pass with one Linux-skipped
  Darwin test at 86.74% coverage; 300/300 local corpus files load without
  warnings.
- Split both 2K-line Petrucci modules by ownership. `render_system.py` is now
  671 lines and `notation_layout.py` 801; every extracted rendering/layout
  module is below 1,000 lines. The former complexity-162 renderer is now 70,
  and the exact debt baseline fell to 166 findings and nine oversized modules.
- Removed game-result policy from Petrucci: no overlay/result enums, feedback
  lane, confidence, or hit/miss styling remains. Semantic roles, IDs, clipping,
  and `cells_for()` let consumers decorate their own states after typesetting.
- Added horizontal viewport translation with separate paint and layout widths.
  Moving `x_offset` repaints one cached layout while preserving translated
  event-cell identity; pretty and safe modes preserve identical semantic maps.
- Moved viewport and prompt-history state into `oud.editor` and made the debt
  gate reject `curses` or `oud.tui` imports from editor, importer, exporter,
  playback, plugin, and Petrucci modules.
- Made `petrucci` a real top-level typed package in the Oud wheel and removed
  the ambiguous `oud.core` grouping. FT3/TAB/MusicXML import, playback timing,
  plugin records, and editor tablature assignment now have explicit package
  owners; no old-path forwarding modules remain.
- Added exact source-neutral `FlowEvent` adaptation for external consumers,
  including chords/rests, voices, lyrics, unusual meters, overlapping active
  events, measure-crossing splits and ties, source-to-segment identity, and
  precomputed-layout painting for playback updates.
- Added an isolated wheel consumer gate proving the public `petrucci` surface
  imports without `oud` or curses. A 256-event benchmark measured about 177 ms
  cold layout and 9.8 ms cached-layout plus repaint at 80x24 on this host.
- Enforced complexity 7 for new code and checked all existing suppressions into
  an exact non-growth debt baseline: 167 complex functions and seven oversized
  production modules plus four oversized test modules. CI now rejects new or
  growing complexity and 1,000-line module debt.
- Validation: architecture debt, isolated Petrucci wheel, Ruff, Ruff format,
  Ty, and 1,294 tests pass with one Darwin-only test skipped at 86.29% coverage;
  237/237 local FT3 corpus files load without warnings.
- Added a compact note/tablature typing workflow matrix derived from MuseScore's
  operation-and-score tests and LilyPond's one-feature regressions. Both key
  profiles now share French chord/rest/bass coverage; replacement retention,
  atomic undo/redo, and Italian two-digit save behavior are explicit.
- Added source-independent Petrucci decoding for Oud's editable tablature cells.
  Italian fret 10 round-trips as one note, while legacy TAB export rejects
  unrepresentable higher frets without creating a partial file.
- Added a third one-time, composer-stratified 50-score FT3 manifest. All 200
  fixed random scores pass the semantic audit; PDF evidence decoded left
  parentheses, under-fret hooks, a placement-layout record, and three score
  headings. External FT3 payloads remain ignored.
- Enabled bounded four-worker pytest execution with load-scope scheduling.
  Per-load text-record caching and single-pass line-feature checks reduced the
  200-score load benchmark from 38.9 to 25.1 seconds; the expanded no-coverage
  suite completes in 31.3 seconds locally.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,289 tests
  pass with one Darwin-only test skipped on Linux at 86.28% coverage; 237/237
  local corpus files load without warnings.
- Closed the Petrucci proper-score P0 gate. Dense independent voices use
  disjoint beam and cue lanes, whole-layout collision checks pass, narrow
  clipping retains event-owned markers, and structural plus ASCII text goldens
  cover 60, 80, and 120 columns.
- Preserved imported tuplets, grace notes, typed slurs, key/clef changes,
  irregular source timing, additional ornaments, and unaligned source lyric
  lines without guessing note onsets. All 15 notation-bearing files in the
  fixed 150-file corpus now adapt strictly.
- Routed vocal-only and focused mixed/polyphonic note or lyric staffs through
  canonical Petrucci rendering while preserving the default tablature path.
  Oud applies cursor and playback attributes after resolving stable source IDs,
  without moving score geometry or adding consumer state to Petrucci.
- Reduced `view_model.__all__` to its intentional public entry point; layout and
  rendering callers now import owned layout primitives directly.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,279 tests
  pass with one Darwin-only test skipped on Linux at 86.02% coverage; 187/187
  local corpus files load without warnings.
- Fixed the normal-mode count hang: numeric prefixes now saturate at 999,
  counted movement stops at boundaries or after one editable append, and
  read-only navigation cannot append bars. Page, staff-focus, and viewport
  counts execute as one bounded operation.
- Replaced rectangular duration/string probing with sparse duration change
  points and reused visual geometry within one counted motion. A 999-step,
  226-bar adversarial probe with million-index duration records completes in
  about 1-2 seconds locally instead of exceeding 30 seconds.
- Added regressions over both key profiles for every byte key and configured
  curses key after an oversized prefix, plus read-only append prevention,
  command-local geometry reuse, and billion-scale sparse duration coordinates.

## 2026-07-17
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,262 tests
  pass with one Darwin-only test skipped on Linux at 85.76% coverage; 187/187
  local corpus files load without warnings.
- Added a compact public Petrucci notation policy that can hide stems/beams and
  barlines and emit collision-safe written pitch labels.
- Preserved one logical onset for simultaneous voices while assigning
  deterministic visual lanes to common unison/second, rest, stem/flag, dynamic,
  same-verse lyric, and dense annotation conflicts. Monophonic score snapshots stay
  unchanged.
- Distinguished eighth, 16th, 32nd, and 64th rests in Unicode-pretty and
  ASCII-safe output. Expanded public-only neutral-host acceptance through
  repeated pitches, rests, cross-system ties, lyrics, compact output, resize,
  and active-system selection.
- Removed redundant new-score and read-only focus key hints from the persistent status area. Playback now follows the active score system by default, retains its viewport through rests, catches positions advanced during a slow full render, and remains disableable with `:set playbackscroll=off`.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,257 tests pass with one Darwin-only test skipped on Linux at 85.73% coverage; 187/187 local corpus files load without warnings.
- Separated FT3 meter codes from shared header flags. Nineteen records across 14 fixed-corpus files now retain their explicit meter; the published Gesualdo score confirms `0e 10` as a repeated `3/2` opening, and all four viol staffs adapt to canonical Petrucci notation.
- Stopped barline and empty notation records from promoting heuristic ASCII coordinate fragments into fake pitches. Relevant barline fragments remain typed control rows, while tablature payload bytes such as `_6(` no longer create synthetic notation staffs.
- Validation: no tracked FT3 payloads, both fixed 75-file semantic audits pass, Ruff, Ruff format, Ty, and 1,254 tests pass with one Darwin-only test skipped on Linux at 85.72% coverage; 187/187 local corpus files load without warnings.
- Added a second fixed 75-file Gerbode corpus with unique, previously unseen composer directories and no overlap with the first sample. All 150 fixed external files load without warnings and pass the semantic audit with no residual flags or unknown records; FT3 payloads remain ignored.
- Corrected lane-major mixed-score detection and the empty `0130` notation marker, so Berchem's 59-bar score maps to one tablature lane plus labeled alto and bass staffs instead of fragmented fake staffs. Typed empty layout records no longer produce unknown-staff warnings.
- Decoded and rendered PDF-confirmed courtesy accidentals (`8000` plus an accidental), editorial square brackets (`4000`), standalone tie continuation (`8000`), left apostrophe (`1600`), and the legacy open ninth-course form (`3c00`). Petrucci now carries courtesy, brackets, and imported ties through its public canonical model and semantic terminal frame.
- Added six FT3/PDF comparisons for the new corpus, bringing the documented matrix to 16 files, and bumped the alpha version to `0.2.0a2`.
- Validation: no tracked FT3 payloads, both fixed 75-file audits pass with zero unresolved semantics, 187/187 local corpus files load without warnings, Ruff, Ruff format, Ty, and 1,251 tests pass with one Darwin-only test skipped on Linux at 85.72% coverage. An isolated `0.2.0a2` wheel renders the new Petrucci courtesy-accidental and editorial-bracket semantics through its public API.
- Deepened the FT3-to-Petrucci adapter with per-voice timing, same-onset chord normalization, opposing polyphonic stems, cut time, repeats/endings, beams, fermatas, dynamics, and `+` ornaments. Meaningful lyrics remain strict; callers can explicitly select trustworthy note-only adaptation with `include_lyrics=False`.
- Added key-aware measure accidental state with natural cancellation and explicit/courtesy policies, distinct repeat forms, reserved ending/ornament/fermata lanes, and a complete public `EventLocation` map so external consumers can follow every canonical event across clipping, system scrolling, and resize.
- Removed Petrucci's eager curses import by keeping text attributes portable and translating them only in `CursesScreen`. An isolated wheel resolved all 64 public symbols and rendered a canonical score with `py.typed` present and no curses module loaded.
- Audited 15 representative real FT3 files without committing source payloads: 4 adapt strictly, 11 adapt in note-only mode, and the remaining 4 fail with explicit pitch or meter diagnostics. The four supported canonical scores retain 1,382 event locations across 60, 80, and 120 columns; only two events in the narrow Folle layout are explicitly clipped.
- Fixed Petrucci's narrow-layout identity contract: every canonical event ID remains in `ScoreLayout` even when its glyph cannot be placed, off-viewport events have no visible cells, and genuinely unknown IDs still fail explicitly.
- Reserved disjoint semantic rows for measure numbers, cross-system slurs/ties, dynamics, annotations, and lyrics. Caller decoration resolves exact cells by event ID without changing geometry; span endpoints and continuations use shaped ASCII-safe/Unicode glyphs instead of repeated fill characters.
- Moved MusicXML golden scratch output to pytest's isolated `tmp_path`, so tests no longer mutate the source fixture tree. Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,241 passed with one Darwin-only test skipped on Linux, 85.64% coverage, and 112/112 corpus files loaded without warnings.

## 2026-07-16
- Added Petrucci's source-independent standard-notation vertical slice: strict immutable score records with stable IDs and exact timing, measured system fitting, content-derived row budgets, semantic onset/layout elements, display-safe terminal painting, and cached layout independent of transient caller decoration.
- Added treble/bass notes and chords, rests, ledger lines, dots, stems, flags and beams, accidentals, conventional key-signature positions, barlines, tuplets, ties/slurs with cross-system segments, fermatas, dynamics, lyrics, ASCII/Unicode glyph policies, and exact event-owned cell geometry.
- Added a strict Oud note/lyric adapter and an independent consumer fixture that imports no Oud model. Built and installed the wheel in an isolated environment; public score rendering worked, `py.typed` was present, and importing `petrucci` did not initialize curses.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,223 passed with one Darwin-only test skipped on Linux, 85.54% coverage, 112/112 corpus files loaded without warnings, and an isolated built-wheel consumer smoke.

## 2026-07-13
- Prevented orphaned rhythm/staff rows by requiring a meaningful half-system before drawing a clipped preview; duet score view only adds complete paired systems. Dense bars forced onto their own system still fill the staff width. The TUI now drains up to 64 queued keys before one render, preventing delayed repeated movement after key release.
- Cached clean dynamic system plans across cursor-only frames while bypassing the cache for modified documents. Cursor-display regressions fell from about 95 seconds to 25 seconds locally, and representative frame time dropped from 0.20 seconds to 0.03-0.09 seconds.
- Made imported FT3 provenance complete and inspectable: `:info` lists bibliographic fields, source page/metadata, format, and every staff; `:notes` includes editorial text from all imported staffs; LilyPond headers/comments preserve the same metadata and source comments.
- Tightened FT3 score presentation against the published Dowland *A Fantasy*: systems use only their visible course height, the playback caret no longer reserves a row, opening systems retain more naturally sized bars, and every displayed system can carry an unbracketed source bar number.
- Removed stale playback highlights from cached base frames, reduced active playback polling to 10 ms, and resampled the MIDI clock after full score renders before drawing the current-note overlay.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,174 passed with one Darwin-only test skipped on Linux, 85.55% coverage, and 112/112 local corpus files loaded without warnings.
- Made casual controls functionally equivalent without key collisions: `d` moves right, `,` moves to the previous bar, `W/S` jump rendered rows, `Ctrl-Z/Ctrl-Y` undo/redo, and visual-mode movement no longer triggers Vim deletion.
- Rendered the next score system into any remaining terminal rows instead of hiding every system that does not fit completely; the status line and cursor-safe full-system viewport remain intact.
- Stopped stretching sparse final, manual-break, and explicitly capped systems across empty width. Width-limited systems still justify, configured editing grids remain stable, and multi-digit frets plus inline source marks retain collision-safe spacing.

## 2026-07-12
- Closed all five semantic failures in the fixed 75-file expansion. Decoded comma, apostrophe, smile, and caret ornaments; separated standard-note musical/layout fields; preserved chord onsets and source voices; and mapped La Couperin's two notation voices to one 77-bar bass-viol staff. The 75-file audit now has zero residuals, unknown records, or warnings.
- Manually compared 17th Century Grounds and La Couperin with their published PDFs, bringing the documented FT3/PDF matrix to ten files.
- Removed all Gerbode FT3 payloads and decoded dumps from the Git index, ignored FT3 suffixes repository-wide, added a CI publication guard, and retained only attribution plus URL/SHA-256 manifests. Added a deterministic fetcher that refuses unsafe URLs, path traversal, checksum drift, and implicit replacement.
- Expanded FT3 compatibility coverage with a one-time 75-file selection fixed in `corpus/ft3-random-75.json`. All 75 load without crashing; the five semantic failures and Couperin structural warning are bounded by regression tests and recorded in `TODO.md`/`docs/ft3-parity.md`.
- Removed discarded exponential string-assignment searches from LilyPond pitch emission. The 226-bar Buxtehude fixture exports in about 0.02 seconds instead of 15.1 seconds with byte-identical output; the full coverage gate fell from 7:06 to 3:43.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,157 passed with one Darwin-only test skipped on Linux, 85.33% coverage, and 112/112 local corpus files loaded without warnings.
- Closed the remaining release-usability P0 items: the first 80x24 help page now gives a complete open/create, note entry, undo, safe save, and quit path, backed by an executable first-score regression.
- Added a macOS-only PTY regression around the real curses loop. It verifies 80x24 -> 120x40 resize preserves the score cursor, source filename, modified marker, imported-projection mode, and TAB write target while keeping cursor and status on separate rows.
- Raised the enforced line/branch coverage floor to 85%, removed the unreachable partial preset converter superseded by the canonical pitch-preserving transform, and covered screenshot/snapshot release tools, corpus failures, the FT3 audit CLI, and plugin error workflows.
- Validation: Ruff, Ruff format, Ty, 1,144 passed with one Darwin-only test skipped on Linux, the 85% coverage gate (85.40%), and the 37-file corpus smoke check all pass locally; the FT3 semantic audit separately passes 36/36 files with zero unresolved records or values.
- Closed the bundled Gerbode FT3 semantic audit: 36/36 files now have zero residual note bits, vocal bits, unknown source records, or import warnings. Typed source provenance is stored once on `ImportedScore`, separate from decoded staff bars.
- Corrected FT3 boundary semantics from PDF evidence (`0x20` first ending, `0x40` second ending), decoded vocal beams/fermatas, Ich annotation groups, arpeggio segments and right-side `x` ornaments, and Passacaglia's editorial appendix page/section records.
- Completed polyphonic viewer/export behavior: every source voice has a complete logical bar map, staff focus changes the rendered voice, LilyPond emits all standard staffs with beams/fermatas, and vocal-only scores now drive MIDI and playback timelines.

## 2026-07-11
- Added a reproducible FT3 residual/raw-record audit and manually compared representative solo, mixed, duet, and three-verse vocal fixtures with Gerbode's published PDFs. Structural content agrees; exact source systems, pages, and edition engraving remain explicit P0 gaps. Decoded the real compositional `0x3500` barre plus left-finger value without residual loss.
- Added explicit read-only staff focus: `j/k` cycles projected Tab/Melody/Lyrics lanes, duet focus maps to the corresponding source staff bar, and the active focus remains visible in status. Added typed info/success/warning/error/confirmation messages with distinct portable terminal attributes.
- Fixed the macOS CI quality environment by declaring `pytest-cov` in the uv dev group and locking coverage dependencies. Applied the repository's Ruff format baseline and documented the formatter-required `COM812` exception; Ruff, format, Ty, 1109 tests, the 82.50% coverage gate, and the 37-file corpus smoke pass locally.
- Removed the root `app.py`/`cli.py` launchers and obsolete `oud.cli`; `oud` -> `oud.app:main` is now the single command path. Removed the former `oud.core` and `oud.ui` Petrucci aliases, migrated tests/scripts to canonical imports, and retained only real parser/domain modules plus the curses adapter.
- Closed the compatibility-layer static-analysis debt: Ruff and Ty pass, 1101 tests pass, and the local corpus smoke test loads 37/37 files with no errors or warnings.
- Added explicit document modes and separate source/write-target state. Tab-only FT3 opens as an editable projection with explicit Save As; mixed, vocal-only, and duet FT3 opens read-only so visible non-TAB layers cannot be lost.
- Replaced implicit `name.ft3.tab` writes with a shared `:w`/`:wq`/`:x` Save As flow, confirmed overwrite handling, truthful modified state, and source-preserving target reuse. ASCII export no longer marks a score saved.
- Added persistent filename, modified, document-mode, write-target, bar, and string/staff context; added acknowledgeable notices and an 80-column first-run/safety presentation.
- Added key-driven workflow regressions for save/cancel/overwrite/reopen and solo, mixed, vocal-only, duet, and TAB classification.
- Reframed the active roadmap around two user-facing alpha blockers: trustworthy FT3 edit/save semantics and persistent workflow context, with explicit macOS interaction tests and release acceptance criteria. Removed completed checklist entries from `TODO.md`; their outcomes remain recorded below.

## 2026-07-10
- Extracted the canonical score model and complete tab/vocal/note character-cell renderer into `petrucci`, with a reusable `typeset_piece`/`typeset_text` API and compatibility aliases for former `oud.core`/`oud.ui` paths.
- Improved import UX: malformed TAB files no longer silently replace an open score, partial TAB bars survive missing end markers, warning summaries point to `:info`, and all import warnings remain visible there.
- Closed the bundled FT3 viewer blockers: multipart note markers crossing the raw header boundary become note staves, unknown text remains visible as comments, observed bar headers are classified, vocal/multipart playback mapping is covered, and narrow multi-verse scores retain a visible bar.
- Closed the remaining FT3 backlog: typed the final score-settings record, eliminated unknown staffs across the bundled corpus, published duet cursor/playback maps, aligned sparse imported lyrics by source bar, and exported all supported non-tab staff variants to LilyPond.
- Finished automatable release polish: project URLs and alpha metadata, a renderer-generated README screenshot, a documented release procedure, and an audited decision to retain the existing non-personal commit metadata.
- Added `scripts/corpus_smoke.py` for local or bounded live lutemusic.org batches; it continues after per-file failures, classifies importer warnings, supports JSON output, and is wired into macOS CI. Release pass: 250/250 live files and 36/36 bundled files loaded with zero errors or warnings.
- Grouped transpose, retune, and reflow into explicit compound undo entries with regressions.
- Added a real-piece alpha workflow regression covering enter, correction, TAB save, MIDI/LilyPond export, and reopen.

## 2026-06-13
- Fixed `:play`/`M` playback regression: without an explicit end bar it again plays from the start bar to the end of the piece (the loop-range refactor had collapsed it to a single bar) — this was the "no sound on Linux" report.
- Made visual h/l movement track the rendered cursor exactly: the renderer publishes per-bar logical→display column maps (`cursor_display_maps`), movement steps one display cell per press and lands on each cell's note column (regressions in `tests/test_cursor_display_sync.py`).
- Fixed motions treating FT3 chord-index duration records as grid columns (`_note_cols`), which mistargeted note snapping in unflattened chord bars.
- Synced viewport block height with the renderer (always-reserved second stem row, melody staff for lyric-only pieces) and editor system planning with renderer minimum bar widths (time-cue padding, event gaps) — the cursor can no longer land on never-rendered systems.
- Added `:dark` / `:light` commands and `:set theme=auto|dark|light`: explicit fg/bg color pair plus painted window background for light-background terminals.

## 2026-06-12
- Publication prep: scrubbed personal absolute paths from DOCS.md/FT3.md/config.toml/tests, resolved .gitignore vs tracked-file conflicts, added lutemusic.org CC BY-NC-SA 4.0 attribution (`lutemusic/README.md`), added GitHub Actions CI (ruff + pytest on ubuntu/macos), and added a pytest/ruff dev dependency group with `uv.lock`.
- Moved to Python 3.11+ with stdlib `tomllib`; project now has zero runtime dependencies.
- Fixed light-theme low contrast: high-contrast mode uses bold on the terminal's default colors instead of forcing a white foreground.
- Added `:help` command that pages help text through less with TUI suspend/resume, plus a dispatch regression test.
- Removed scratch `examples/test.tab`; corpus check: all 43 local lutemusic.org files import without crashes (13 with partial-decode warnings).
- Reordered TODO.md for publication: P0 fix-now, P1 publication blockers (viewer coverage + alpha editing + mechanics), features pushed to P2+.
- Completed easy TODO cleanup: slimmed the `command_ops.py` compatibility facade, added loop playback for visual/current ranges, covered comment/gridflag/reflow tools, and added a dense synthetic snippet regression.
- Completed P1 edit foundation work: added cursor/deletable bar range helpers, routed normal-mode bar yank/delete through explicit range operations, and switched normal-mode movement to pure motion targets.
- Finished remaining P0 edit-mode cleanup: unified edit chord slots on raw chord positions, removed dead insert chord branches, made insert cursor snapping predictable, centralized post-insert advance, added visual delete/change, and recorded the short-term dual-representation decision.
- Fixed additional P0 edit-mode bugs: exact destructive chord targeting, file-open state reset, stave-break delete shifting, gliss/mark bar reindexing, count handling, and undo/redo cursor + clean modified-state restoration.
- Fixed first P0 edit-mode bugs: removed French lowercase duration-letter aliases, preserved insert-mode quit fallthrough, recorded chord flattening in undo, and grouped insert keystroke mutations into single undo steps.

## 2026-03-13
- Decoded `note-staff-raw` FT3 bars into imported `note` staffs instead of leaving them in generic unknown import buckets.
- Decoded `note-lyric-raw` FT3 bars into imported `note` + `lyrics` staffs.
- Split `barline-raw` FT3 material into a dedicated imported `barline` staff.
- Kept FT3 imported bar context (`time_sig`, `barline`, `repeat`) on imported score content.
- Reduced redundant TUI redraw during playback by only re-rendering on actual playback/message/resize changes.
- Tightened bottom vocal layout by removing the extra spacer row between tablature and note staff while keeping playback marker visibility.

## 2026-02-07
- Added reprise marker support end-to-end: `:repeat` now accepts structural + cue variants (`both`, `dc/ds`, `fine/coda`, `*alfine/*alcoda`) with normalization and limit handling in `oud/editor/notation_ops.py`.
- Added reprise export/render coverage: repeat cue marks are emitted in LilyPond export and tested in `tests/test_lilypond.py`.
- Finalized ASCII save parity check: `:wascii` output is validated against framebuffer snapshot in `tests/test_tui_commands_media.py`.
- Implemented and tested bars-per-line behavior (`:set barsperline=<n>`, `0=auto`) with new layout/render tests (`tests/test_editor_layout.py`, `tests/test_ui_render_split.py`).
- Added new testing suites:
  - `tests/test_tui_prompt.py` (prompt/update behavior paths),
  - `tests/test_render_matrix.py` (spacing/style/bass/marker matrix scenarios).
- Ran full quality under `.venv`: `ruff`, `ty`, and `pytest` all pass (`322 passed`, coverage `80.60%`).
- Continued command-layer split: moved media/playback/export command helpers into `oud/editor/media_ops.py` (`cmd_midi`, `cmd_lilypond`, `cmd_pdf`, `cmd_play`, `cmd_midicmd`, `print_pdf`) with wrappers kept in `command_ops.py`.
- Continued command-layer split: moved score-edit operations (`yank/paste`, `cmd_bar`, `cmd_stave`, `cmd_chord`) into `oud/editor/score_ops.py` and kept wrappers in `command_ops.py`.
- Added direct tests for split modules in `tests/test_tool_and_load_ops.py` (`cmd_info`, `cmd_plugins`, `cmd_tool`, and basic `cmd_open` path cases).
- Continued command-layer split: moved `cmd_open` into `oud/editor/load_ops.py` with injected loader functions so test monkeypatch behavior stays unchanged.
- Continued command-layer split: extracted tool/view commands into `oud/editor/tool_ops.py` (`cmd_tool`, `cmd_info`, `cmd_plugins`) with wrappers retained in `oud/editor/command_ops.py`.
- Continued command-layer split: extracted notation/time/repeat/ornament helpers into `oud/editor/notation_ops.py` with compatibility wrappers in `oud/editor/command_ops.py`.
- Continued command-layer split: extracted file/source/ascii write handlers into `oud/editor/file_ops.py` and kept thin wrappers in `oud/editor/command_ops.py`.
- Kept compatibility for existing tests/monkeypatch paths by preserving public `command_ops` entrypoints.
- Re-ran full quality under `.venv`: `ruff`, `ty`, and `pytest` all pass (`233 passed`).
- Added `/Users/s/Documents/Python/frnm/DOCS.md` with full current feature/usage reference and workflows.
- Started command-layer split by extracting `:set` and style-conversion logic into `oud/editor/settings_ops.py` (slimming `command_ops.py`).
- Added Vim word-search parity in normal mode: `*`, `#`, `n`, `N`.
- Added `%` jump for tab matching (slur/tie/hold endpoints and repeat start/end markers).
- Added mark support in normal mode: `m{char}` to set, `' {char}` / `` ` {char}`` to jump.
- Added config-driven key remap hooks in keymap (e.g. `remap_move_left = "a"`).
- Added shared prompt history helpers and wired search prompt history navigation (`/` with up/down).
- Added Vim-like char find motions in normal mode: `f/F/t/T` with repeat `;` and reverse repeat `,`.
- Added MIDI playback animation timeline plumbing and live render highlight for current playback bar/column.
- Tightened spacing/layout rendering: compact bar width pass + per-system auto fit + dense flag spread to avoid overlap.

## 2026-01-30
- Moved all code into `oud/` package with root wrappers for `app.py` and `cli.py`.
- Updated imports/tests for `oud.*` package layout and plugin pathing.
- Folded `about_project.md` into `README.md` and removed the standalone file.
- Added TODO/DONE to `.gitignore`.

## 2025-02-14
- Moved help/info key handling into `tui/controller.py`.
- Added help/info bindings in `editor/keymap.py`.
- Moved help text into `core/help_text.py`.
- Completed layered architecture cleanup (core no longer depends on UI/TUI).
- UI rendering now depends on `core/view_model` only.
- Added help/info mode tests in `tests/test_tui_controller.py`.
- Added view model adapter for UI rendering (`core/view_model.py`).
- Added count bindings to `editor/keymap.py`.
- Moved render view-model helpers into `core/view_model.py`.
- Centralized normal action bindings in `editor/keymap.py`.
- Added `editor/init.py` to initialize editor state outside TUI.
- Centralized command/search mode key bindings in `editor/keymap.py`.
- Added insert-mode bindings table in `editor/keymap.py`.
- Moved curses main loop to `tui/loop.py` and slimmed `app.py`.
- Added UI adapter (`ui/adapter.py`) and removed curses dependency from `ui/render.py`.
- Centralized normal-mode key bindings in `editor/keymap.py`.
- Fixed settings loader import to avoid ty unresolved-import errors.
- Added Ctrl-C as a confirmed-quit path (matches q behavior).
- Added French duration digit mapping test coverage.
- Refactored command handlers into `editor/command_ops.py`.
- Moved verify logic into `editor/verify_ops.py`.
- Added `editor/load_ops.py` for file loading.
- Added `tui/viewport.py` and `tui/controller.py` for TUI wiring.
