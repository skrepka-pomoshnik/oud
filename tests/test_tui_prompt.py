from __future__ import annotations

from oud.presentation.tui.prompt import PromptBindings, update_prompt


def _bindings() -> PromptBindings:
    return PromptBindings(
        escape=(27,),
        backspace=(127,),
        enter=(10,),
        tab=(9,),
        history_up=(259,),
        history_down=(258,),
    )


def test_update_prompt_escape_cancel() -> None:
    result = update_prompt("abc", 27, _bindings(), history=[], history_index=None)
    assert result.cancel is True
    assert result.text == ""


def test_update_prompt_tab_completion_callback() -> None:
    result = update_prompt(
        "se",
        9,
        _bindings(),
        history=[],
        history_index=None,
        on_complete=lambda text: ("set style=", f"from:{text}"),
    )
    assert result.text == "set style="
    assert result.message == "from:se"


def test_update_prompt_history_navigation_and_submit() -> None:
    history = ["one", "two"]
    up = update_prompt("", 259, _bindings(), history=history, history_index=None)
    assert up.text == "two"
    assert up.history_index == 1
    down = update_prompt(
        up.text,
        258,
        _bindings(),
        history=history,
        history_index=up.history_index,
    )
    assert down.text == ""
    assert down.history_index is None
    submit = update_prompt("cmd", 10, _bindings(), history=history, history_index=None)
    assert submit.submit is True
    assert submit.text == "cmd"


def test_update_prompt_backspace_printable_and_ignored_key() -> None:
    result = update_prompt("ab", 127, _bindings(), history=[], history_index=None)
    assert result.text == "a"
    result = update_prompt("a", ord("b"), _bindings(), history=[], history_index=None)
    assert result.text == "ab"
    result = update_prompt("ab", 1, _bindings(), history=[], history_index=None)
    assert result.text == "ab"
