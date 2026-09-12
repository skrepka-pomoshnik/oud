from __future__ import annotations

import copy
from dataclasses import dataclass

from oud.editor.core.coordinates import string_index
from oud.editor.core.state import EditorState, UndoAction
from oud.editor.editing.primitives.edits import record_action, undo_group
from oud.editor.editing.primitives.tablature import french_to_fret, fret_to_french, fret_to_italian, italian_to_fret
from oud.editor.editing.tab.assignment import AssignmentPolicy, assign_chord_pitches
from petrucci.core.music.tuning import parse_tuning_pitches, tuning_preset
from petrucci.rendering.primitives.utils import chord_positions


@dataclass
class TransformReport:
    changed: int = 0
    skipped: int = 0
    first_diagnostic: str | None = None

    @property
    def total(self) -> int:
        return self.changed + self.skipped


def _policy_from_settings(state: EditorState) -> AssignmentPolicy:
    minimum_fret = int(state.settings.get("minimumfret", "0") or "0")
    max_stretch_raw = int(state.settings.get("maxstretch", "0") or "0")
    max_stretch = max_stretch_raw if max_stretch_raw > 0 else None
    restrain_open = state.settings.get("restrainopenstrings", "off") == "on"
    return AssignmentPolicy(
        minimum_fret=minimum_fret,
        max_stretch=max_stretch,
        restrain_open_strings=restrain_open,
    )


def _parse_override_fret(ch: str, style: str) -> int | None:
    return italian_to_fret(ch) if style == "italian" else french_to_fret(ch)


def _format_override_fret(fret: int, style: str) -> str | None:
    return fret_to_italian(fret) if style == "italian" else fret_to_french(fret)


def _note_pitch(note, tuning_pitches: list[int]) -> int | None:
    idx = note.string - 1
    if idx < 0 or idx >= len(tuning_pitches):
        return None
    return tuning_pitches[idx] + note.fret


def _editor_tuning_pitches(text: str, *, strings: int | None = None) -> list[int]:
    pitches = parse_tuning_pitches(text)
    if strings is not None:
        return pitches[:strings]
    return pitches


def _snapshot_score_transform(state: EditorState) -> dict[str, object]:
    return {
        "piece": copy.deepcopy(state.piece),
        "overrides": dict(state.overrides),
        "settings_tuning": state.settings.get("tuning"),
        "settings_strings": state.settings.get("strings"),
    }


def _record_score_transform(
    state: EditorState,
    *,
    before: dict[str, object],
    label: str,
) -> None:
    after = _snapshot_score_transform(state)
    record_action(
        state,
        UndoAction(
            kind="score-transform",
            data={
                "label": label,
                "before": before,
                "after": after,
            },
        ),
    )


def _source_chord_pitches(chord, source_tuning: list[int], semitones: int) -> list[int] | None:
    pitches: list[int] = []
    for note in chord.notes:
        pitch = _note_pitch(note, source_tuning)
        if pitch is None:
            return None
        pitches.append(pitch + semitones)
    return pitches


def _apply_chord_assignments(chord, assigned_notes) -> int:
    changed = 0
    for note, assigned in zip(chord.notes, assigned_notes, strict=False):
        if note.string != assigned.string or note.fret != assigned.fret:
            changed += 1
        note.string = assigned.string
        note.fret = assigned.fret
    return changed


def _reassign_chord_notes(
    chord,
    *,
    source_tuning: list[int],
    target_tuning: list[int],
    semitones: int,
    policy: AssignmentPolicy,
) -> TransformReport:
    report = TransformReport()
    if not chord.notes:
        return report
    pitches = _source_chord_pitches(chord, source_tuning, semitones)
    if pitches is None:
        report.skipped += 1
        return report
    result = assign_chord_pitches(pitches, target_tuning, policy=policy)
    if not result.ok or len(result.notes) != len(chord.notes):
        report.skipped += len(chord.notes)
        if report.first_diagnostic is None and result.diagnostics:
            report.first_diagnostic = result.diagnostics[0].code
        return report
    report.changed = _apply_chord_assignments(chord, result.notes)
    return report


