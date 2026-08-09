from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from queue import Empty
from threading import Thread

from oud.editor.core.state import EditorState


def pdf_job_running(state: EditorState) -> bool:
    """Return whether a PDF build currently owns the output pipeline."""
    return state.pdf_job is not None and state.pdf_job.is_alive()


def drain_background_messages(state: EditorState) -> bool:
    """Publish worker notices without overwriting newer UI feedback."""
    changed = False
    while True:
        try:
            expected, result = state.background_messages.get_nowait()
        except Empty:
            return changed
        if not state.message or state.message == expected:
            state.message = result
            changed = True


def start_pdf_job(state: EditorState, target: str, build: Callable[[], str]) -> bool:
    """Start one non-blocking PDF build and report its result through editor state."""

    if pdf_job_running(state):
        state.message = "PDF build already running"
        return False

    pending = f"Building PDF: {Path(target).name}"

    def worker() -> None:
        try:
            result = build()
        except Exception as exc:
            result = f"PDF build failed: {exc}"
        state.background_messages.put((pending, result))

    state.message = pending
    state.pdf_job = Thread(target=worker, name="oud-pdf", daemon=True)
    state.pdf_job.start()
    return True
