from scripts.checks.architecture_debt import MAX_COMPLEXITY, MAX_MODULE_LINES, _is_ui_only_module


def test_architecture_limits_are_explicit() -> None:
    assert MAX_COMPLEXITY == 7
    assert MAX_MODULE_LINES == 1_000


def test_ui_only_module_classifier_is_directional() -> None:
    assert _is_ui_only_module("curses")
    assert _is_ui_only_module("oud.presentation.tui.loop")
    assert not _is_ui_only_module("oud.presentation.ui")
    assert not _is_ui_only_module("petrucci.rendering")
