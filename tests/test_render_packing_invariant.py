from __future__ import annotations

import pytest

from oud.settings import DEFAULT_SETTINGS
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import FrameBuffer


def _render(fill: str) -> str:
    piece = Piece(
        title="Packing",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=16, dotted=True, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "layout": "auto",
            "justify": fill,
            "barpad": "1",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "showdur": "on",
            "showextras": "off",
            "showtactus": "off",
            "showtuning": "off",
            "flagredundant": "on",
            "flagstems": "single",
            "flagstyle": "standard",
            "measures": "off",
            "bargap": "1",
        },
    )
    fb = FrameBuffer(16, 64)
    render_piece(
        fb,
        piece,
        0,
        0,
        0,
        cursor_col=0,
        bar_width=8,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        highlights=set(),
        dotted=set(),
        slurs=[],
        ties=[],
        holds=[],
        mode="normal",
        cmdline="",
        message="",
        status_line="",
        searchline="",
        settings=settings,
        ascii_lines=None,
        stave_breaks=set(),
        plugin_title="Plugins",
        plugin_items=[],
        plugin_index=0,
        plugin_offset=0,
    )
    frame = fb.snapshot()
    return "\n".join(frame.lines)


@pytest.mark.parametrize("fill", ["compact", "center", "edge", "stretch", "smart"])
def test_spacing_modes_do_not_drop_chord_note_events(fill: str) -> None:
    rendered = _render(fill)
    for glyph in ("a", "b", "c", "d"):
        assert glyph in rendered
    assert "|" in rendered
    assert "\\" in rendered
