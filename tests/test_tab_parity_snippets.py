from __future__ import annotations

import pytest

from oud.importers.ft3 import build_durations
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.input.tablature.policy import apply_tabnotation_preset
from tests.helpers_regression_cases import (
    dense_auftact_piece,
    dense_flag_alignment_piece,
    polyphony_analogue_piece,
    regression_state,
)


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
        getattr(state, "glisses", None),
    )
    return fb.snapshot().lines


def _assert_aligned_staff_systems(lines: list[str], width: int) -> None:
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.count("|") >= 2 and "-" in line:
            current.append(line)
            continue
        if current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    assert groups
    for group in groups:
        right_edges = {row.rfind("|") for row in group}
        assert len(right_edges) == 1
        assert 0 < next(iter(right_edges)) <= width - 2


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


def test_tab_snippet_tab_full_notation_keeps_rest_marker_visible() -> None:
    state = regression_state(_simple_piece(), width=88, bar_width=10)
    apply_tabnotation_preset(state.settings, "full")
    # Replace first onset with an explicit rest marker in the rendered tab cell.
    state.overrides[(0, 0, 0)] = "_"
    lines = _render_state_lines(state, height=18)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    assert any("_" in row for row in staff_rows)
    # Full preset still shows duration digits and cue rows with the rest present.
    assert any(any(ch.isdigit() for ch in line) for line in lines[:12])


def test_tab_snippet_inline_ornament_hash_renders_next_to_note() -> None:
    state = regression_state(_simple_piece(), width=88, bar_width=10)
    apply_tabnotation_preset(state.settings, "full")
    state.settings["showextras"] = "on"
    state.ornaments = {(0, 0): "#"}
    lines = _render_state_lines(state, height=18)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert any("a#" in row for row in staff_rows)


def test_tab_snippet_inline_fingering_uses_compact_superscript() -> None:
    state = regression_state(_simple_piece(), width=88, bar_width=10)
    apply_tabnotation_preset(state.settings, "full")
    state.settings["style"] = "italian"
    state.settings["italianorient"] = "reverse"
    state.settings["showspans"] = "on"
    state.annotations = {(0, 0): "1"}
    lines = _render_state_lines(state, height=18)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert any(any(pair in row for pair in ("0¹", "¹0", "1¹", "¹1", "2¹", "¹2")) for row in staff_rows)


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
    _assert_aligned_staff_systems(lines, state.screen_width)


@pytest.mark.parametrize("flagstyle", ["standard", "englishgrid", "continental"])
@pytest.mark.parametrize("flagstems", ["single", "double"])
@pytest.mark.parametrize("flaglean", ["right", "left"])
def test_tab_snippet_stem_beam_analogue_flagshape_and_stem_rows_matrix(
    flagstyle: str,
    flagstems: str,
    flaglean: str,
) -> None:
    piece = dense_flag_alignment_piece()
    piece.bars[0].time_sig = None  # avoid cue rows confusing the stem-row count
    state = regression_state(piece, justify="smart", width=96, bar_width=12)
    apply_tabnotation_preset(state.settings, "full")
    state.settings["flagstyle"] = flagstyle
    state.settings["flagstems"] = flagstems
    state.settings["flaglean"] = flaglean
    lines = _render_state_lines(state, height=20)
    staff_start = next(i for i, line in enumerate(lines) if line.count("|") >= 2 and "-" in line)
    head = lines[:staff_start]
    stem_like_rows = [
        line
        for line in head
        if "|" in line and "-" not in line and any(ch in line for ch in ("|", "\\", "/", "=", "Γ", "F"))
    ]
    assert stem_like_rows, (flagstyle, flagstems, flaglean)
    if flagstems == "double" and flagstyle == "standard":
        assert len(stem_like_rows) >= 2, (flagstyle, flaglean, head)
    if flagstyle == "standard":
        joined = "\n".join(stem_like_rows)
        if flaglean == "left":
            assert "/" in joined
        else:
            assert "\\" in joined


