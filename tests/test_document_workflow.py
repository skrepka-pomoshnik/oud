from __future__ import annotations

from pathlib import Path

import pytest

from oud.editor.core.document import DocumentMode
from oud.editor.core.feedback.messages import MessageLevel, infer_message_level
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write_ascii
from oud.editor.services.status import status_line
from oud.presentation.tui.commands import apply_command
from oud.presentation.tui.input import handle_command
from petrucci.rendering.primitives.helpers import render_help
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from tests.helpers_keyscript import press_keys

PURE_FT3 = "tests/fixtures/ft3/corpus/01_unquiet_thoughts/unquiet_thoughts_T.ft3"
MIXED_FT3 = "tests/fixtures/ft3/corpus/can_she_excuse.ft3"
DUET_FT3 = "tests/fixtures/ft3/corpus/willoughby_duet.ft3"
VOCAL_ONLY_FT3 = "tests/fixtures/ft3/corpus/01_unquiet_thoughts/unquiet_thoughts_4-part.ft3"
TAB_FILE = "tests/fixtures/tab/minimal_score.tab"


def _submit_command_path(state, path: Path, config_path: str) -> None:
    def apply(current, command: str) -> None:
        apply_command(current, command, config_path)

    for char in str(path):
        handle_command(state, ord(char), apply)
    handle_command(state, 10, apply)


def test_ft3_document_classification_is_conservative(tmp_path: Path) -> None:
    config = str(tmp_path / "config.toml")

    projection = init_state(PURE_FT3, config_path=config)
    assert projection.document_mode is DocumentMode.IMPORTED_PROJECTION
    assert projection.read_only is False
    assert projection.write_path is None
    assert projection.visible_message == ""

    mixed = init_state(MIXED_FT3, config_path=config)
    assert mixed.document_mode is DocumentMode.IMPORTED_READ_ONLY
    assert mixed.read_only is True
    assert mixed.visible_message == ""
    assert mixed.visible_message_level is MessageLevel.INFO

    duet = init_state(DUET_FT3, config_path=config)
    assert duet.document_mode is DocumentMode.IMPORTED_READ_ONLY
    assert duet.read_only is True

    vocal_only = init_state(VOCAL_ONLY_FT3, config_path=config)
    assert vocal_only.document_mode is DocumentMode.IMPORTED_READ_ONLY
    assert vocal_only.read_only is True

    tab = init_state(TAB_FILE, config_path=config)
    assert tab.document_mode is DocumentMode.NATIVE
    assert tab.read_only is False
    assert tab.path == TAB_FILE
    assert tab.write_path == TAB_FILE


def test_first_ft3_write_uses_a_sibling_tab_default(tmp_path: Path) -> None:
    config = str(tmp_path / "config.toml")
    source = tmp_path / "source.ft3"
    source.write_bytes(Path(PURE_FT3).read_bytes())
    state = init_state(str(source), config_path=config)
    state.modified = True

    apply_command(state, "w", config)
    assert state.mode == "command"
    assert state.cmdline == f"w {source.with_suffix('.tab')}"
    handle_command(state, 10, lambda current, command: apply_command(current, command, config))

    assert state.mode == "normal"
    assert state.modified is False
    assert state.path == str(source)
    assert state.write_path == str(source.with_suffix(".tab"))
    assert source.with_suffix(".tab").exists()


def test_key_driven_ft3_save_as_keeps_source_and_reuses_target(tmp_path: Path) -> None:
    config = str(tmp_path / "config.toml")
    target = tmp_path / "projection.tab"
    state = init_state(PURE_FT3, config_path=config)
    source = state.path
    state.modified = True

    apply_command(state, f"w {target}", config)

    assert target.exists()
    assert state.path == source
    assert state.write_path == str(target)
    assert state.modified is False
    assert state.settings["filepath"] == source
    assert state.settings["writepath"] == str(target)

    reopened = init_state(str(target), config_path=config)
    assert reopened.document_mode is DocumentMode.NATIVE
    assert reopened.path == str(target)
    assert reopened.write_path == str(target)

    state.modified = True
    apply_command(state, "w", config)
    assert state.mode == "normal"
    assert state.modified is False
    assert state.write_path == str(target)


