from __future__ import annotations

import copy

from oud.editor.bar_ops import clear_bar_contents, delete_bar, insert_bar, snapshot_bar
from oud.editor.edit_ops import record_action
from oud.editor.layout import bars_per_line, system_range
from oud.editor.messages import NO_BARS
from oud.editor.ops import delete_chord, insert_chord
from oud.editor.state import EditorState, UndoAction, YankedBar


def yank_bar(state: EditorState, index: int) -> None:
    if index < 0 or index >= len(state.piece.bars):
        return
    bar_copy = copy.deepcopy(state.piece.bars[index])
    overrides = {
        (0, s, c): value for (b, s, c), value in state.overrides.items() if b == index
    }
    durations = {
        (0, s, c): value for (b, s, c), value in state.durations.items() if b == index
    }
    annotations = {(0, c): value for (b, c), value in state.annotations.items() if b == index}
    ornaments = {(0, c): value for (b, c), value in state.ornaments.items() if b == index}
    dotted = {(0, c) for (b, c) in state.dotted if b == index}
    slurs = [(0, start, end) for (b, start, end) in state.slurs if b == index]
    ties = [(0, start, end) for (b, start, end) in state.ties if b == index]
    holds = [(0, start, end) for (b, start, end) in state.holds if b == index]
    state.yanked_bar = YankedBar(
        bar=bar_copy,
        overrides=overrides,
        durations=durations,
        annotations=annotations,
        ornaments=ornaments,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )


def paste_bar(state: EditorState, index: int) -> None:
    if state.yanked_bar is None:
        state.message = "No yanked bar"
        return
    insert_bar(state, index)
    bar_copy = copy.deepcopy(state.yanked_bar.bar)
    state.piece.bars[index] = bar_copy
    for (b, s, c), value in state.yanked_bar.overrides.items():
        state.overrides[(index + b, s, c)] = value
    for (b, s, c), value in state.yanked_bar.durations.items():
        state.durations[(index + b, s, c)] = value
    for (b, c), value in state.yanked_bar.annotations.items():
        state.annotations[(index + b, c)] = value
    for (b, c), value in state.yanked_bar.ornaments.items():
        state.ornaments[(index + b, c)] = value
    for (b, c) in state.yanked_bar.dotted:
        state.dotted.add((index + b, c))
    for b, start, end in state.yanked_bar.slurs:
        state.slurs.append((index + b, start, end))
    for b, start, end in state.yanked_bar.ties:
        state.ties.append((index + b, start, end))
    for b, start, end in state.yanked_bar.holds:
        state.holds.append((index + b, start, end))
    state.modified = True


def cmd_bar(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if action in ("add", "after"):
        prev_breaks = set(state.stave_breaks)
        insert_bar(state, state.cursor_bar + 1)
        new_breaks = set(state.stave_breaks)
        record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar + 1, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_bar = min(state.cursor_bar + 1, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar added"
        return
    if action in ("before", "insert"):
        prev_breaks = set(state.stave_breaks)
        insert_bar(state, state.cursor_bar)
        new_breaks = set(state.stave_breaks)
        record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_col = 0
        state.message = "Bar inserted"
        return
    if action in ("del", "delete", "remove"):
        if not state.piece.bars:
            state.message = NO_BARS
            return
        index = state.cursor_bar
        if len(state.piece.bars) == 1:
            snapshot = snapshot_bar(state, index)
            clear_bar_contents(state, index)
            record_action(
                state,
                UndoAction(
                    kind="bar-clear",
                    data={"index": index, "snapshot": snapshot},
                ),
            )
        else:
            snapshot = snapshot_bar(state, index)
            prev_breaks = set(state.stave_breaks)
            delete_bar(state, state.cursor_bar)
            new_breaks = set(state.stave_breaks)
            record_action(
                state,
                UndoAction(
                    kind="bar-delete",
                    data={
                        "index": index,
                        "snapshot": snapshot,
                        "prev": prev_breaks,
                        "new": new_breaks,
                    },
                ),
            )
        state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar deleted"
        return
    state.message = "Bar action: add/after/before/insert/del"


def cmd_stave(state: EditorState, args: str) -> None:
    action = args.strip() or "break"
    per_line = bars_per_line(state, state.screen_width or 80)
    start, end = system_range(state, state.cursor_bar, per_line)
    if action in ("break", "split"):
        idx = state.cursor_bar + 1
        if idx < len(state.piece.bars):
            prev = set(state.stave_breaks)
            state.stave_breaks.add(idx)
            record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break added"
        else:
            state.message = "No bar to break after"
        return
    if action in ("join", "merge"):
        idx = state.cursor_bar + 1
        if idx in state.stave_breaks:
            prev = set(state.stave_breaks)
            state.stave_breaks.discard(idx)
            record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break removed"
        else:
            state.message = "No break at cursor"
        return
    if action in ("new", "insert"):
        idx = state.cursor_bar + 1
        prev_breaks = set(state.stave_breaks)
        insert_bar(state, idx)
        state.stave_breaks.add(idx)
        record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": idx, "prev": prev_breaks, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Stave inserted"
        return
    if action in ("del", "delete", "remove"):
        if start >= end:
            state.message = "No stave to delete"
            return
        snapshots = [snapshot_bar(state, idx) for idx in range(start, end)]
        prev_breaks = set(state.stave_breaks)
        for _ in range(end - start):
            delete_bar(state, start)
        state.stave_breaks = {
            b - (end - start) if b >= end else b
            for b in state.stave_breaks
            if b < start or b >= end
        }
        record_action(
            state,
            UndoAction(
                kind="bars-delete",
                data={
                    "start": start,
                    "count": end - start,
                    "snapshots": snapshots,
                    "prev": prev_breaks,
                    "new": set(state.stave_breaks),
                },
            ),
        )
        state.cursor_bar = max(0, min(start, len(state.piece.bars) - 1))
        state.cursor_col = 0
        state.message = "Stave deleted"
        return
    state.message = "Stave action: break/join/new/del"


def cmd_chord(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    if action in ("add", "insert"):
        prev = copy.deepcopy(bar.chords)
        insert_chord(bar, state.bar_width, state.cursor_col)
        record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        state.modified = True
        state.message = "Chord added"
        return
    if action in ("del", "delete", "remove"):
        prev = copy.deepcopy(bar.chords)
        if delete_chord(bar, state.bar_width, state.cursor_col):
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
            state.modified = True
            state.message = "Chord deleted"
        else:
            state.message = "No chord at cursor"
        return
    state.message = "Chord action: add/del"
