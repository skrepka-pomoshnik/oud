from __future__ import annotations

DEFAULT_MESSAGE_TTL_TICKS = 24


def reset_transient_message_ttl(state) -> None:
    message = getattr(state, "message", "")
    if message:
        state.message_ttl_ticks = DEFAULT_MESSAGE_TTL_TICKS
    else:
        state.message_ttl_ticks = 0


def decay_transient_message(state) -> None:
    if getattr(state, "mode", "") not in {"normal", "insert"}:
        return
    if not getattr(state, "message", ""):
        return
    ticks = int(getattr(state, "message_ttl_ticks", 0))
    if ticks <= 0:
        state.message = ""
        return
    state.message_ttl_ticks = ticks - 1
    if state.message_ttl_ticks <= 0:
        state.message = ""
