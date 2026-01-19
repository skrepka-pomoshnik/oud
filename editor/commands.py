from __future__ import annotations

from .state import EditorState


def cmd_title(state: EditorState, args: str) -> None:
    value = args.strip()
    if not value:
        state.message = "Title required"
        return
    state.piece.title = value
    state.modified = True
    state.message = "Title set"


def cmd_author(state: EditorState, args: str) -> None:
    value = args.strip()
    if not value:
        state.message = "Author required"
        return
    state.piece.author = value
    state.modified = True
    state.message = "Author set"


def cmd_composer(state: EditorState, args: str) -> None:
    value = args.strip()
    if not value:
        state.message = "Composer required"
        return
    state.piece.composer = value
    state.modified = True
    state.message = "Composer set"


def cmd_subtitle(state: EditorState, args: str) -> None:
    value = args.strip()
    if not value:
        state.message = "Subtitle required"
        return
    state.piece.subtitle = value
    state.modified = True
    state.message = "Subtitle set"


def cmd_footnote(state: EditorState, args: str) -> None:
    value = args.strip()
    if not value:
        state.message = "Footnote required"
        return
    state.piece.footnote = value
    state.modified = True
    state.message = "Footnote set"


def cmd_header_template(state: EditorState, _args: str) -> None:
    state.piece.title = "Title"
    state.piece.author = "Author"
    state.piece.composer = "Composer"
    state.piece.subtitle = "Subtitle"
    state.piece.footnote = "Footnote"
    state.modified = True
    state.message = "Header template applied"