def _reassign_bar_notes(
    bar,
    *,
    source_tuning: list[int],
    target_tuning: list[int],
    semitones: int,
    policy: AssignmentPolicy,
) -> TransformReport:
    report = TransformReport()
    for note in bar.notes:
        pitch = _note_pitch(note, source_tuning)
        if pitch is None:
            report.skipped += 1
            continue
        result = assign_chord_pitches([pitch + semitones], target_tuning, policy=policy)
        if not result.ok or not result.notes:
            report.skipped += 1
            if report.first_diagnostic is None and result.diagnostics:
                report.first_diagnostic = result.diagnostics[0].code
            continue
        assigned = result.notes[0]
        if note.string != assigned.string or note.fret != assigned.fret:
            report.changed += 1
        note.string = assigned.string
        note.fret = assigned.fret
    return report


def _override_pitch(
    key: tuple[int, int, int],
    value: str,
    *,
    style: str,
    source_tuning: list[int],
    semitones: int,
) -> tuple[int, str, int] | None:
    fret = _parse_override_fret(value, style)
    if fret is None:
        return None
    _bar_idx, s_idx, _col = key
    if s_idx < 0 or s_idx >= len(source_tuning):
        return (0, value, -1)
    return (source_tuning[s_idx] + fret + semitones, value, 0)


def _format_reassigned_override(
    pitch: int,
    *,
    target_tuning: list[int],
    policy: AssignmentPolicy,
    style: str,
) -> tuple[str, int | None, str | None]:
    result = assign_chord_pitches([pitch], target_tuning, policy=policy)
    if not result.ok or not result.notes:
        return "", None, result.diagnostics[0].code if result.diagnostics else "assignment_failed"
    out = _format_override_fret(result.notes[0].fret, style)
    if out is None:
        return "", None, "override_format_failed"
    return out, result.notes[0].string - 1, None


def _reassigned_override(
    key: tuple[int, int, int],
    value: str,
    *,
    style: str,
    source_tuning: list[int],
    target_tuning: list[int],
    semitones: int,
    policy: AssignmentPolicy,
) -> tuple[tuple[int, int, int], str, bool, str | None]:
    pitch_info = _override_pitch(
        key,
        value,
        style=style,
        source_tuning=source_tuning,
        semitones=semitones,
    )
    if pitch_info is None:
        return key, value, False, None
    pitch, _source_value, pitch_error = pitch_info
    if pitch_error:
        return key, value, False, "source_string_out_of_range"
    out, target_string, error = _format_reassigned_override(
        pitch,
        target_tuning=target_tuning,
        policy=policy,
        style=style,
    )
    if error is not None or target_string is None:
        return key, value, False, error or "assignment_failed"
    bar_idx, _string, col = key
    new_key = (bar_idx, target_string, col)
    return new_key, out, new_key != key or out != value, None


def _record_transform_skip(report: TransformReport, diagnostic: str) -> None:
    report.skipped += 1
    if report.first_diagnostic is None:
        report.first_diagnostic = diagnostic


def _reassign_overrides(
    state: EditorState,
    *,
    source_tuning: list[int],
    target_tuning: list[int],
    semitones: int,
    policy: AssignmentPolicy,
) -> TransformReport:
    report = TransformReport()
    style = state.settings.get("style", "french")
    new_overrides: dict[tuple[int, int, int], str] = {}
    # Process in deterministic order to keep collision behavior stable.
    for key in sorted(state.overrides.keys()):
        value = state.overrides[key]
        new_key, out, changed, diagnostic = _reassigned_override(
            key,
            value,
            style=style,
            source_tuning=source_tuning,
            target_tuning=target_tuning,
            semitones=semitones,
            policy=policy,
        )
        if diagnostic is not None:
            _record_transform_skip(report, diagnostic)
            new_overrides[key] = value
            continue
        if new_key in new_overrides and new_key != key:
            _record_transform_skip(report, "override_collision")
            new_overrides[key] = value
            continue
        if changed:
            report.changed += 1
        new_overrides[new_key] = out
    state.overrides = new_overrides
    return report


