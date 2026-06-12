# DONE

Technical change log. Keep short, append newest on top.

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
- Finalized ASCII save parity check: `:wascii` output is validated against framebuffer snapshot in `tests/test_tui_commands_exec.py`.
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