def test_tab_snippet_polyphony_in_tablature_analogue_two_voice_texture_stays_aligned() -> None:
    state = regression_state(polyphony_analogue_piece(), justify="smart", width=88, bar_width=10)
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["flagstyle"] = "standard"
    state.settings["flagstems"] = "double"
    lines = _render_state_lines(state, height=28)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    # Mixed durations should produce visible flag/tail rows.
    assert any(("\\" in line or "=" in line) for line in lines[:12])
    # Two-voice-like texture should preserve multiple independent note rows.
    note_rows = [row for row in staff_rows if any(ch.isalnum() for ch in row if ch not in {"|"})]
    assert len(note_rows) >= 3
    # No obvious split gaps or glued repeated noteheads in dense areas.
    assert all("|  |" not in row for row in staff_rows)


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
    _assert_aligned_staff_systems(lines, state.screen_width)


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
    _assert_aligned_staff_systems(lines, state.screen_width)


def test_tab_snippet_tab_full_notation_sets_tie_cue_style() -> None:
    state = regression_state(_simple_piece(), width=90, bar_width=10)
    assert apply_tabnotation_preset(state.settings, "full") is True
    assert state.settings["tiecuestyle"] == "paren"


def test_tab_snippet_tab_full_notation_shows_tuplet_cue() -> None:
    state = regression_state(_simple_piece(), width=90, bar_width=10)
    assert apply_tabnotation_preset(state.settings, "full") is True
    state.annotations = {(0, 0): "³"}
    lines = _render_state_lines(state, height=18)
    cue_rows = [line for line in lines[:10] if "³" in line]
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert cue_rows
    assert staff_rows
    assert not any("³" in row for row in staff_rows)


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
        _assert_aligned_staff_systems(lines, state.screen_width)


def test_tab_snippet_time_cue_dense_auftact_no_glue_c_o_3() -> None:
    cases = [
        ("C", "symbol", "C"),
        ("O", "symbol", "O"),
        ("3/4", "numeric", "3"),
    ]
    for time_sig, style_mode, cue in cases:
        state = regression_state(dense_auftact_piece(time_sig), width=100, bar_width=10, justify="smart")
        state.settings["timesigstyle"] = style_mode
        lines = _render_state_lines(state, height=18)
        head = lines[:14]
        assert any(cue in line for line in head), (time_sig, style_mode)
        # Regression: cue must not glue directly to first notehead letter in dense auftact.
        assert not any(f"{cue}a" in line for line in head), (time_sig, style_mode, head)


def test_tab_snippet_repeats_and_double_barline_render_without_breaking_staff() -> None:
    piece = Piece(
        title="Repeats",
        bars=[
            Bar(
                repeat=".:",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)])],
            ),
            Bar(
                barline="||",
                repeat=":.",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=90, bar_width=10, justify="smart")
    for key in ("showdur", "showextras", "showtactus"):
        state.settings[key] = "off"
    lines = _render_state_lines(state, height=18)
    head = lines[:8]
    assert not any(".:" in line for line in head)
    assert not any(":." in line for line in head)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    assert any(":" in row for row in staff_rows)
    # Double barline at the system edge is allowed, but staff rows must still draw a closing barline.
    assert all(row.rstrip().endswith("|") for row in staff_rows)
    assert any(row.rstrip().endswith("||") for row in staff_rows)


def test_tab_snippet_repeat_and_barline_variant_matrix_renders() -> None:
    variants = [
        (".:", "|"),
        (":.", "||"),
        (".", "|"),
        ("DC al Fine", "||"),
    ]
    for repeat, barline in variants:
        piece = Piece(
            title="RepeatVariant",
            bars=[
                Bar(
                    repeat=repeat,
                    barline=barline,
                    chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                ),
            ],
            strings=6,
            style="french",
        )
        state = regression_state(piece, width=70, bar_width=10, justify="smart")
        for key in ("showdur", "showextras", "showtactus"):
            state.settings[key] = "off"
        lines = _render_state_lines(state, height=16)
        staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
        assert staff_rows, (repeat, barline)
        assert any(row.rstrip().endswith("|") for row in staff_rows), (repeat, barline)
        if repeat in {".:", ":.", "."}:
            assert not any(repeat in line for line in lines[:6]), (repeat, barline)
            assert any(":" in line for line in lines[2:12]), (repeat, barline)
        else:
            assert any("DC al Fine" in line for line in lines[:8]), (repeat, barline)