def _resolve_transform_tuning(
    state: EditorState,
    target_tuning_text: str,
    target_strings: int | None,
) -> tuple[list[int], list[int], int, str | None]:
    source_tuning = _editor_tuning_pitches(
        state.settings.get("tuning", ""),
        strings=state.piece.strings,
    )
    target_tuning = _editor_tuning_pitches(target_tuning_text)
    if not source_tuning:
        return [], [], 0, "Invalid tuning for transform"
    if not target_tuning:
        return [], [], 0, "Invalid target tuning"
    resolved_strings = target_strings if target_strings is not None else len(target_tuning)
    target_tuning = target_tuning[:resolved_strings]
    if not target_tuning:
        return [], [], 0, "Invalid target tuning"
    return source_tuning, target_tuning, resolved_strings, None


def _merge_transform_report(target: TransformReport, source: TransformReport) -> None:
    target.changed += source.changed
    target.skipped += source.skipped
    if target.first_diagnostic is None:
        target.first_diagnostic = source.first_diagnostic


def _transform_bars(
    state: EditorState,
    *,
    source_tuning: list[int],
    target_tuning: list[int],
    semitones: int,
    policy: AssignmentPolicy,
) -> TransformReport:
    report = TransformReport()
    for bar in state.piece.bars:
        _merge_transform_report(
            report,
            _reassign_bar_notes(
                bar,
                source_tuning=source_tuning,
                target_tuning=target_tuning,
                semitones=semitones,
                policy=policy,
            ),
        )
        for chord in bar.chords:
            _merge_transform_report(
                report,
                _reassign_chord_notes(
                    chord,
                    source_tuning=source_tuning,
                    target_tuning=target_tuning,
                    semitones=semitones,
                    policy=policy,
                ),
            )
    return report


def transform_score_to_tuning(
    state: EditorState,
    *,
    target_tuning_text: str,
    target_strings: int | None = None,
    semitones: int = 0,
    label: str,
    update_settings_tuning: bool = False,
) -> TransformReport:
    source_tuning, target_tuning, target_strings, error = _resolve_transform_tuning(
        state,
        target_tuning_text,
        target_strings,
    )
    if error is not None:
        state.message = error
        return TransformReport()

    before = _snapshot_score_transform(state)
    policy = _policy_from_settings(state)
    report = _transform_bars(
        state,
        source_tuning=source_tuning,
        target_tuning=target_tuning,
        semitones=semitones,
        policy=policy,
    )
    ro = _reassign_overrides(
        state,
        source_tuning=source_tuning,
        target_tuning=target_tuning,
        semitones=semitones,
        policy=policy,
    )
    report.changed += ro.changed
    report.skipped += ro.skipped
    if report.first_diagnostic is None:
        report.first_diagnostic = ro.first_diagnostic

    state.piece.strings = max(4, min(13, target_strings))
    state.cursor_string = min(state.cursor_string, state.piece.strings - 1)
    state.settings["strings"] = str(state.piece.strings)
    if update_settings_tuning:
        state.settings["tuning"] = target_tuning_text
    state.modified = True
    _record_score_transform(state, before=before, label=label)
    return report


def cmd_transpose(state: EditorState, value: str) -> None:
    text = value.strip()
    if not text:
        state.message = "Transpose requires semitones"
        return
    try:
        semitones = int(text)
    except ValueError:
        state.message = "Transpose must be int"
        return
    tuning_text = state.settings.get("tuning", "")
    label = f"transpose {semitones}"
    with undo_group(state, label=label):
        report = transform_score_to_tuning(
            state,
            target_tuning_text=tuning_text,
            target_strings=state.piece.strings,
            semitones=semitones,
            label=label,
            update_settings_tuning=False,
        )
    if report.total == 0:
        return
    diag = f" ({report.first_diagnostic})" if report.skipped and report.first_diagnostic else ""
    state.message = f"Transposed {semitones:+d}: changed {report.changed}, skipped {report.skipped}{diag}"


