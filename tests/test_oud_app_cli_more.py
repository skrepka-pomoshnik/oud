from __future__ import annotations

import curses
import os

import pytest

from oud import app as oud_app


def test_parse_bars_spec_errors() -> None:
    with pytest.raises(ValueError, match="empty bars range"):
        oud_app._parse_bars_spec("", 10)
    with pytest.raises(ValueError, match="START:END"):
        oud_app._parse_bars_spec("a:b", 10)
    with pytest.raises(ValueError, match="N or START:END"):
        oud_app._parse_bars_spec("bad", 10)
    with pytest.raises(ValueError, match="> 0"):
        oud_app._parse_bars_spec("0", 10)
    with pytest.raises(ValueError, match="start must be <="):
        oud_app._parse_bars_spec("3:1", 10)
    with pytest.raises(ValueError, match="past end"):
        oud_app._parse_bars_spec("20:21", 10)


def test_parse_bars_spec_valid_and_clamp() -> None:
    assert oud_app._parse_bars_spec("2", 10) == (1, 2)
    assert oud_app._parse_bars_spec("2:50", 5) == (1, 5)


def test_main_ascii_invalid_bars_expr(capsys: pytest.CaptureFixture[str]) -> None:
    rc = oud_app.main(["ascii", "x.ft3", "oops"])
    assert rc == 2
    assert "Invalid ascii argument" in capsys.readouterr().err


def test_main_ascii_invalid_bars_value(capsys: pytest.CaptureFixture[str]) -> None:
    rc = oud_app.main(["ascii", "x.ft3", "--bars", "0"])
    assert rc == 2
    assert "Invalid --bars" in capsys.readouterr().err


def test_main_unknown_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ex:
        oud_app.main(["unknown", "x"])
    assert ex.value.code == 2
    assert "usage:" in capsys.readouterr().err.lower()


def test_export_context_spacing_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oud_app, "load_settings", lambda _cfg: {"spacing": "oops"})
    monkeypatch.setattr(
        oud_app,
        "load_piece_data",
        lambda _p: ("piece", {}, {}, set(), 0),
    )
    settings, width, piece, overrides, durations, dotted = oud_app._export_context(
        "in.ft3",
        "cfg.toml",
    )
    assert settings["spacing"] == "oops"
    assert width >= 4
    assert piece == "piece"
    assert overrides == {}
    assert durations == {}
    assert dotted == set()


def test_cmd_convert_ascii_and_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        oud_app,
        "_export_context",
        lambda _in, _cfg: ({}, 8, "piece", {}, {}, set()),
    )
    monkeypatch.setattr(oud_app, "_cmd_ascii", lambda *_args, **_kwargs: 0)
    rc = oud_app._cmd_convert("in.ft3", "out.txt", "cfg.toml")
    assert rc == 0
    assert "Wrote out.txt" in capsys.readouterr().out

    rc = oud_app._cmd_convert("in.ft3", "out.unsupported", "cfg.toml")
    assert rc == 2
    assert "Unsupported output format" in capsys.readouterr().err


def test_cmd_convert_mxl(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        oud_app,
        "_export_context",
        lambda _in, _cfg: ({}, 8, "piece", {}, {}, set()),
    )
    monkeypatch.setattr(
        oud_app,
        "export_mxl",
        lambda path, *_args, **_kwargs: called.append(path) or f"Wrote {path}",
    )
    rc = oud_app._cmd_convert("in.ft3", "out.mxl", "cfg.toml")
    assert rc == 0
    assert called == ["out.mxl"]
    assert "Wrote out.mxl" in capsys.readouterr().out


def test_cmd_convert_pdf(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, list[str]] = {"export": [], "print": []}
    monkeypatch.setattr(
        oud_app,
        "_export_context",
        lambda _in, _cfg: ({}, 8, "piece", {}, {}, set()),
    )
    monkeypatch.setattr(
        oud_app,
        "export_lilypond",
        lambda path, *_args, **_kwargs: calls["export"].append(path) or f"Wrote {path}",
    )
    monkeypatch.setattr(
        oud_app,
        "print_lilypond_pdf",
        lambda ly_path, out_base: calls["print"].append(f"{ly_path}|{out_base}") or "Printed out.pdf",
    )
    rc = oud_app._cmd_convert("in.ft3", "out.pdf", "cfg.toml")
    assert rc == 0
    assert calls["export"] == ["out.ly"]
    assert calls["print"] == ["out.ly|out"]
    out = capsys.readouterr().out
    assert "Wrote out.ly" in out
    assert "Printed out.pdf" in out


def test_main_tui_no_path_when_only_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str | None, str]] = []

    def fake_wrapper(func, path, config):
        calls.append((func, path, config))
        return 0

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    assert oud_app.main(["--config", "cfg.toml"]) == 2
    assert calls == []


def test_cmd_ascii_sets_terminal_size(monkeypatch: pytest.MonkeyPatch) -> None:
    class _State:
        def __init__(self) -> None:
            self.screen_width = 0
            self.screen_height = 0
            self.piece = None
            self.overrides = {}
            self.durations = {}
            self.dotted = set()
            self.annotations = {}
            self.ornaments = {}
            self.slurs = []
            self.ties = []
            self.holds = []

    state = _State()
    monkeypatch.setattr(oud_app, "init_state", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(oud_app, "render_ascii_snapshot", lambda _s: "x\n")
    monkeypatch.setattr(
        oud_app.shutil,
        "get_terminal_size",
        lambda _fallback: os.terminal_size((100, 50)),
    )
    assert oud_app._cmd_ascii("in.ft3", "cfg.toml", None) == 0
    assert state.screen_width == 100
    assert state.screen_height == 50
