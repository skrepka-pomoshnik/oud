"""Command and search prompt input."""

from oud.presentation.tui.input.completion import complete_command_text
from oud.presentation.tui.input.dispatch import (
    complete_command,
    handle_command,
    handle_search,
    history_next,
    history_prev,
    parse_search,
)

__all__ = [
    "complete_command",
    "complete_command_text",
    "handle_command",
    "handle_search",
    "history_next",
    "history_prev",
    "parse_search",
]