def cmd_retune(state: EditorState, value: str) -> None:
    raw = value.strip()
    if not raw:
        state.message = "Retune requires tuning or preset"
        return
    target_tuning = tuning_preset(raw) or raw
    target_pitches = parse_tuning_pitches(target_tuning)
    if not target_pitches:
        state.message = "Invalid target tuning"
        return
    label = f"retune {raw}"
    with undo_group(state, label=label):
        report = transform_score_to_tuning(
            state,
            target_tuning_text=target_tuning,
            target_strings=len(target_pitches),
            semitones=0,
            label=label,
            update_settings_tuning=True,
        )
    if report.total == 0:
        return
    diag = f" ({report.first_diagnostic})" if report.skipped and report.first_diagnostic else ""
    state.message = f"Retuned: changed {report.changed}, skipped {report.skipped}{diag}"


def _find_cursor_chord_for_shift(state: EditorState):
    if not state.piece.bars:
        state.message = "No bars"
        return None, None
    bar = state.piece.bars[state.cursor_bar]
    if not bar.chords:
        state.message = "No chord at cursor"
        return None, None
    positions = chord_positions(bar, state.bar_width, state.current_duration or 4)
    chord_idx = next(
        (i for i, (col, _d, _dot) in enumerate(positions) if col == state.cursor_col),
        None,
    )
    if chord_idx is None or chord_idx >= len(bar.chords):
        state.message = "No chord at cursor"
        return None, None
    return bar, bar.chords[chord_idx]


def _assign_shifted_chord(
    state: EditorState,
    chord,
    *,
    forced_note_index: int,
    forced_target_string: int,
) -> bool:
    source_tuning = _editor_tuning_pitches(
        state.settings.get("tuning", ""),
        strings=state.piece.strings,
    )
    if not source_tuning:
        state.message = "Invalid tuning"
        return False
    pitches: list[int] = []
    for note in chord.notes:
        pitch = _note_pitch(note, source_tuning)
        if pitch is None:
            state.message = "Course shift failed"
            return False
        pitches.append(pitch)
    policy = _policy_from_settings(state)
    result = assign_chord_pitches(
        pitches,
        source_tuning[: state.piece.strings],
        policy=policy,
        forced_strings={forced_note_index: forced_target_string},
    )
    if not result.ok or len(result.notes) != len(chord.notes):
        state.message = "Course shift impossible"
        return False
    for note, assigned in zip(chord.notes, result.notes, strict=False):
        note.string = assigned.string
        note.fret = assigned.fret
    return True


def _cursor_grid_entries(
    state: EditorState,
    *,
    bar: int,
    col: int,
    style: str,
) -> list[tuple[tuple[int, int, int], int, str]]:
    entries: list[tuple[tuple[int, int, int], int, str]] = []
    for key, value in sorted(state.overrides.items()):
        b, _s_idx, c = key
        if b != bar or c != col:
            continue
        fret = _parse_override_fret(value, style)
        if fret is not None:
            entries.append((key, fret, value))
    return entries


def _cursor_grid_entry_index(
    state: EditorState,
    entries: list[tuple[tuple[int, int, int], int, str]],
) -> int | None:
    actual_string_idx = string_index(state, state.cursor_string)
    return next(
        (i for i, (key, _fret, _value) in enumerate(entries) if key[1] == actual_string_idx),
        None,
    )


def _find_cursor_grid_entries_for_shift(
    state: EditorState,
) -> tuple[list[tuple[tuple[int, int, int], int, str]], int | None]:
    if not state.piece.bars:
        state.message = "No bars"
        return [], None
    if state.cursor_bar < 0 or state.cursor_bar >= len(state.piece.bars):
        state.message = "No bars"
        return [], None
    bar = state.cursor_bar
    col = state.cursor_col
    style = state.settings.get("style", "french")
    entries = _cursor_grid_entries(state, bar=bar, col=col, style=style)
    if not entries:
        state.message = "No note at cursor"
        return [], None
    note_idx = _cursor_grid_entry_index(state, entries)
    if note_idx is None:
        state.message = "No note on cursor string"
        return entries, None
    return entries, note_idx


def _grid_column_pitches(
    entries: list[tuple[tuple[int, int, int], int, str]],
    *,
    source_tuning: list[int],
) -> list[int] | None:
    pitches: list[int] = []
    for key, fret, _value in entries:
        _bar, s_idx, _col = key
        if s_idx < 0 or s_idx >= len(source_tuning):
            return None
        pitches.append(source_tuning[s_idx] + fret)
    return pitches


