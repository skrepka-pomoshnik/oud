from __future__ import annotations

import curses
import fcntl
import json
import os
import select
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path
from typing import Any

import pytest

from oud.editor.core.document import display_path
from oud.editor.interaction.dispatch.actions import handle_insert, handle_normal
from oud.editor.services.screen.status import status_line
from oud.presentation.tui.commands import apply_command
from oud.presentation.tui.loop import run_loop

_PROBE_KEY = ord("!")
_SMALL_SIZE = (24, 80)
_LARGE_SIZE = (40, 120)


def _capture_screen(stdscr: curses.window, state: Any) -> dict[str, Any]:
    height, width = stdscr.getmaxyx()
    rows: list[str] = []
    reverse_rows: set[int] = set()
    for y in range(height):
        try:
            raw = stdscr.instr(y, 0, max(0, width - 1))
        except curses.error:
            raw = b""
        rows.append(raw.decode("utf-8", errors="replace").rstrip())
        for x in range(max(0, width - 1)):
            try:
                if stdscr.inch(y, x) & curses.A_REVERSE:
                    reverse_rows.add(y)
            except curses.error:
                break
    return {
        "size": [height, width],
        "cursor": [state.cursor_bar, state.cursor_string, state.cursor_col],
        "filename": display_path(state),
        "modified": state.modified,
        "mode": state.mode,
        "document_mode": state.document_mode.value,
        "write_path": state.write_path,
        "status": status_line(state),
        "rows": rows,
        "reverse_rows": sorted(reverse_rows),
    }


def _run_probe(report_path: Path, source_path: str, config_path: str) -> int:
    def wrapped(stdscr: curses.window) -> int:
        def probe_normal(state: Any, key: int) -> bool:
            if key != _PROBE_KEY:
                return handle_normal(state, key)
            payload = _capture_screen(stdscr, state)
            with report_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
            return True

        return run_loop(
            stdscr,
            source_path,
            config_path=config_path,
            handle_insert=handle_insert,
            handle_normal=probe_normal,
            apply_command=apply_command,
        )

    return curses.wrapper(wrapped)


def _set_terminal_size(fd: int, size: tuple[int, int]) -> None:
    rows, columns = size
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))


def _drain_terminal(fd: int, output: bytearray) -> None:
    while select.select([fd], [], [], 0)[0]:
        try:
            output.extend(os.read(fd, 65536))
        except (BlockingIOError, OSError):
            return


def _reports(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _wait_for_report(
    process: subprocess.Popen[bytes],
    *,
    master_fd: int,
    report_path: Path,
    size: tuple[int, int],
    target_path: Path,
    terminal_output: bytearray,
) -> dict[str, Any]:
    deadline = time.monotonic() + 8
    next_probe = 0.0
    while time.monotonic() < deadline:
        _drain_terminal(master_fd, terminal_output)
        matching = [
            report
            for report in _reports(report_path)
            if report["size"] == list(size) and report["write_path"] == str(target_path) and report["modified"] is True
        ]
        if matching:
            return matching[-1]
        if process.poll() is not None:
            break
        if time.monotonic() >= next_probe:
            os.write(master_fd, bytes([_PROBE_KEY]))
            next_probe = time.monotonic() + 0.2
        time.sleep(0.02)
    rendered_output = terminal_output.decode("utf-8", errors="replace")[-2000:]
    pytest.fail(f"curses probe did not report {size}; exit={process.poll()} output={rendered_output!r}")


def _wait_for_exit(
    process: subprocess.Popen[bytes],
    master_fd: int,
    terminal_output: bytearray,
    *,
    timeout: float = 5,
) -> int:
    deadline = time.monotonic() + timeout
    while process.poll() is None and time.monotonic() < deadline:
        _drain_terminal(master_fd, terminal_output)
        time.sleep(0.02)
    _drain_terminal(master_fd, terminal_output)
    if process.poll() is None:
        process.kill()
        process.wait()
        rendered_output = terminal_output.decode("utf-8", errors="replace")[-2000:]
        pytest.fail(f"curses probe did not exit after :q!; output={rendered_output!r}")
    return process.returncode


def _run_resize_session(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(__file__).resolve().parents[1]
    source = root / "tests/fixtures/ft3/corpus/01_unquiet_thoughts/unquiet_thoughts_T.ft3"
    target = tmp_path / "resize-target.tab"
    report = tmp_path / "resize-report.jsonl"
    config = tmp_path / "config.toml"
    master_fd, slave_fd = os.openpty()
    terminal_output = bytearray()
    process: subprocess.Popen[bytes] | None = None
    try:
        _set_terminal_size(slave_fd, _SMALL_SIZE)
        env = dict(os.environ)
        env.update({"TERM": "xterm-256color", "LANG": "en_US.UTF-8"})
        process = subprocess.Popen(  # noqa: S603 - fixed interpreter and local probe path
            [sys.executable, __file__, "--probe", str(report), str(source), str(config)],
            cwd=root,
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = -1
        command = f":w {target}\nia\x1bllj!".encode()
        os.write(master_fd, command)
        small = _wait_for_report(
            process,
            master_fd=master_fd,
            report_path=report,
            size=_SMALL_SIZE,
            target_path=target,
            terminal_output=terminal_output,
        )

        _set_terminal_size(master_fd, _LARGE_SIZE)
        process.send_signal(signal.SIGWINCH)
        large = _wait_for_report(
            process,
            master_fd=master_fd,
            report_path=report,
            size=_LARGE_SIZE,
            target_path=target,
            terminal_output=terminal_output,
        )

        os.write(master_fd, b":q!\n")
        assert _wait_for_exit(process, master_fd, terminal_output) == 0
        return small, large
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            _wait_for_exit(process, master_fd, terminal_output)
        os.close(master_fd)
        if slave_fd >= 0:
            os.close(slave_fd)


@pytest.mark.skipif(sys.platform != "darwin", reason="real curses terminal regression is macOS-only")
def test_real_curses_resize_preserves_workflow_context(tmp_path: Path) -> None:
    small, large = _run_resize_session(tmp_path)

    assert small["cursor"] == large["cursor"]
    for report in (small, large):
        height, width = report["size"]
        assert report["filename"] == "unquiet_thoughts_T.ft3"
        assert report["modified"] is True
        assert report["mode"] == "normal"
        assert report["document_mode"] == "imported-projection"
        assert Path(report["write_path"]).name == "resize-target.tab"
        assert "unquiet_thoughts_T.ft3*" in report["status"]
        assert "[FT3 EDIT:resize-target.tab]" in report["status"]
        assert len(report["status"]) < width
        assert report["rows"][-1].startswith(report["status"])
        assert any(row < height - 1 for row in report["reverse_rows"])


if __name__ == "__main__" and sys.argv[1:2] == ["--probe"]:
    raise SystemExit(_run_probe(Path(sys.argv[2]), sys.argv[3], sys.argv[4]))
