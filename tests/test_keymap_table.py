"""Contract of the single key table (docs/ui-fix-plan.md phase 2)."""

from __future__ import annotations

import copy
from itertools import product
from pathlib import Path

import pytest
from helpers_keyscript import keyscript_state, press_keys

from oud.editor.commands.handlers.misc import show_help
from oud.editor.commands.help import help_lines
from oud.editor.commands.plugins.operations import PLUGIN_HANDLED_ACTIONS
from oud.editor.core.feedback.messages import READ_ONLY_VIEWER
from oud.editor.core.input.keycodes import DEFAULT_KEYCODES
from oud.editor.core.input.keymap import (
    ACTION_SPECS,
    Action,
    KeyProfile,
    KeyStyle,
    active_bindings,
    key_codes,
    keymap_for,
)
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import set_mode
from oud.editor.editing.primitives.tablature import is_french_fret, is_italian_fret
from oud.editor.interaction.insert.actions import _INSERT_HANDLERS
from oud.editor.interaction.normal.handlers import NORMAL_HANDLERS
from oud.presentation.tui.input.dispatch import prompt_bindings

TABLE_MODES = (Mode.NORMAL, Mode.VISUAL, Mode.INSERT, Mode.COMMAND, Mode.SEARCH, Mode.HELP, Mode.PLUGIN)
PROFILES = tuple(
    KeyProfile(style, arrows, read_only) for style, arrows, read_only in product(KeyStyle, (False, True), (False, True))
)


def _sequences(profile: KeyProfile, mode: Mode) -> dict[tuple[int, ...], set[Action]]:
    sequences: dict[tuple[int, ...], set[Action]] = {}
    for binding in active_bindings(profile, mode):
        for sequence in product(*(key_codes(name, DEFAULT_KEYCODES) for name in binding.keys)):
            sequences.setdefault(sequence, set()).add(binding.action)
    return sequences


@pytest.mark.parametrize("mode", TABLE_MODES)
@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: f"{p.label}-{'ro' if p.read_only else 'rw'}")
def test_every_key_sequence_has_one_meaning(profile: KeyProfile, mode: Mode) -> None:
    sequences = _sequences(profile, mode)

    ambiguous = {seq: actions for seq, actions in sequences.items() if len(actions) > 1}
    assert ambiguous == {}
    prefixes = {seq[:length] for seq in sequences for length in range(1, len(seq))}
    assert prefixes.isdisjoint(sequences), "a bound key must not also start a longer sequence"


def test_every_bound_action_has_a_spec_and_a_handler() -> None:
    assert set(ACTION_SPECS) == set(Action)
    for profile in PROFILES:
        for binding in active_bindings(profile, Mode.NORMAL) + active_bindings(profile, Mode.VISUAL):
            assert binding.action in NORMAL_HANDLERS, binding
        for binding in active_bindings(profile, Mode.INSERT):
            assert binding.action in _INSERT_HANDLERS, binding
        for binding in active_bindings(profile, Mode.PLUGIN):
            assert binding.action in PLUGIN_HANDLED_ACTIONS, binding


@pytest.mark.parametrize("mode", [Mode.COMMAND, Mode.SEARCH, Mode.HELP, Mode.PLUGIN])
def test_every_prompt_page_and_browser_closes_on_escape_and_ctrl_c(mode: Mode) -> None:
    keymap = keymap_for(keyscript_state(), mode)
    closing = {Mode.HELP: Action.PAGE_CLOSE, Mode.PLUGIN: Action.PLUGIN_CLOSE}.get(mode, Action.PROMPT_CANCEL)

    assert {27, 3} <= set(keymap.keys_for(closing))


def test_command_prompt_keys_come_from_the_table() -> None:
    state = keyscript_state()

    bindings = prompt_bindings(state, Mode.COMMAND)

    assert 3 in bindings.escape
    assert 9 in bindings.tab
    assert prompt_bindings(state, Mode.SEARCH).tab == ()


def test_insert_bindings_never_shadow_a_fret_or_duration() -> None:
    for profile in PROFILES:
        for binding in active_bindings(profile, Mode.INSERT):
            for name in binding.keys:
                if len(name) != 1:
                    continue
                assert not is_french_fret(name.lower()), binding
                assert not is_italian_fret(name), binding


def _mutating_sequences() -> list[tuple[str, ...]]:
    profile = KeyProfile(KeyStyle.VIM, True, read_only=True)
    return [binding.keys for binding in active_bindings(profile, Mode.NORMAL) if ACTION_SPECS[binding.action].mutates]


@pytest.mark.parametrize("keys", _mutating_sequences(), ids="".join)
def test_read_only_gate_refuses_every_mutating_key(keys: tuple[str, ...]) -> None:
    state = keyscript_state(settings_override={"bassstrings": "d2"})
    press_keys(state, ["i", "a", 27, "y", "y"])
    state.read_only = True
    state.message = ""
    before = (copy.deepcopy(state.piece), dict(state.overrides), len(state.undo_stack))
    codes = [key_codes(name, state.keycodes)[0] for name in keys]

    press_keys(state, codes)

    assert state.message == READ_ONLY_VIEWER
    assert state.mode == Mode.NORMAL
    assert (state.piece, state.overrides, len(state.undo_stack)) == before


def test_help_follows_the_active_key_style() -> None:
    vim = "\n".join(help_lines(keyscript_state(settings_override={"keys": "vim"})))
    casual = "\n".join(help_lines(keyscript_state(settings_override={"keys": "casual"})))

    assert "keys=vim" in vim
    assert "  h Ctrl-B " in vim
    assert "  a " in casual
    assert " h Ctrl-B" not in casual
    assert "Ctrl+1" not in vim + casual
    assert "1 2 4 8 6 3" not in vim + casual
    assert "  f{c} " in vim


def test_viewer_help_omits_editing_keys() -> None:
    state = keyscript_state()
    state.read_only = True

    text = "\n".join(help_lines(state))

    assert "(read-only viewer)" in text
    assert "INSERT MODE" not in text
    assert "delete note" not in text
    assert "next section or page" in text


def test_help_pager_shows_the_generated_help() -> None:
    state = keyscript_state()
    shown: list[str] = []

    def fake_less(argv: list[str], check: bool) -> None:
        assert check is False
        shown.append(Path(argv[1]).read_text(encoding="utf-8"))

    show_help(state, which_fn=lambda _name: "/usr/bin/less", run_fn=fake_less)

    assert shown == ["\n".join(help_lines(state)) + "\n"]


def test_mode_transitions_reject_unknown_modes() -> None:
    state = keyscript_state()

    with pytest.raises(ValueError, match="bogus"):
        set_mode(state, "bogus")