def _grid_shift_has_nonfret_collision(
    state: EditorState,
    *,
    entries: list[tuple[tuple[int, int, int], int, str]],
    assigned_notes,
    style: str,
) -> bool:
    source_keys = {key for (key, _fret, _value) in entries}
    dest_keys = {(entries[i][0][0], assigned.string - 1, entries[i][0][2]) for i, assigned in enumerate(assigned_notes)}
    for dest_key in dest_keys:
        existing = state.overrides.get(dest_key)
        if existing is None or dest_key in source_keys:
            continue
        if _parse_override_fret(existing, style) is None:
            return True
    return False


def _apply_grid_shift_assignments(
    state: EditorState,
    *,
    entries: list[tuple[tuple[int, int, int], int, str]],
    assigned_notes,
    style: str,
) -> bool:
    new_overrides = dict(state.overrides)
    for key, _fret, _value in entries:
        new_overrides.pop(key, None)
    for entry, assigned in zip(entries, assigned_notes, strict=False):
        src_key, _src_fret, _src_value = entry
        out = _format_override_fret(assigned.fret, style)
        if out is None:
            return False
        bar_idx, _s_idx, col = src_key
        new_overrides[(bar_idx, assigned.string - 1, col)] = out
    state.overrides = new_overrides
    return True


def _assign_shifted_grid_column(
    state: EditorState,
    *,
    entries: list[tuple[tuple[int, int, int], int, str]],
    forced_note_index: int,
    forced_target_string: int,
) -> bool:
    source_tuning = _editor_tuning_pitches(
        state.settings.get("tuning", ""),
        strings=state.piece.strings,
    )
    if not source_tuning:
        state.message = "Invalid tuning"
        return False
    policy = _policy_from_settings(state)
    pitches = _grid_column_pitches(entries, source_tuning=source_tuning)
    if pitches is None:
        state.message = "Course shift failed"
        return False
    result = assign_chord_pitches(
        pitches,
        source_tuning[: state.piece.strings],
        policy=policy,
        forced_strings={forced_note_index: forced_target_string},
    )
    if not result.ok or len(result.notes) != len(entries):
        state.message = "Course shift impossible"
        return False
    style = state.settings.get("style", "french")
    if _grid_shift_has_nonfret_collision(
        state,
        entries=entries,
        assigned_notes=result.notes,
        style=style,
    ):
        state.message = "Course shift collision"
        return False
    if not _apply_grid_shift_assignments(
        state,
        entries=entries,
        assigned_notes=result.notes,
        style=style,
    ):
        state.message = "Course shift failed"
        return False
    return True


def cmd_courseshift(state: EditorState, value: str) -> None:
    direction = value.strip().lower() or "down"
    if direction not in {"up", "down"}:
        state.message = "Courseshift must be up/down"
        return
    before = _snapshot_score_transform(state)
    _bar, chord = _find_cursor_chord_for_shift(state)
    if chord is not None:
        actual_string_idx = string_index(state, state.cursor_string)
        note_idx = next(
            (i for i, n in enumerate(chord.notes) if (n.string - 1) == actual_string_idx),
            None,
        )
        if note_idx is None:
            state.message = "No note on cursor string"
            return
        target_string = chord.notes[note_idx].string + (1 if direction == "down" else -1)
        if not _assign_shifted_chord(
            state,
            chord,
            forced_note_index=note_idx,
            forced_target_string=target_string,
        ):
            return
    else:
        entries, note_idx = _find_cursor_grid_entries_for_shift(state)
        if note_idx is None:
            return
        src_key, _fret, _value = entries[note_idx]
        target_string = (src_key[1] + 1) + (1 if direction == "down" else -1)
        if not _assign_shifted_grid_column(
            state,
            entries=entries,
            forced_note_index=note_idx,
            forced_target_string=target_string,
        ):
            return
    state.modified = True
    _record_score_transform(state, before=before, label=f"courseshift {direction}")
    state.message = f"Course shift {direction}"