@pytest.mark.parametrize("command", ["wq", "x"])
def test_write_quit_prefills_sibling_destination_before_write(
    tmp_path: Path,
    command: str,
) -> None:
    config = str(tmp_path / "config.toml")
    source = tmp_path / "source.ft3"
    source.write_bytes(Path(PURE_FT3).read_bytes())
    target = source.with_suffix(".tab")
    state = init_state(str(source), config_path=config)
    state.modified = True

    apply_command(state, command, config)
    assert state.mode == "command"
    assert state.cmdline == f"{command} {target}"
    with pytest.raises(SystemExit):
        apply_command(state, state.cmdline, config)
    assert target.exists()
    assert state.modified is False


def test_new_target_requires_overwrite_confirmation(tmp_path: Path) -> None:
    config = str(tmp_path / "config.toml")
    target = tmp_path / "existing.tab"
    target.write_text("keep me\n", encoding="utf-8")
    state = init_state(None, config_path=config)
    state.modified = True

    apply_command(state, f"w {target}", config)
    assert target.read_text(encoding="utf-8") == "keep me\n"
    assert state.modified is True
    assert "repeat write" in state.message

    apply_command(state, f"w {target}", config)
    assert target.read_text(encoding="utf-8") != "keep me\n"
    assert state.modified is False
    assert state.write_path == str(target)


def test_mixed_ft3_blocks_editing_but_allows_ascii_export(tmp_path: Path) -> None:
    config = str(tmp_path / "config.toml")
    output = tmp_path / "view.txt"
    state = init_state(MIXED_FT3, config_path=config)

    press_keys(state, ["i", "a", 27])
    assert state.modified is False
    assert state.overrides == {}

    apply_command(state, f"wa {output}", config)
    assert output.exists()


def test_ascii_export_does_not_mark_score_saved(tmp_path: Path) -> None:
    state = init_state(None, config_path=str(tmp_path / "config.toml"))
    state.modified = True

    cmd_write_ascii(state, str(tmp_path / "snapshot.txt"))

    assert state.modified is True
    assert state.write_path is None
    assert state.message.startswith("Exported ASCII")


def test_status_keeps_identity_mode_and_target_visible_at_80_columns(tmp_path: Path) -> None:
    state = init_state(PURE_FT3, config_path=str(tmp_path / "config.toml"))
    state.screen_width = 80
    state.modified = True
    target = tmp_path / "edited.tab"
    apply_command(state, f"w {target}", state.config_path)
    state.modified = True

    line = status_line(state)

    assert "unquiet_thoughts_T.ft3*" in line
    assert "FT3 EDIT:edited.tab" in line
    assert "bar:1" in line
    assert "str:1" in line
    assert len(line) <= 80


def test_visible_help_drives_a_safe_first_score_workflow(tmp_path: Path) -> None:
    screen = FrameBuffer(24, 80)
    render_help(screen, "help  j/k scroll  q close", 0, 0)
    visible_help = "\n".join(line.rstrip() for line in screen.snapshot().lines[:-1])

    assert "Open/create  oud [FILE] / oud" in visible_help
    assert "Open here  :e FILE" in visible_help
    assert "Enter note   i, type fret a-t or 0-9, then Esc" in visible_help
    assert "Undo         u" in visible_help
    assert "Save       :w [FILE.tab]" in visible_help
    assert "Quit         :q" in visible_help
    assert "Discard    :q!" in visible_help

    config = str(tmp_path / "config.toml")
    target = tmp_path / "first-score.tab"
    state = init_state(None, config_path=config)
    press_keys(state, ["i", "a", 27])
    assert state.overrides == {(0, 0, 0): "a"}
    press_keys(state, ["u"])
    assert state.overrides == {}

    apply_command(state, f"w {target}", config)
    assert target.exists()
    assert state.write_path == str(target)
    assert state.modified is False
    with pytest.raises(SystemExit):
        apply_command(state, "q", config)


def test_read_only_focus_uses_status_without_redundant_notice(tmp_path: Path) -> None:
    state = init_state(MIXED_FT3, config_path=str(tmp_path / "config.toml"))
    state.screen_width = 80

    assert state.persistent_notice == ""
    assert state.visible_message == ""

    line = status_line(state)
    assert "[FT3 VIEW]" in line
    assert "focus:" in line


def test_message_levels_classify_user_facing_results() -> None:
    assert infer_message_level("Wrote TAB score.tab") is MessageLevel.SUCCESS
    assert infer_message_level("Import warning: unsupported record") is MessageLevel.WARNING
    assert infer_message_level("Write failed: permission denied") is MessageLevel.ERROR
    assert infer_message_level("Save As .tab; source unchanged") is MessageLevel.CONFIRM
    assert infer_message_level("Focus: Melody") is MessageLevel.INFO
