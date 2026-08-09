from __future__ import annotations

import copy

from oud.editor.core.feedback.messages import NO_BARS
from oud.editor.core.state import EditorState, UndoAction, YankedBar
from oud.editor.editing.primitives.bars import clear_bar_contents, delete_bar, insert_bar, snapshot_bar
from oud.editor.editing.primitives.edits import record_action
from oud.editor.editing.primitives.ranges import (
    BarRange,
    ChordRange,
    bar_range_from_cursor,
    chord_range_at_col_count,
    deletable_bar_range_from_cursor,
)
from oud.editor.editing.primitives.tablature import chord_index_at_col, insert_chord
from oud.editor.navigation.layout import bars_per_line, system_range
from oud.editor.navigation.motions import apply_motion_target, target_home_bar
from petrucci.core.model import Bar


def _inserted_chord_range(
    state: EditorState,
    *,
    previous_count: int,
    previous_index: int | None,
) -> ChordRange:
    """Best-effort inserted chord span for current cursor insertion semantics."""
    bar = state.piece.bars[state.cursor_bar]
    if len(bar.chords) <= previous_count:
        return ChordRange(state.cursor_bar, 0, 0)
    if previous_index is None:
        return ChordRange.single(state.cursor_bar, 0).clamp(len(bar.chords))
    insert_idx = max(0, min(previous_index, len(bar.chords) - 1))
    return ChordRange.single(state.cursor_bar, insert_idx).clamp(len(bar.chords))


def _parse_chord_action_args(args: str) -> tuple[str, int] | None:
    tokens = args.split()
    action = (tokens[0] if tokens else "add").strip()
    count = 1
    if len(tokens) > 1:
        try:
            count = max(1, int(tokens[1]))
        except ValueError:
            return None
    return (action, count)


def _cmd_chord_insert(state: EditorState, bar: Bar, count: int) -> None:
    prev = copy.deepcopy(bar.chords)
    before_count = len(bar.chords)
    prev_idx = chord_index_at_col(bar, state.bar_width, state.cursor_col)
    for _ in range(count):
        insert_chord(bar, state.bar_width, state.cursor_col)
    inserted_range = ChordRange.from_start_count(
        state.cursor_bar,
        _inserted_chord_range(
            state,
            previous_count=before_count,
            previous_index=prev_idx,
        ).start,
        len(bar.chords) - before_count,
    ).clamp(len(bar.chords))
    record_action(
        state,
        UndoAction(
            kind="chords",
            data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
        ),
    )
    state.modified = True
    if inserted_range.count == 1:
        state.message = "Chord added"
    else:
        state.message = f"Chords added: {inserted_range.count}"


def _cmd_chord_delete(state: EditorState, bar: Bar, count: int) -> None:
    prev = copy.deepcopy(bar.chords)
    chord_range = chord_range_at_col_count(
        bar,
        state.bar_width,
        state.cursor_col,
        count=count,
        bar_index=state.cursor_bar,
    )
    if chord_range.is_empty:
        state.message = "No chord at cursor"
        return
    for idx in reversed(list(chord_range.indices())):
        bar.chords.pop(idx)
    record_action(
        state,
        UndoAction(
            kind="chords",
            data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
        ),
    )
    state.modified = True
    if chord_range.count == 1:
        state.message = "Chord deleted"
    else:
        state.message = f"Chords deleted: {chord_range.count}"


def _cmd_chord_yank(state: EditorState, bar: Bar, count: int) -> None:
    chord_range = chord_range_at_col_count(
        bar,
        state.bar_width,
        state.cursor_col,
        count=count,
        bar_index=state.cursor_bar,
    )
    if chord_range.is_empty:
        state.message = "No chord at cursor"
        return
    state.yanked_chords = copy.deepcopy(
        [bar.chords[idx] for idx in chord_range.indices()],
    )
    if chord_range.count == 1:
        state.message = "Chord yanked"
    else:
        state.message = f"Chords yanked: {chord_range.count}"


def _cmd_chord_paste(state: EditorState, bar: Bar, count: int) -> None:
    if not state.yanked_chords:
        state.message = "No yanked chords"
        return
    prev = copy.deepcopy(bar.chords)
    before_count = len(bar.chords)
    prev_idx = chord_index_at_col(bar, state.bar_width, state.cursor_col)
    insert_idx = 0 if prev_idx is None else max(0, min(prev_idx, len(bar.chords)))
    payload: list = []
    for _ in range(max(1, count)):
        payload.extend(copy.deepcopy(state.yanked_chords))
    for offset, chord in enumerate(payload):
        bar.chords.insert(insert_idx + offset, chord)
    inserted_range = ChordRange.from_start_count(
        state.cursor_bar,
        insert_idx,
        len(bar.chords) - before_count,
    ).clamp(len(bar.chords))
    record_action(
        state,
        UndoAction(
            kind="chords",
            data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
        ),
    )
    state.modified = True
    if inserted_range.count == 1:
        state.message = "Chord pasted"
    else:
        state.message = f"Chords pasted: {inserted_range.count}"


