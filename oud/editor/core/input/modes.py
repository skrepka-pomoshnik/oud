from __future__ import annotations

from enum import StrEnum


class Mode(StrEnum):
    """Editor input modes. Values match the strings renderers already receive."""

    NORMAL = "normal"
    INSERT = "insert"
    REPLACE = "replace"
    VISUAL = "visual"
    VISUAL_LINE = "visual_line"
    COMMAND = "command"
    SEARCH = "search"
    HELP = "help"
    INFO = "info"
    NOTES = "notes"
    PLUGIN = "plugin"


VISUAL_MODES = frozenset({Mode.VISUAL, Mode.VISUAL_LINE})
INSERT_MODES = frozenset({Mode.INSERT, Mode.REPLACE})
OVERLAY_MODES = frozenset({Mode.HELP, Mode.INFO, Mode.NOTES})
