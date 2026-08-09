import curses

import pytest

from oud.presentation import app


def test_tui_keyboard_interrupt_exits_quietly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def interrupt(*_args: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(curses, "wrapper", interrupt)

    assert app.main([]) == app.EXIT_INTERRUPTED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