def _capture_yanked_bar(state: EditorState, index: int) -> YankedBar | None:
    bar_range = BarRange.single(index).clamp(len(state.piece.bars))
    if bar_range.is_empty:
        return None
    index = bar_range.start
    bar_copy = copy.deepcopy(state.piece.bars[index])
    overrides = {(0, s, c): value for (b, s, c), value in state.overrides.items() if b == index}
    durations = {(0, s, c): value for (b, s, c), value in state.durations.items() if b == index}
    annotations = {(0, c): value for (b, c), value in state.annotations.items() if b == index}
    ornaments = {(0, c): value for (b, c), value in state.ornaments.items() if b == index}
    dotted = {(0, c) for (b, c) in state.dotted if b == index}
    slurs = [(0, start, end) for (b, start, end) in state.slurs if b == index]
    ties = [(0, start, end) for (b, start, end) in state.ties if b == index]
    holds = [(0, start, end) for (b, start, end) in state.holds if b == index]
    glisses = [(0, start, end) for (b, start, end) in state.glisses if b == index]
    marks = {name: (0, string, col) for name, (b, string, col) in state.marks.items() if b == index}
    return YankedBar(
        bar=bar_copy,
        overrides=overrides,
        durations=durations,
        annotations=annotations,
        ornaments=ornaments,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
        glisses=glisses,
        marks=marks,
    )


def yank_bar(state: EditorState, index: int, *, count: int = 1) -> None:
    bar_range = BarRange.from_start_count(index, count).clamp(len(state.piece.bars))
    if bar_range.is_empty:
        return
    captured = [item for item in (_capture_yanked_bar(state, idx) for idx in bar_range.indices()) if item is not None]
    if not captured:
        return
    state.yanked_bar = copy.deepcopy(captured[0])
    state.yanked_bars = copy.deepcopy(captured)


def yank_bar_range(state: EditorState, bar_range: BarRange) -> int:
    bar_range = bar_range.clamp(len(state.piece.bars))
    if bar_range.is_empty:
        state.message = NO_BARS
        return 0
    yank_bar(state, bar_range.start, count=bar_range.count)
    state.message = "Bar yanked" if bar_range.count == 1 else f"Bars yanked: {bar_range.count}"
    return bar_range.count


def _paste_one_yanked_bar(state: EditorState, index: int, yanked: YankedBar) -> None:  # noqa: C901
    insert_bar(state, index)
    bar_copy = copy.deepcopy(yanked.bar)
    state.piece.bars[index] = bar_copy
    for (b, s, c), value in yanked.overrides.items():
        state.overrides[(index + b, s, c)] = value
    for (b, s, c), value in yanked.durations.items():
        state.durations[(index + b, s, c)] = value
    for (b, c), value in yanked.annotations.items():
        state.annotations[(index + b, c)] = value
    for (b, c), value in yanked.ornaments.items():
        state.ornaments[(index + b, c)] = value
    for b, c in yanked.dotted:
        state.dotted.add((index + b, c))
    for b, start, end in yanked.slurs:
        state.slurs.append((index + b, start, end))
    for b, start, end in yanked.ties:
        state.ties.append((index + b, start, end))
    for b, start, end in yanked.holds:
        state.holds.append((index + b, start, end))
    for b, start, end in yanked.glisses:
        state.glisses.append((index + b, start, end))
    for name, (b, string, col) in yanked.marks.items():
        state.marks[name] = (index + b, string, col)
    state.modified = True


def paste_bar(state: EditorState, index: int, *, count: int = 1) -> None:
    if state.yanked_bar is None and not state.yanked_bars:
        state.message = "No yanked bar"
        return
    prev_breaks = set(state.stave_breaks)
    base_payload = state.yanked_bars or ([state.yanked_bar] if state.yanked_bar is not None else [])
    payload: list[YankedBar] = []
    for _ in range(max(1, count)):
        payload.extend(copy.deepcopy(base_payload))
    for offset, yanked in enumerate(payload):
        _paste_one_yanked_bar(state, index + offset, yanked)
    inserted_snapshots = [snapshot_bar(state, index + offset) for offset in range(len(payload))]
    record_action(
        state,
        UndoAction(
            kind="bars-insert",
            data={
                "start": index,
                "count": len(payload),
                "snapshots": inserted_snapshots,
                "prev": prev_breaks,
                "new": set(state.stave_breaks),
            },
        ),
    )
    state.message = "Bar pasted" if len(payload) == 1 else f"Bars pasted: {len(payload)}"


