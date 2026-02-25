from __future__ import annotations

import copy
from dataclasses import dataclass

from oud.core.render_utils import chord_positions
from oud.core.tab_assign_policy import AssignmentPolicy, assign_chord_pitches
from oud.core.tuning_utils import parse_tuning_pitches, tuning_preset
from oud.editor.controller_utils import string_index
from oud.editor.edit_ops import record_action
from oud.editor.ops import french_to_fret, fret_to_french, fret_to_italian, italian_to_fret
from oud.editor.state import EditorState, UndoAction


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
    pitches: list[int] = []
    for note in chord.notes:
        pitch = _note_pitch(note, source_tuning)
        if pitch is None:
            report.skipped += 1
            return report
        pitches.append(pitch + semitones)
    result = assign_chord_pitches(pitches, target_tuning, policy=policy)
    if not result.ok or len(result.notes) != len(chord.notes):
        report.skipped += len(chord.notes)
        if report.first_diagnostic is None and result.diagnostics:
            report.first_diagnostic = result.diagnostics[0].code
        return report
    for note, assigned in zip(chord.notes, result.notes, strict=False):
        if note.string != assigned.string or note.fret != assigned.fret:
            report.changed += 1
        note.string = assigned.string
        note.fret = assigned.fret
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


def _reassign_overrides(  # noqa: C901
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
        bar_idx, s_idx, col = key
        fret = _parse_override_fret(value, style)
        if fret is None:
            new_overrides[key] = value
            continue
        if s_idx < 0 or s_idx >= len(source_tuning):
            report.skipped += 1
            if report.first_diagnostic is None:
                report.first_diagnostic = "source_string_out_of_range"
            new_overrides[key] = value
            continue
        pitch = source_tuning[s_idx] + fret + semitones
        result = assign_chord_pitches([pitch], target_tuning, policy=policy)
        if not result.ok or not result.notes:
            report.skipped += 1
            if report.first_diagnostic is None and result.diagnostics:
                report.first_diagnostic = result.diagnostics[0].code
            new_overrides[key] = value
            continue
        assigned = result.notes[0]
        out = _format_override_fret(assigned.fret, style)
        if out is None:
            report.skipped += 1
            if report.first_diagnostic is None:
                report.first_diagnostic = "override_format_failed"
            new_overrides[key] = value
            continue
        new_key = (bar_idx, assigned.string - 1, col)
        if new_key in new_overrides and new_key != key:
            report.skipped += 1
            if report.first_diagnostic is None:
                report.first_diagnostic = "override_collision"
            new_overrides[key] = value
            continue
        if new_key != key or out != value:
            report.changed += 1
        new_overrides[new_key] = out
    state.overrides = new_overrides
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
    source_tuning = _editor_tuning_pitches(
        state.settings.get("tuning", ""),
        strings=state.piece.strings,
    )
    target_tuning = _editor_tuning_pitches(target_tuning_text)
    if not source_tuning or not target_tuning:
        state.message = "Invalid tuning for transform"
        return TransformReport()
    if target_strings is None:
        target_strings = len(target_tuning) if target_tuning else state.piece.strings
    target_tuning = target_tuning[:target_strings]
    if not target_tuning:
        state.message = "Invalid target tuning"
        return TransformReport()

    before = _snapshot_score_transform(state)
    policy = _policy_from_settings(state)
    report = TransformReport()
    for bar in state.piece.bars:
        r1 = _reassign_bar_notes(
            bar,
            source_tuning=source_tuning,
            target_tuning=target_tuning,
            semitones=semitones,
            policy=policy,
        )
        r2 = TransformReport()
        for chord in bar.chords:
            rc = _reassign_chord_notes(
                chord,
                source_tuning=source_tuning,
                target_tuning=target_tuning,
                semitones=semitones,
                policy=policy,
            )
            r2.changed += rc.changed
            r2.skipped += rc.skipped
        report.changed += r1.changed + r2.changed
        report.skipped += r1.skipped + r2.skipped
        if report.first_diagnostic is None:
            report.first_diagnostic = r1.first_diagnostic or r2.first_diagnostic
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
    report = transform_score_to_tuning(
        state,
        target_tuning_text=tuning_text,
        target_strings=state.piece.strings,
        semitones=semitones,
        label=f"transpose {semitones}",
        update_settings_tuning=False,
    )
    if report.total == 0:
        return
    diag = f" ({report.first_diagnostic})" if report.skipped and report.first_diagnostic else ""
    state.message = (
        f"Transposed {semitones:+d}: changed {report.changed}, skipped {report.skipped}{diag}"
    )


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
    report = transform_score_to_tuning(
        state,
        target_tuning_text=target_tuning,
        target_strings=len(target_pitches),
        semitones=0,
        label=f"retune {raw}",
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


def cmd_courseshift(state: EditorState, value: str) -> None:
    direction = value.strip().lower() or "down"
    if direction not in {"up", "down"}:
        state.message = "Courseshift must be up/down"
        return
    _bar, chord = _find_cursor_chord_for_shift(state)
    if chord is None:
        return
    actual_string_idx = string_index(state, state.cursor_string)
    note_idx = next(
        (i for i, n in enumerate(chord.notes) if (n.string - 1) == actual_string_idx),
        None,
    )
    if note_idx is None:
        state.message = "No note on cursor string"
        return
    before = _snapshot_score_transform(state)
    target_string = chord.notes[note_idx].string + (1 if direction == "down" else -1)
    if not _assign_shifted_chord(
        state,
        chord,
        forced_note_index=note_idx,
        forced_target_string=target_string,
    ):
        return
    state.modified = True
    _record_score_transform(state, before=before, label=f"courseshift {direction}")
    state.message = f"Course shift {direction}"
