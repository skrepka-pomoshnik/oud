# DONE

Technical change log. Keep short, append newest on top.

## 2026-02-07
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
