from __future__ import annotations

from oud.core.ft3 import build_durations
from oud.core.model import Bar, Chord, Note, Piece
from oud.core.tab_policy import apply_tabnotation_preset
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece
from tests.helpers_regression_cases import dense_flag_alignment_piece, regression_state


def _render_state_lines(state, *, height: int = 24) -> list[str]:
    fb = FrameBuffer(height, state.screen_width or 120)
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
    )
    return fb.snapshot().lines


def _simple_piece() -> Piece:
    return Piece(
        title="Snippet",
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


def _dense_auftact_piece(time_sig: str) -> Piece:
    return Piece(
        title="AuftactDense",
        bars=[
            Bar(
                time_sig=time_sig,
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )


def test_tab_snippet_tab_full_notation_preset_bundle() -> None:
    state = regression_state(_simple_piece(), width=90, bar_width=10)
    ok = apply_tabnotation_preset(state.settings, "full")
    assert ok is True
    lines = _render_state_lines(state)
    # Full preset should show a fractional cue for common-triple symbol O => 3/4
    # as a 3-row in-staff block.
    first_rows = lines[:14]
    assert any("3" in line for line in first_rows)
    assert any("/" in line for line in first_rows)
    assert any("4" in line for line in first_rows)
    # Full preset should reveal duration digits row content.
    assert any(any(ch.isdigit() for ch in line) for line in lines[:12])


def test_tab_snippet_letter_tablature_formatting_analogue() -> None:
    piece = Piece(
        title="Letters",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 10, 0), Note(2, 2, 0)])])],
        strings=6,
    )
    french = regression_state(piece, width=70, bar_width=8)
    french.settings["style"] = "french"
    italian = regression_state(piece, width=70, bar_width=8)
    italian.settings["style"] = "italian"
    italian.settings["timesigstyle"] = "numeric"
    fr_lines = _render_state_lines(french, height=14)
    it_lines = _render_state_lines(italian, height=14)
    # French tablature uses letters (10 -> l, 2 -> c with default shape).
    assert any("l" in line or "c" in line for line in fr_lines if "|" in line)
    # Italian tablature uses numbers (10 -> x special form, 2 -> 2).
    assert any(("x" in line or "2" in line) for line in it_lines if "|" in line)


def test_tab_snippet_stem_beam_behavior_in_tablature_full_mode() -> None:
    state = regression_state(dense_flag_alignment_piece(), justify="smart", width=100, bar_width=12)
    apply_tabnotation_preset(state.settings, "full")
    lines = _render_state_lines(state, height=20)
    # Expect at least one flag row with visible stems and tails.
    flag_rows = [line for line in lines if "|" in line and ("\\" in line or "=" in line or "/" in line)]
    assert flag_rows
    # Staff rows should remain present and aligned (right barline drawn).
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    assert all(row.rfind("|") == state.screen_width - 2 for row in staff_rows)


def test_tab_snippet_mid_system_meter_change_cue_fraction_style() -> None:
    piece = Piece(
        title="MeterChange",
        bars=[
            Bar(
                time_sig="C",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                ],
            ),
            Bar(
                time_sig="O",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 0, 0)]),
                ],
            ),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 1, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=100, bar_width=10, justify="smart")
    state.settings["timesigstyle"] = "fraction"
    lines = _render_state_lines(state, height=18)
    head = lines[:14]
    # Fraction cue for O => 3/4 must appear even when meter change occurs mid-system.
    assert any("3" in line for line in head)
    assert any("/" in line for line in head)
    assert any("4" in line for line in head)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    assert all(row.rfind("|") == state.screen_width - 2 for row in staff_rows)


def test_tab_snippet_hold_cue_row_does_not_break_staff_alignment() -> None:
    piece = Piece(
        title="Spans",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(6, 0, 0)])],
            ),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=120, bar_width=12, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.slurs = []
    state.ties = []
    state.holds = [(1, 0, 3)]
    lines = _render_state_lines(state, height=20)
    assert any("<" in line or ">" in line or "_" in line for line in lines)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    assert all(row.rfind("|") == state.screen_width - 2 for row in staff_rows)


def test_tab_snippet_tab_full_notation_sets_tie_cue_style() -> None:
    state = regression_state(_simple_piece(), width=90, bar_width=10)
    assert apply_tabnotation_preset(state.settings, "full") is True
    assert state.settings["tiecuestyle"] == "paren"


def test_tab_snippet_tab_full_notation_flagstyle_matrix_renders() -> None:
    for flagstyle in ("standard", "board", "englishgrid", "continental"):
        state = regression_state(dense_flag_alignment_piece(), justify="smart", width=100, bar_width=12)
        apply_tabnotation_preset(state.settings, "full")
        state.settings["flagstyle"] = flagstyle
        lines = _render_state_lines(state, height=20)
        staff_rows = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                continue
            if stripped[0] not in "123456789abcdefghijklmnopqrstuvwxyz/":
                continue
            if line.count("|") >= 2 and "-" in line:
                staff_rows.append(line)
        assert staff_rows, flagstyle
        assert all(row.rfind("|") == state.screen_width - 2 for row in staff_rows), flagstyle


def test_tab_snippet_time_cue_dense_auftact_no_glue_c_o_3() -> None:
    cases = [
        ("C", "symbol", "C"),
        ("O", "symbol", "O"),
        ("3/4", "numeric", "3"),
    ]
    for time_sig, style_mode, cue in cases:
        state = regression_state(_dense_auftact_piece(time_sig), width=100, bar_width=10, justify="smart")
        state.settings["timesigstyle"] = style_mode
        lines = _render_state_lines(state, height=18)
        head = lines[:14]
        assert any(cue in line for line in head), (time_sig, style_mode)
        # Regression: cue must not glue directly to first notehead letter in dense auftact.
        assert not any(f"{cue}a" in line for line in head), (time_sig, style_mode, head)
