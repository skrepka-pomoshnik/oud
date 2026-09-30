from __future__ import annotations

import curses
import os
import zipfile
from pathlib import Path

import pytest

from oud.presentation import app as oud_app
from oud.presentation import cli_convert
from petrucci.core.model import Bar, Piece


def _write_tab(path: Path) -> None:
    path.write_text("% test\n-C\n{CLI score}\nb\n0a-----\n\ne\n", encoding="utf-8")


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
    piece = Piece(title="T", bars=[Bar()])
    monkeypatch.setattr(cli_convert, "load_settings", lambda _cfg: {"spacing": "oops"})
    monkeypatch.setattr(
        cli_convert,
        "load_piece_data",
        lambda _p: (piece, {}, {}, set(), 0),
    )
    context = cli_convert.load_export_context("in.ft3", "cfg.toml")
    assert context.settings["spacing"] == "oops"
    assert context.bar_width >= 4
    assert context.piece is piece
    assert context.overrides == {}
    assert context.durations == {}
    assert context.dotted == set()


def test_cmd_convert_ascii_and_unsupported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "input score.tab"
    output = tmp_path / "output score.txt"
    _write_tab(source)

    rc = oud_app._cmd_convert(str(source), str(output), "cfg.toml")
    assert rc == 0
    assert output.read_text(encoding="utf-8")
    assert f"Wrote {output}" in capsys.readouterr().out

    rc = oud_app._cmd_convert(str(source), str(tmp_path / "out.unsupported"), "cfg.toml")
    assert rc == 2
    assert "unsupported output format" in capsys.readouterr().err


def test_cmd_convert_mxl_is_atomic_zip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.tab"
    output = tmp_path / "out.mxl"
    _write_tab(source)

    rc = oud_app._cmd_convert(str(source), str(output), "cfg.toml")
    assert rc == 0
    assert zipfile.is_zipfile(output)
    assert f"Wrote {output}" in capsys.readouterr().out


def test_cmd_convert_pdf_preserves_source_and_fails_when_lilypond_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "input.tab"
    output = tmp_path / "out.pdf"
    _write_tab(source)
    monkeypatch.setattr(
        cli_convert,
        "print_lilypond_pdf",
        lambda _ly_path, _out_base, **_kwargs: "LilyPond not found on PATH",
    )

    rc = oud_app._cmd_convert(str(source), str(output), "cfg.toml")

    assert rc == cli_convert.EXIT_TOOL
    assert output.with_suffix(".ly").is_file()
    assert not output.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "LilyPond not found" in captured.err


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


def test_ascii_renders_a_musicxml_file_and_reports_what_it_did_not_read(capsys: pytest.CaptureFixture[str]) -> None:
    code = oud_app.main(["ascii", "tests/fixtures/musicxml/guitar_study_am.musicxml", "--bars", "1:2"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip()
    assert "oud: warning: MusicXML: 1 grace note was not read" in captured.err
