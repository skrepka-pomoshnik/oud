# about_project

Technical overview of the oud codebase.

## Goals
- Curses TUI editor for Renaissance lute tablature.
- Vim-like controls with optional casual keyset.
- FT3/TAB import, ASCII export, LilyPond export, MIDI export/playback.
- Minimal deps, Unix-friendly structure, easy to maintain.

## Runtime Targets
- Python >= 3.10 (see pyproject.toml).
- macOS/Linux terminals (curses).

## Repository Layout
- `app.py`                Main entrypoint + wiring (thin app glue).
- `cli.py`                CLI entrypoint (if used).
- `core/`                 File formats + parsing helpers.
- `editor/`               Editor logic (state, ops, command helpers).
- `tui/`                  Input + viewport adapters (curses oriented).
- `ui/`                   Rendering and ASCII layout helpers.
- `exports/`              Exporters (tab/ly/midi).
- `settings.py`           Config load/save + defaults.
- `config.toml`           Local config (user settings).
- `tests/`                Pytest suite.
- `scripts/`              Quality scripts.

## Editor Layering
- **State**: `editor/state.py` stores cursor, piece, durations, overrides, etc.
- **Ops**: `editor/edit_ops.py`, `editor/ops.py`, `editor/bar_ops.py` handle edits.
- **Command ops**: `editor/command_ops.py` owns `:cmd` handlers + helpers.
- **Undo**: `editor/undo_ops.py` applies undo/redo actions.
- **Load**: `editor/load_ops.py` loads pieces and parsed data from disk.
- **Verify**: `editor/verify_ops.py` validates bar duration vs time signature.
- **Undo**: `editor/undo_ops.py` applies undo/redo actions.
- **Keymap**: `editor/keymap.py` centralizes movement keys (vim/casual).

## TUI Layering
- **Input**: `tui/input.py` parses command/search keystrokes.
- **Controller**: `tui/controller.py` wires curses keycodes into editor actions.
- **Viewport**: `tui/viewport.py` handles scroll/visibility logic.
- **Render**: `ui/render.py` builds screen text; `ui` should not mutate state.

## Data Flow (high-level)
1) `app.py` loads config + piece and builds `EditorState`.
2) Input -> `tui/controller.py` -> `editor/actions.py`.
3) Actions mutate `EditorState` via ops + undo/redo tracking.
4) `ui/render.py` renders the current state.

## Commands
- Command parsing via `tui/commands.py` registry.
- App wrappers delegate to `editor/command_ops.py` for actual behavior.

## Settings
- `settings.py` merges defaults with `config.toml`.
- Relative config path resolves to `./config.toml` or `~/.config/oud/config.toml`.

## Exports
- `exports/export_tab.py`  ASCII/tab export.
- `exports/lilypond.py`    LilyPond export + optional PDF compile.
- `exports/midi.py`        MIDI export and playback command building.

## Testing
- `pytest` suite in `tests/`.
- Core behavior and editor actions are tested; target 100% coverage for TUI/UI.

## Linting
- `ruff` for lint; `ty` for type checking (optional).
- `ruff.toml` sets lint rules; `scripts/quality.sh` runs checks.

## Technical Notes
- Keep core/editor logic free from curses imports.
- Prefer moving app glue into `editor/` or `tui/` modules.
- Record completed work in `DONE.md`.