def test_tab_snippet_spans_and_ornament_markers_keep_alignment_dense() -> None:
    piece = Piece(
        title="SpansDense",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0), Note(4, 1, 0)]),
                ],
            ),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=110, bar_width=12, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.ornaments = {(0, 1): "*", (0, 2): "o"}  # harmonic/ornament-style markers analogue
    state.slurs = [(0, 0, 3)]
    state.holds = [(0, 1, 3)]
    state.ties = [(0, 1, 3)]
    state.settings["tienoteheads"] = "parenthesize"
    lines = _render_state_lines(state, height=22)
    assert any("*" in line or "o" in line for line in lines)
    assert any("(" in line or ")" in line for line in lines)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)


def test_tab_snippet_tie_notehead_modes_survive_multi_system_reflow() -> None:
    piece = Piece(
        title="TieModes",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(6)
        ],
        strings=6,
        style="french",
    )
    ties = [(idx, 1, 3) for idx in range(6)]
    for mode in ("show", "hide", "parenthesize"):
        state = regression_state(piece, width=52, bar_width=8, justify="smart")
        state.settings["layout"] = "packed"
        state.settings["barsperline"] = "2"
        apply_tabnotation_preset(state.settings, "full")
        state.settings["tienoteheads"] = mode
        state.settings["tiecuestyle"] = "hide"
        state.ties = list(ties)
        lines = _render_state_lines(state, height=24)
        staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
        assert staff_rows, mode
        assert all(row.rstrip().endswith("|") for row in staff_rows), mode
        if mode == "parenthesize":
            assert any("(" in line for line in lines), mode


