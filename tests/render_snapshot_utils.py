from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any, Protocol, cast

from oud.core.ft3 import build_durations
from oud.core.model import Bar, Chord, Note, Piece
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece
from tests.helpers_regression_cases import dense_flag_alignment_piece, regression_state


class RenderSnapshotState(Protocol):
    piece: Piece
    screen_width: int
    bar_width: int
    overrides: dict[tuple[int, int, int], str]
    ornaments: dict[tuple[int, int], str]
    annotations: dict[tuple[int, int], str]
    highlights: set[tuple[int, int, int]]
    dotted: set[tuple[int, int]]
    slurs: list[tuple[int, int, int]]
    ties: list[tuple[int, int, int]]
    holds: list[tuple[int, int, int]]
    settings: dict[str, str]
    stave_breaks: set[int]


@dataclass(frozen=True)
class SnapshotCase:
    name: str
    build_state: Callable[[], RenderSnapshotState]
    height: int


def render_state_lines(state: RenderSnapshotState, *, height: int = 24) -> list[str]:
    fb = FrameBuffer(height, getattr(state, "screen_width", 120) or 120)
    render_piece(
        fb,
        state.piece,
        0,
        0,
        0,
        0,
        state.bar_width,
        state.overrides,
        build_durations(state.piece),
        state.ornaments,
        state.annotations,
        state.highlights,
        state.dotted,
        state.slurs,
        state.ties,
        state.holds,
        "normal",
        "",
        "",
        "",
        "",
        state.settings,
        None,
        state.stave_breaks,
        "Plugins",
        [],
        0,
        0,
        0,
        None,
        None,
        getattr(cast(Any, state), "glisses", None),
    )
    return fb.snapshot().lines


def normalize_snapshot_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    # Drop volatile header/status lines; snapshots focus on score block geometry.
    core = lines[1:-1] if len(lines) >= 2 else list(lines)
    core = [line.rstrip() for line in core]
    while core and not core[0].strip():
        core.pop(0)
    while core and not core[-1].strip():
        core.pop()
    return core


def snapshot_signature(lines: list[str]) -> dict[str, object]:
    norm = normalize_snapshot_lines(lines)
    staff_rows: list[str] = [line for line in norm if line.count("|") >= 2 and "-" in line]
    staff_note_cols: set[int] = set()
    staff_right_edges: list[int] = []
    for row in staff_rows:
        left = row.find("|")
        right = row.rfind("|")
        staff_right_edges.append(right)
        if left < 0 or right <= left:
            continue
        for idx in range(left + 1, right):
            ch = row[idx]
            if ch not in (" ", "-", "|"):
                staff_note_cols.add(idx)
    first_staff_idx = next((i for i, line in enumerate(norm) if line in staff_rows), len(norm))
    flag_cols: set[int] = set()
    flag_symbols = set("|IΓF/\\=.-")
    for line in norm[:first_staff_idx]:
        if "-" in line and "|" in line:
            continue
        for idx, ch in enumerate(line):
            if ch in flag_symbols:
                flag_cols.add(idx)
    return {
        "line_count": len(norm),
        "row_widths": [len(line) for line in norm],
        "staff_rows": len(staff_rows),
        "staff_right_edges": staff_right_edges,
        "staff_note_cols": sorted(staff_note_cols),
        "flag_cols": sorted(flag_cols),
    }


def snapshot_case_lines(case: SnapshotCase) -> list[str]:
    state = case.build_state()
    return normalize_snapshot_lines(render_state_lines(state, height=case.height))


def snapshot_case_signature(case: SnapshotCase) -> dict[str, object]:
    state = case.build_state()
    return snapshot_signature(render_state_lines(state, height=case.height))


def _case_simple_full() -> RenderSnapshotState:
    piece = Piece(
        title="SnapshotSimple",
        bars=[
            Bar(
                time_sig="O",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
                ],
            ),
            Bar(
                chords=[
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 4, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 5, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=92, bar_width=10, justify="smart")
    state.settings.update(
        {
            "showdur": "on",
            "showextras": "on",
            "showtactus": "on",
            "timesigstyle": "fraction",
            "tabnotation": "full",
            "tiecuestyle": "paren",
            "slurcuestyle": "paren",
            "holdcuestyle": "angle",
        },
    )
    return state


def _case_dense_flags() -> RenderSnapshotState:
    state = regression_state(dense_flag_alignment_piece(), width=104, bar_width=12, justify="smart")
    state.settings.update(
        {
            "layout": "auto",
            "justify": "smart",
            "showdur": "on",
            "showextras": "off",
            "showtactus": "on",
            "flagredundant": "on",
            "flagstyle": "englishgrid",
        },
    )
    return state


def _case_span_cues() -> RenderSnapshotState:
    piece = Piece(
        title="SnapshotSpans",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 10, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 11, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 12, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 9, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=66, bar_width=8, justify="smart")
    state.settings.update(
        {
            "layout": "auto",
            "showextras": "on",
            "tienoteheads": "parenthesize",
            "tiecuestyle": "bracket",
            "slurcuestyle": "paren",
            "holdcuestyle": "paren",
            "glisscuestyle": "slash",
        },
    )
    state.stave_breaks = {2}
    state.annotations = {(i, 3): "x" for i in range(4)}
    state.ornaments = {(i, 3): "#" for i in range(4)}
    state.ties = [(i, 1, 3) for i in range(4)]
    state.slurs = [(i, 0, 3) for i in range(4)]
    state.holds = [(i, 0, 3) for i in range(4)]
    state.glisses = [(i, 0, 3) for i in range(4)]
    return state


def snapshot_cases() -> list[SnapshotCase]:
    return [
        SnapshotCase("simple_full", _case_simple_full, 22),
        SnapshotCase("dense_flags_englishgrid", _case_dense_flags, 20),
        SnapshotCase("span_cues_breaks", _case_span_cues, 28),
    ]


def snapshot_fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "render_snapshots"


def write_snapshot_fixtures() -> None:
    out_dir = snapshot_fixture_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in snapshot_cases():
        lines = snapshot_case_lines(case)
        sig = snapshot_case_signature(case)
        (out_dir / f"{case.name}.snap.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (out_dir / f"{case.name}.sig.json").write_text(
            json.dumps(sig, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def read_snapshot_fixture(case: SnapshotCase) -> tuple[list[str], dict[str, object]]:
    fixture_dir = snapshot_fixture_dir()
    snap_path = fixture_dir / f"{case.name}.snap.txt"
    sig_path = fixture_dir / f"{case.name}.sig.json"
    snap_lines = snap_path.read_text(encoding="utf-8").splitlines()
    signature = json.loads(sig_path.read_text(encoding="utf-8"))
    return snap_lines, signature


def snapshot_mismatch_report(case: SnapshotCase) -> str | None:
    actual_lines = snapshot_case_lines(case)
    actual_sig = snapshot_case_signature(case)
    expected_lines, expected_sig = read_snapshot_fixture(case)
    if actual_sig != expected_sig:
        return (
            f"{case.name}: signature mismatch\n"
            f"expected: {json.dumps(expected_sig, sort_keys=True)}\n"
            f"actual:   {json.dumps(actual_sig, sort_keys=True)}"
        )
    if actual_lines != expected_lines:
        diff = "".join(
            unified_diff(
                [line + "\n" for line in expected_lines],
                [line + "\n" for line in actual_lines],
                fromfile=f"{case.name}.expected",
                tofile=f"{case.name}.actual",
            ),
        )
        return f"{case.name}: snapshot mismatch\n{diff}"
    return None
