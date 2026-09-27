from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.presentation.tui.controller import handle_key
from oud.services.plugins.model import RemoteTab
from petrucci.core.model import Bar, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "",
        "strings": "6",
        "flagstyle": "standard",
        "key": "C",
        "countdots": "off",
        "keys": "vim+arrows",
        "spacing": "12",
        "linelen": "80",
        "staffthick": "1",
        "fontstyle": "modern",
        "charstyle": "standard",
        "midipatch": "0",
        "grid": "off",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
    }
    return EditorState(piece, settings)


def test_help_mode_scroll_and_exit() -> None:
    state = _state()
    state.mode = Mode.HELP
    handle_key(state, ord("j"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.help_offset == 1
    handle_key(state, ord("k"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.help_offset == 0
    handle_key(state, ord("q"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.mode == "normal"


def test_info_mode_scroll_and_exit() -> None:
    state = _state()
    state.mode = Mode.INFO
    handle_key(state, ord("j"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.info_offset == 1
    handle_key(state, ord("k"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.info_offset == 0
    handle_key(state, ord("q"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.mode == "normal"


def test_plugin_mode_navigation_and_exit() -> None:
    state = _state()
    state.mode = Mode.PLUGIN
    state.plugin_items = [
        RemoteTab(title="One", url="https://example.com/one.tab"),
        RemoteTab(title="Two", url="https://example.com/two.tab"),
    ]
    handle_key(state, ord("j"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.plugin_index == 1
    handle_key(state, ord("k"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.plugin_index == 0
    handle_key(state, ord("q"), handle_insert=None, handle_normal=None, handle_command=None, handle_search=None)
    assert state.mode == "normal"