def test_tab_snippet_parenthesize_tie_cues_survive_auto_scaling() -> None:
    piece = Piece(
        title="TieAuto",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(5)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=58, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "hide"
    state.ties = [(idx, 1, 3) for idx in range(5)]
    lines = _render_state_lines(state, height=32)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    assert any("(" in line for line in lines)
    assert any(")" in line for line in lines)


def test_tab_snippet_parenthesize_tie_cues_with_annotation_and_tie_cue_collisions() -> None:
    piece = Piece(
        title="TieCueCollision",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=64, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.ties = [(idx, 1, 3) for idx in range(4)]
    # Occupy the preferred opening-cue column in the annotation row.
    state.annotations = {(idx, 3): "x" for idx in range(4)}
    lines = _render_state_lines(state, height=28)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    assert any("(" in line for line in lines)
    assert any(")" in line for line in lines)


def test_tab_snippet_parenthesize_tie_cues_survive_slur_hold_collision_stack() -> None:
    piece = Piece(
        title="TieSlurHoldCollision",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(3)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=70, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["slurcuestyle"] = "paren"
    state.settings["holdcuestyle"] = "paren"
    state.annotations = {(i, 3): "x" for i in range(3)}
    state.ornaments = {(i, 3): "*" for i in range(3)}
    state.ties = [(i, 1, 3) for i in range(3)]
    state.slurs = [(i, 0, 3) for i in range(3)]
    state.holds = [(i, 0, 3) for i in range(3)]
    lines = _render_state_lines(state, height=28)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    assert any("(" in line for line in lines)
    assert any(")" in line for line in lines)


def test_tab_snippet_tie_cues_keep_precedence_across_forced_system_breaks() -> None:
    piece = Piece(
        title="TieBreakPrecedence",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=64, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["slurcuestyle"] = "paren"
    state.settings["holdcuestyle"] = "paren"
    state.stave_breaks = {2}
    state.annotations = {(i, 3): "x" for i in range(4)}
    state.ornaments = {(i, 3): "*" for i in range(4)}
    state.ties = [(i, 1, 3) for i in range(4)]
    state.slurs = [(i, 0, 3) for i in range(4)]
    state.holds = [(i, 0, 3) for i in range(4)]
    lines = _render_state_lines(state, height=32)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    # Tie brackets should survive same-row slur/hold collisions after compositing.
    assert any("[" in line for line in lines)
    assert any("]" in line for line in lines)
    # Parenthesize proxy cues should still appear somewhere around the tied onsets.
    assert any("(" in line for line in lines)
    assert any(")" in line for line in lines)


def test_tab_snippet_tie_followed_by_gliss_cues_survive_system_break_collisions() -> None:
    piece = Piece(
        title="TieGlissBreak",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=66, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["glisscuestyle"] = "slash"
    state.stave_breaks = {2}
    state.annotations = {(i, 3): "x" for i in range(4)}
    state.ornaments = {(i, 3): "*" for i in range(4)}
    state.ties = [(i, 1, 3) for i in range(4)]
    state.glisses = [(i, 0, 3) for i in range(4)]
    lines = _render_state_lines(state, height=30)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    assert any("[" in line for line in lines)
    assert any("]" in line for line in lines)
    assert any("(" in line for line in lines)
    assert any(")" in line for line in lines)
    assert any("/" in line or "\\" in line for line in lines)


def test_tab_snippet_slur_gliss_parenthesize_cues_do_not_clobber_dense_frets() -> None:
    piece = Piece(
        title="CueVsFretDense",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 10, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 11, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 12, 0)]),
                    Chord(note_type=5, dotted=True, grid=None, notes=[Note(1, 9, 0), Note(4, 2, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 10, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 11, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=68, bar_width=9, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["slurcuestyle"] = "paren"
    state.settings["glisscuestyle"] = "slash"
    state.annotations = {(i, 3): "x" for i in range(4)}
    state.ornaments = {(i, 3): "*" for i in range(4)}
    state.ties = [(i, 1, 3) for i in range(4)]
    state.slurs = [(i, 0, 3) for i in range(4)]
    state.glisses = [(i, 0, 3) for i in range(4)]
    lines = _render_state_lines(state, height=30)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    # Fret glyphs (10/11/12 => l/m/n in French) must survive dense cue overlays.
    staff_text = "\n".join(staff_rows)
    assert "l" in staff_text and "m" in staff_text and "n" in staff_text
    # Cue glyphs render, but should stay in cue rows (not overwrite staff frets).
    cue_chars = set("()[]<>~/\\")
    assert any(any(ch in cue_chars for ch in line) for line in lines)
    disallowed_staff_cues = set("()[]<>~\\")
    assert not any(
        any(ch in disallowed_staff_cues for ch in row.replace("|", "").replace("-", "")) for row in staff_rows
    )


def test_tab_snippet_slur_gliss_parenthesize_collision_regression_with_system_breaks() -> None:
    piece = Piece(
        title="CueVsFretBreaks",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 10, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 11, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 12, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 9, 0)]),
                ],
            )
            for _ in range(6)
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, width=62, bar_width=8, justify="smart")
    apply_tabnotation_preset(state.settings, "full")
    state.settings["layout"] = "auto"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["slurcuestyle"] = "paren"
    state.settings["holdcuestyle"] = "paren"
    state.settings["glisscuestyle"] = "slash"
    state.stave_breaks = {2, 4}
    state.annotations = {(i, 3): "x" for i in range(6)}
    state.ornaments = {(i, 3): "*" for i in range(6)}
    state.ties = [(i, 1, 3) for i in range(6)]
    state.slurs = [(i, 0, 3) for i in range(6)]
    state.holds = [(i, 0, 3) for i in range(6)]
    state.glisses = [(i, 0, 3) for i in range(6)]
    lines = _render_state_lines(state, height=36)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    staff_text = "\n".join(staff_rows)
    assert "l" in staff_text and "m" in staff_text and "n" in staff_text
    assert any("[" in line and "]" in line for line in lines)
    assert any("(" in line for line in lines)
    assert any("/" in line or "\\" in line for line in lines)


def test_tab_snippet_gridflags_after_comment_clear_keeps_dense_staff_alignment() -> None:
    state = regression_state(dense_flag_alignment_piece(), justify="smart", width=92, bar_width=12)
    apply_tabnotation_preset(state.settings, "full")
    state.settings["flagstyle"] = "board"
    state.annotations = {}
    lines = _render_state_lines(state, height=22)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    _assert_aligned_staff_systems(lines, state.screen_width)
    assert any("=" in line for line in lines[:12])
    assert not any("comment" in line.lower() for line in lines)
