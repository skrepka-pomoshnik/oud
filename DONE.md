# DONE

Technical change log. Keep short, append newest on top.

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
