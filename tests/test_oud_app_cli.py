from __future__ import annotations

import curses
import os
from dataclasses import dataclass, field

import pytest

from oud import app as oud_app
from oud.core.model import Bar, Piece


def test_main_defaults_to_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str, bool]] = []

    def fake_wrapper(func, path, config, read_only):
        calls.append((func, path, config, read_only))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main([]) == 0
    assert calls == [(oud_app._main, None, oud_app.CONFIG_PATH, False)]


def test_main_with_path_opens_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str, bool]] = []

    def fake_wrapper(func, path, config, read_only):
        calls.append((func, path, config, read_only))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main(["examples/example.ft3"]) == 0
    assert calls == [(oud_app._main, "examples/example.ft3", oud_app.CONFIG_PATH, False)]


def test_main_with_config_then_path_opens_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str, bool]] = []

    def fake_wrapper(func, path, config, read_only):
        calls.append((func, path, config, read_only))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main(["--config", "cfg.toml", "examples/example.ft3"]) == 0
    assert calls == [(oud_app._main, "examples/example.ft3", "cfg.toml", False)]


def test_main_with_readonly_flag_opens_tui_in_viewer_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str, bool]] = []

    def fake_wrapper(func, path, config, read_only):
        calls.append((func, path, config, read_only))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main(["--readonly", "examples/example.ft3"]) == 0
    assert calls == [(oud_app._main, "examples/example.ft3", oud_app.CONFIG_PATH, True)]


def test_main_tui_subcommand_accepts_readonly_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str, bool]] = []

    def fake_wrapper(func, path, config, read_only):
        calls.append((func, path, config, read_only))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main(["tui", "--readonly", "examples/example.ft3"]) == 0
    assert calls == [(oud_app._main, "examples/example.ft3", oud_app.CONFIG_PATH, True)]


def test_main_dispatches_convert(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str, str]] = []

    def fake_convert(path_in: str, path_out: str, config: str) -> int:
        captured.append((path_in, path_out, config))
        return 7

    monkeypatch.setattr(oud_app, "_cmd_convert", fake_convert)
    assert oud_app.main(["convert", "in.ft3", "out.tab"]) == 7
    assert captured == [("in.ft3", "out.tab", oud_app.CONFIG_PATH)]


def test_main_dispatches_ascii(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str, str | None, str | None]] = []

    def fake_ascii(path: str, config: str, output: str | None, bars: str | None = None) -> int:
        captured.append((path, config, output, bars))
        return 9

    monkeypatch.setattr(oud_app, "_cmd_ascii", fake_ascii)
    assert oud_app.main(["ascii", "in.ft3", "-o", "out.txt"]) == 9
    assert captured == [("in.ft3", oud_app.CONFIG_PATH, "out.txt", None)]


def test_main_dispatches_ascii_with_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str, str | None, str | None]] = []

    def fake_ascii(path: str, config: str, output: str | None, bars: str | None = None) -> int:
        captured.append((path, config, output, bars))
        return 11

    monkeypatch.setattr(oud_app, "_cmd_ascii", fake_ascii)
    assert oud_app.main(["ascii", "in.ft3", "--bars", "1:2"]) == 11
    assert captured == [("in.ft3", oud_app.CONFIG_PATH, None, "1:2")]


def test_main_dispatches_ascii_with_bars_expr(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str, str | None, str | None]] = []

    def fake_ascii(path: str, config: str, output: str | None, bars: str | None = None) -> int:
        captured.append((path, config, output, bars))
        return 12

    monkeypatch.setattr(oud_app, "_cmd_ascii", fake_ascii)
    assert oud_app.main(["ascii", "in.ft3", "bars=2:4"]) == 12
    assert captured == [("in.ft3", oud_app.CONFIG_PATH, None, "2:4")]


def test_main_help_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ex:
        oud_app.main(["--help"])
    assert ex.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "usage:" in output
    assert "ascii" in output
    assert "convert" in output
    assert "tui" in output


def test_main_version_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ex:
        oud_app.main(["--version"])
    assert ex.value.code == 0
    assert "oud " in capsys.readouterr().out


def test_cmd_ascii_uses_tui_render_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _State:
        screen_width = 0
        screen_height = 0

    def _fake_init(_path: str, *, config_path: str) -> _State:
        assert config_path == "cfg.toml"
        return state

    state = _State()
    monkeypatch.setattr(oud_app, "init_state", _fake_init)
    monkeypatch.setattr(oud_app, "render_ascii_snapshot", lambda _s: "VIEW\n")
    monkeypatch.setattr(
        oud_app.shutil,
        "get_terminal_size",
        lambda _fallback: os.terminal_size((88, 33)),
    )
    assert oud_app._cmd_ascii("in.ft3", "cfg.toml", None) == 0
    assert state.screen_width == 88
    assert state.screen_height == 33
    assert capsys.readouterr().out == "VIEW\n"


def test_cmd_ascii_writes_file_from_tui_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class _State:
        screen_width = 0
        screen_height = 0

    def _fake_init(_path: str, *, config_path: str) -> _State:
        assert config_path == "cfg.toml"
        return state

    state = _State()
    out = tmp_path / "out.txt"
    monkeypatch.setattr(oud_app, "init_state", _fake_init)
    monkeypatch.setattr(oud_app, "render_ascii_snapshot", lambda _s: "FRAME\n")
    monkeypatch.setattr(
        oud_app.shutil,
        "get_terminal_size",
        lambda _fallback: os.terminal_size((80, 24)),
    )
    assert oud_app._cmd_ascii("in.ft3", "cfg.toml", str(out)) == 0
    assert out.read_text(encoding="utf-8") == "FRAME\n"


def test_cmd_ascii_bars_range_slices_piece(monkeypatch: pytest.MonkeyPatch) -> None:
    @dataclass
    class _State:
        piece: Piece
        overrides: dict[tuple[int, int, int], str] = field(default_factory=dict)
        durations: dict[tuple[int, int, int], int] = field(default_factory=dict)
        dotted: set[tuple[int, int]] = field(default_factory=set)
        annotations: dict[tuple[int, int], str] = field(default_factory=dict)
        ornaments: dict[tuple[int, int], str] = field(default_factory=dict)
        slurs: list[tuple[int, int, int]] = field(default_factory=list)
        ties: list[tuple[int, int, int]] = field(default_factory=list)
        holds: list[tuple[int, int, int]] = field(default_factory=list)
        screen_width: int = 0
        screen_height: int = 0

    state = _State(
        piece=Piece(title="T", bars=[Bar(), Bar(), Bar()], strings=6),
        overrides={(0, 0, 0): "a", (1, 0, 0): "b", (2, 0, 0): "c"},
    )
    captured: dict[str, int] = {}

    def _fake_init(_path: str, *, config_path: str) -> _State:
        assert config_path == "cfg.toml"
        return state

    def _fake_render(st) -> str:
        captured["bars"] = len(st.piece.bars)
        captured["overrides"] = len(st.overrides)
        return "SLICE\n"

    monkeypatch.setattr(oud_app, "init_state", _fake_init)
    monkeypatch.setattr(oud_app, "render_ascii_snapshot", _fake_render)
    monkeypatch.setattr(
        oud_app.shutil,
        "get_terminal_size",
        lambda _fallback: os.terminal_size((80, 24)),
    )
    assert oud_app._cmd_ascii("in.ft3", "cfg.toml", None, "2:3") == 0
    assert captured == {"bars": 2, "overrides": 2}
