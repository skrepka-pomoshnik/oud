from __future__ import annotations

import pytest

from oud.settings import DEFAULT_SETTINGS
from petrucci.framebuffer import FrameBuffer
from petrucci.model import Bar, Chord, Note, Piece
from petrucci.render import render_piece


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
        0,
        8,
        {},
        {},
        {},
        {},
        set(),
        set(),
        [],
        [],
        [],
        "normal",
        "",
        "",
        "",
        "",
        settings,
        None,
        set(),
        "Plugins",
        [],
        0,
        0,
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
