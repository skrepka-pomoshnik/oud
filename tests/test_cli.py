import sys

import cli
from oud.core.model import Bar, Piece


def test_cli_main_tab(monkeypatch, capsys) -> None:
    piece = Piece(title="Tab", bars=[Bar()], strings=6)
    monkeypatch.setattr(cli, "load_tab", lambda _path: piece)
    monkeypatch.setattr(cli, "load_ft3", lambda _path: piece)
    monkeypatch.setattr(sys, "argv", ["cli.py", "test.tab"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "Title: Tab" in output


def test_cli_main_ft3(monkeypatch, capsys) -> None:
    piece = Piece(title="Ft3", bars=[Bar()], strings=6)
    monkeypatch.setattr(cli, "load_tab", lambda _path: piece)
    monkeypatch.setattr(cli, "load_ft3", lambda _path: piece)
    monkeypatch.setattr(sys, "argv", ["cli.py", "test.ft3"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "Title: Ft3" in output
