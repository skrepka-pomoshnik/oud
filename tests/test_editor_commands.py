from oud.core.model import Bar, Piece
from oud.editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from oud.editor.state import EditorState


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {"style": "french"}
    return EditorState(piece, settings)


def test_header_template_sets_fields() -> None:
    state = _state()
    cmd_header_template(state, "")
    assert state.piece.title == "Title"
    assert state.piece.author == "Author"
    assert state.piece.composer == "Composer"
    assert state.piece.subtitle == "Subtitle"
    assert state.piece.footnote == "Footnote"


def test_title_author_composer_require_value() -> None:
    state = _state()
    cmd_title(state, "")
    assert state.message == "Title required"
    cmd_author(state, "")
    assert state.message == "Author required"
    cmd_composer(state, "")
    assert state.message == "Composer required"


def test_title_author_composer_updates_piece() -> None:
    state = _state()
    cmd_title(state, "My Title")
    cmd_author(state, "Me")
    cmd_composer(state, "Them")
    assert state.piece.title == "My Title"
    assert state.piece.author == "Me"
    assert state.piece.composer == "Them"


def test_subtitle_and_footnote_require_value() -> None:
    state = _state()
    cmd_subtitle(state, "")
    assert state.message == "Subtitle required"
    cmd_footnote(state, "")
    assert state.message == "Footnote required"


def test_subtitle_and_footnote_updates_piece() -> None:
    state = _state()
    cmd_subtitle(state, "Sub")
    cmd_footnote(state, "Note")
    assert state.piece.subtitle == "Sub"
    assert state.piece.footnote == "Note"