def _parse_bar_action_args(args: str) -> tuple[str, int] | None:
    tokens = args.split()
    action = (tokens[0] if tokens else "add").strip()
    count = 1
    if len(tokens) > 1:
        try:
            count = max(1, int(tokens[1]))
        except ValueError:
            return None
    return (action, count)


def _cmd_bar_add_after(state: EditorState) -> None:
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
    apply_motion_target(state, target_home_bar(state, state.cursor_bar + 1))
    state.message = "Bar added"


def _cmd_bar_insert_before(state: EditorState) -> None:
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
    apply_motion_target(state, target_home_bar(state, state.cursor_bar))
    state.message = "Bar inserted"


def _cmd_bar_paste(state: EditorState, count: int) -> None:
    paste_bar(state, state.cursor_bar + 1, count=count)


def delete_bar_range(state: EditorState, bar_range: BarRange) -> int:
    if not state.piece.bars:
        state.message = NO_BARS
        return 0
    bar_range = bar_range.clamp(len(state.piece.bars))
    if bar_range.is_empty:
        state.message = NO_BARS
        return 0
    index = bar_range.start
    if len(state.piece.bars) == 1:
        snapshot = snapshot_bar(state, index)
        clear_bar_contents(state, index)
        record_action(
            state,
            UndoAction(kind="bar-clear", data={"index": index, "snapshot": snapshot}),
        )
        apply_motion_target(state, target_home_bar(state, state.cursor_bar))
        state.message = "Bar deleted"
        return 1
    if bar_range.count == 1:
        snapshot = snapshot_bar(state, index)
        prev_breaks = set(state.stave_breaks)
        delete_bar(state, index)
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
        apply_motion_target(state, target_home_bar(state, index))
        state.message = "Bar deleted"
        return 1
    snapshots = [snapshot_bar(state, idx) for idx in bar_range.indices()]
    prev_breaks = set(state.stave_breaks)
    for _ in range(bar_range.count):
        delete_bar(state, bar_range.start)
    record_action(
        state,
        UndoAction(
            kind="bars-delete",
            data={
                "start": bar_range.start,
                "count": bar_range.count,
                "snapshots": snapshots,
                "prev": prev_breaks,
                "new": set(state.stave_breaks),
            },
        ),
    )
    apply_motion_target(state, target_home_bar(state, bar_range.start))
    state.message = f"Bars deleted: {bar_range.count}"
    return bar_range.count


def _cmd_bar_yank(state: EditorState, count: int) -> None:
    yank_bar_range(state, bar_range_from_cursor(state, count))


def _cmd_bar_delete(state: EditorState, count: int) -> None:
    delete_bar_range(state, deletable_bar_range_from_cursor(state, count))


def cmd_bar(state: EditorState, args: str) -> None:
    parsed = _parse_bar_action_args(args)
    if parsed is None:
        state.message = "Bar count must be a positive integer"
        return
    action, count = parsed
    if action in ("add", "after"):
        _cmd_bar_add_after(state)
        return
    if action in ("before", "insert"):
        _cmd_bar_insert_before(state)
        return
    if action in ("yank", "copy"):
        _cmd_bar_yank(state, count)
        return
    if action in ("paste", "put"):
        _cmd_bar_paste(state, count)
        return
    if action in ("del", "delete", "remove"):
        _cmd_bar_delete(state, count)
        return
    state.message = "Bar action: add/after/before/insert/del/yank/paste [count]"


def cmd_stave(state: EditorState, args: str) -> None:  # noqa: C901
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
        bar_range = BarRange.from_bounds(start, end).clamp(len(state.piece.bars))
        if bar_range.is_empty:
            state.message = "No stave to delete"
            return
        snapshots = [snapshot_bar(state, idx) for idx in bar_range.indices()]
        prev_breaks = set(state.stave_breaks)
        for _ in range(bar_range.count):
            delete_bar(state, bar_range.start)
        record_action(
            state,
            UndoAction(
                kind="bars-delete",
                data={
                    "start": bar_range.start,
                    "count": bar_range.count,
                    "snapshots": snapshots,
                    "prev": prev_breaks,
                    "new": set(state.stave_breaks),
                },
            ),
        )
        apply_motion_target(state, target_home_bar(state, bar_range.start))
        state.message = "Stave deleted"
        return
    state.message = "Stave action: break/join/new/del"


def cmd_chord(state: EditorState, args: str) -> None:
    parsed = _parse_chord_action_args(args)
    if parsed is None:
        state.message = "Chord count must be a positive integer"
        return
    action, count = parsed
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    if action in ("add", "insert"):
        _cmd_chord_insert(state, bar, count)
        return
    if action in ("del", "delete", "remove"):
        _cmd_chord_delete(state, bar, count)
        return
    if action in ("yank", "copy"):
        _cmd_chord_yank(state, bar, count)
        return
    if action in ("paste", "put"):
        _cmd_chord_paste(state, bar, count)
        return
    state.message = "Chord action: add/del/yank/paste [count]"
