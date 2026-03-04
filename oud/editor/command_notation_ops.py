from __future__ import annotations

from oud.editor.notation_ops import cmd_arpeggio as _cmd_arpeggio
from oud.editor.notation_ops import cmd_barline as _cmd_barline
from oud.editor.notation_ops import cmd_dynamic as _cmd_dynamic
from oud.editor.notation_ops import cmd_fermata as _cmd_fermata
from oud.editor.notation_ops import cmd_repeat as _cmd_repeat
from oud.editor.notation_ops import cmd_separee as _cmd_separee
from oud.editor.notation_ops import cmd_time as _cmd_time
from oud.editor.notation_ops import cmd_tuplet as _cmd_tuplet
from oud.editor.notation_ops import set_annotation as _set_annotation
from oud.editor.notation_ops import set_barline as _set_barline
from oud.editor.notation_ops import set_dynamic as _set_dynamic
from oud.editor.notation_ops import set_fermata as _set_fermata
from oud.editor.notation_ops import set_highlight as _set_highlight
from oud.editor.notation_ops import set_hold as _set_hold
from oud.editor.notation_ops import set_ornament as _set_ornament
from oud.editor.notation_ops import set_repeat as _set_repeat
from oud.editor.notation_ops import set_slur as _set_slur
from oud.editor.notation_ops import set_tie as _set_tie
from oud.editor.state import EditorState


def cmd_time(state: EditorState, value: str) -> None:
    _cmd_time(state, value)


def cmd_barline(state: EditorState, value: str) -> None:
    _cmd_barline(state, value)


def cmd_repeat(state: EditorState, value: str) -> None:
    _cmd_repeat(state, value)


def cmd_dynamic(state: EditorState, value: str) -> None:
    _cmd_dynamic(state, value)


def cmd_fermata(state: EditorState, value: str) -> None:
    _cmd_fermata(state, value)


def cmd_arpeggio(state: EditorState, value: str) -> None:
    _cmd_arpeggio(state, value)


def cmd_separee(state: EditorState, value: str) -> None:
    _cmd_separee(state, value)


def cmd_tuplet(state: EditorState, value: str) -> None:
    _cmd_tuplet(state, value)


def set_ornament(state: EditorState, value: str) -> None:
    _set_ornament(state, value)


def set_annotation(state: EditorState, value: str) -> None:
    _set_annotation(state, value)


def set_highlight(state: EditorState, value: str) -> None:
    _set_highlight(state, value)


def set_barline(state: EditorState, value: str) -> None:
    _set_barline(state, value)


def set_repeat(state: EditorState, value: str) -> None:
    _set_repeat(state, value)


def set_dynamic(state: EditorState, value: str) -> None:
    _set_dynamic(state, value)


def set_fermata(state: EditorState, value: str) -> None:
    _set_fermata(state, value)


def set_slur(state: EditorState, value: str) -> None:
    _set_slur(state, value)


def set_tie(state: EditorState, value: str) -> None:
    _set_tie(state, value)


def set_hold(state: EditorState, value: str) -> None:
    _set_hold(state, value)
