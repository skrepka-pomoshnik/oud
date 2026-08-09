from __future__ import annotations

from enum import StrEnum


class MessageLevel(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CONFIRM = "confirm"


def infer_message_level(text: str) -> MessageLevel:
    lowered = text.strip().lower()
    if not lowered:
        return MessageLevel.INFO
    if lowered.startswith(("save as", "unsaved changes", "file exists")) or "repeat write" in lowered:
        return MessageLevel.CONFIRM
    if lowered.startswith(("import warning", "warning", "unsupported")):
        return MessageLevel.WARNING
    if lowered.startswith(("wrote ", "exported ", "opened ", "reloaded:", "downloaded ")):
        return MessageLevel.SUCCESS
    if lowered.startswith(
        (
            "error",
            "invalid",
            "missing",
            "unknown",
            "could not",
            "write failed",
            "read-only",
            "no path",
            "no source",
        ),
    ):
        return MessageLevel.ERROR
    return MessageLevel.INFO


MISSING_LESS = "Missing less"
NO_PATH = "No path"
NO_SOURCE_PATH = "No source path"
NO_BARS = "No bars"
UNSAVED_QUIT = "Unsaved changes. Press q/Ctrl-C again to quit."
UNSAVED_QUIT_CMD = "Unsaved changes. Use :q! to quit or :w to save."
READ_ONLY_VIEWER = "Read-only viewer mode"
