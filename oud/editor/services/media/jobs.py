from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Thread

from oud.editor.core.state import EditorState


def start_pdf_job(state: EditorState, target: str, build: Callable[[], str]) -> bool:
    """Start one non-blocking PDF build and report its result through editor state."""

    if state.pdf_job is not None and state.pdf_job.is_alive():
        state.message = "PDF build already running"
        return False

    def worker() -> None:
        try:
            state.message = build()
        except Exception as exc:
            state.message = f"PDF build failed: {exc}"

    state.message = f"Building PDF: {Path(target).name}"
    state.pdf_job = Thread(target=worker, name="oud-pdf", daemon=True)
    state.pdf_job.start()
    return True
