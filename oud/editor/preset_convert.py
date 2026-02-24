from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from oud.core.tab_assign_policy import assign_chord_pitches
from oud.core.tuning_utils import parse_tuning_pitches
from oud.editor.ops import (
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    italian_to_fret,
)

if TYPE_CHECKING:
    from oud.editor.state import EditorState


def apply_meta_preset_content_conversion(
    state: EditorState,
    name: str,
    *,
    target_preset: Mapping[str, str] | None = None,
) -> str | None:
    # Temporary bridge until the full transpose/course-shift module is implemented.
    # Current behavior intentionally handles only the historical guitar/lute preset
    # mismatch on course 3, and returns a warning string for UI status.
    if name not in {"guitar", "lute"}:
        return None
    if getattr(state, "partial_preset_convert_applied", None) == name:
        return None
    if not _score_has_content(state):
        return None
    delta = -1 if name == "guitar" else 1
    source_tuning_pitches = parse_tuning_pitches(state.settings.get("tuning", ""))
    target_tuning_text = ""
    target_strings = state.piece.strings
    if target_preset is not None:
        target_tuning_text = str(target_preset.get("tuning", "") or "")
        try:
            target_strings = int(str(target_preset.get("strings", state.piece.strings)))
        except ValueError:
            target_strings = state.piece.strings
    target_tuning_pitches = parse_tuning_pitches(target_tuning_text) or list(source_tuning_pitches)
    changed, skipped = _shift_partial_bridge_course_notes_semis(
        state,
        name,
        delta,
        source_tuning_pitches=source_tuning_pitches,
        target_tuning_pitches=target_tuning_pitches,
    )
    rescued_changed, rescued_skipped = _rescue_notes_outside_target_strings_octave_up(
        state,
        source_tuning_pitches=source_tuning_pitches,
        target_tuning_pitches=target_tuning_pitches,
        target_strings=target_strings,
    )
    changed += rescued_changed
    skipped += rescued_skipped
    state.partial_preset_convert_applied = name
    sign = f"{delta:+d}"
    return (
        "warning: partial convert (bridge course only "
        f"{sign} semitone, changed {changed}, skipped {skipped})"
    )


def _score_has_content(state: EditorState) -> bool:
    if state.overrides:
        return True
    return any(bar.notes or bar.chords for bar in state.piece.bars)


def _parse_override_fret(ch: str, style: str) -> int | None:
    if style == "italian":
        return italian_to_fret(ch)
    return french_to_fret(ch)


def _format_override_fret(fret: int, style: str) -> str | None:
    if style == "italian":
        return fret_to_italian(fret)
    return fret_to_french(fret)


def _bridge_course_for_partial_preset(name: str) -> int:
    # 1-based internal course number (high to low).
    # Lute and guitar place the major-third interval on different adjacent courses.
    # This temporary bridge adjusts one representative course only:
    # - lute -> guitar: course 4
    # - guitar -> lute: course 3
    return 4 if name == "guitar" else 3


def _shift_partial_bridge_course_notes_semis(  # noqa: C901, PLR0912
    state: EditorState,
    preset_name: str,
    delta: int,
    *,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
) -> tuple[int, int]:
    changed = 0
    skipped = 0
    target_string = _bridge_course_for_partial_preset(preset_name)
    for bar in state.piece.bars:
        kept_notes = []
        for note in bar.notes:
            if note.string != target_string:
                kept_notes.append(note)
                continue
            new_fret = note.fret + delta
            if new_fret >= 0:
                note.fret = new_fret
                kept_notes.append(note)
                changed += 1
                continue
            moved = _retarget_negative_shift_note(
                note,
                delta=delta,
                source_tuning_pitches=source_tuning_pitches,
                target_tuning_pitches=target_tuning_pitches,
                occupied_strings={
                    n.string
                    for n in bar.notes
                    if n is not note and n.raw_pos == note.raw_pos
                },
            )
            if moved is None:
                # Drop the note if no equivalent next-string placement is available.
                changed += 1
                continue
            kept_notes.append(moved)
            changed += 1
        bar.notes = kept_notes
        for chord in bar.chords:
            kept_chord_notes = []
            for note in chord.notes:
                if note.string != target_string:
                    kept_chord_notes.append(note)
                    continue
                new_fret = note.fret + delta
                if new_fret >= 0:
                    note.fret = new_fret
                    kept_chord_notes.append(note)
                    changed += 1
                    continue
                moved = _retarget_negative_shift_note(
                    note,
                    delta=delta,
                    source_tuning_pitches=source_tuning_pitches,
                    target_tuning_pitches=target_tuning_pitches,
                    occupied_strings={n.string for n in chord.notes if n is not note},
                )
                if moved is None:
                    changed += 1
                    continue
                kept_chord_notes.append(moved)
                changed += 1
            chord.notes = kept_chord_notes
    style = state.settings.get("style", "french")
    for key, ch in list(state.overrides.items()):
        _bar, s_idx, _col = key
        if s_idx != (target_string - 1):
            continue
        fret = _parse_override_fret(ch, style)
        if fret is None:
            continue
        new_fret = fret + delta
        if new_fret >= 0:
            out = _format_override_fret(new_fret, style)
            if out is None:
                skipped += 1
                continue
            state.overrides[key] = out
            changed += 1
            continue
        moved_key, moved_fret = _retarget_negative_shift_override(
            key,
            delta=delta,
            fret=fret,
            source_tuning_pitches=source_tuning_pitches,
            target_tuning_pitches=target_tuning_pitches,
            occupied_keys=set(state.overrides.keys()),
        )
        if moved_key is None or moved_fret is None:
            del state.overrides[key]
            changed += 1
            continue
        out = _format_override_fret(moved_fret, style)
        if out is None:
            skipped += 1
            continue
        del state.overrides[key]
        state.overrides[moved_key] = out
        changed += 1
    if changed:
        state.modified = True
    return changed, skipped


def _retarget_negative_shift_note(
    note,
    *,
    delta: int,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
    occupied_strings: set[int],
):
    string_idx = note.string - 1
    next_idx = string_idx + 1
    if next_idx >= len(target_tuning_pitches):
        return None
    if (next_idx + 1) in occupied_strings:
        return None
    if string_idx >= len(source_tuning_pitches):
        return None
    target_pitch = source_tuning_pitches[string_idx] + note.fret + delta
    result = assign_chord_pitches(
        [target_pitch],
        target_tuning_pitches,
        forced_strings={0: next_idx + 1},
    )
    if (not result.ok) or not result.notes:
        return None
    assigned = result.notes[0]
    if assigned.fret < 0:
        return None
    note.string = assigned.string
    note.fret = assigned.fret
    return note


def _retarget_negative_shift_override(
    key: tuple[int, int, int],
    *,
    delta: int,
    fret: int,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
    occupied_keys: set[tuple[int, int, int]],
) -> tuple[tuple[int, int, int] | None, int | None]:
    bar_idx, s_idx, col = key
    next_idx = s_idx + 1
    if next_idx >= len(target_tuning_pitches):
        return None, None
    target_key = (bar_idx, next_idx, col)
    if target_key in occupied_keys and target_key != key:
        return None, None
    if s_idx >= len(source_tuning_pitches):
        return None, None
    target_pitch = source_tuning_pitches[s_idx] + fret + delta
    result = assign_chord_pitches(
        [target_pitch],
        target_tuning_pitches,
        forced_strings={0: next_idx + 1},
    )
    if (not result.ok) or not result.notes:
        return None, None
    assigned = result.notes[0]
    if assigned.fret < 0:
        return None, None
    return target_key, assigned.fret


def _rescue_notes_outside_target_strings_octave_up(  # noqa: C901, PLR0912
    state: EditorState,
    *,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
    target_strings: int,
) -> tuple[int, int]:
    changed = 0
    skipped = 0
    if target_strings <= 0:
        return 0, 0
    target_tuning = target_tuning_pitches[:target_strings]
    if not target_tuning:
        return 0, 0
    for bar in state.piece.bars:
        kept_notes = []
        for note in bar.notes:
            if note.string <= target_strings:
                kept_notes.append(note)
                continue
            moved = _retarget_note_octave_up(
                note,
                source_tuning_pitches=source_tuning_pitches,
                target_tuning_pitches=target_tuning,
                occupied_strings={n.string for n in kept_notes if n.raw_pos == note.raw_pos},
            )
            if moved is None:
                changed += 1
                continue
            kept_notes.append(moved)
            changed += 1
        bar.notes = kept_notes
        for chord in bar.chords:
            kept_chord_notes = []
            for note in chord.notes:
                if note.string <= target_strings:
                    kept_chord_notes.append(note)
                    continue
                moved = _retarget_note_octave_up(
                    note,
                    source_tuning_pitches=source_tuning_pitches,
                    target_tuning_pitches=target_tuning,
                    occupied_strings={n.string for n in kept_chord_notes},
                )
                if moved is None:
                    changed += 1
                    continue
                kept_chord_notes.append(moved)
                changed += 1
            chord.notes = kept_chord_notes
    style = state.settings.get("style", "french")
    occupied_keys = set(state.overrides.keys())
    for key, ch in list(state.overrides.items()):
        bar_idx, s_idx, col = key
        if (s_idx + 1) <= target_strings:
            continue
        fret = _parse_override_fret(ch, style)
        if fret is None:
            skipped += 1
            continue
        moved_key, moved_fret = _retarget_override_octave_up(
            key=(bar_idx, s_idx, col),
            fret=fret,
            source_tuning_pitches=source_tuning_pitches,
            target_tuning_pitches=target_tuning,
            occupied_keys=occupied_keys,
        )
        del state.overrides[key]
        occupied_keys.discard(key)
        if moved_key is None or moved_fret is None:
            changed += 1
            continue
        out = _format_override_fret(moved_fret, style)
        if out is None:
            skipped += 1
            continue
        state.overrides[moved_key] = out
        occupied_keys.add(moved_key)
        changed += 1
    if changed:
        state.modified = True
    return changed, skipped


def _retarget_note_octave_up(
    note,
    *,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
    occupied_strings: set[int],
):
    string_idx = note.string - 1
    if string_idx >= len(source_tuning_pitches):
        return None
    pitch = source_tuning_pitches[string_idx] + note.fret + 12
    result = assign_chord_pitches([pitch], target_tuning_pitches)
    if (not result.ok) or not result.notes:
        return None
    assigned = result.notes[0]
    if assigned.string in occupied_strings or assigned.fret < 0:
        return None
    note.string = assigned.string
    note.fret = assigned.fret
    return note


def _retarget_override_octave_up(
    *,
    key: tuple[int, int, int],
    fret: int,
    source_tuning_pitches: list[int],
    target_tuning_pitches: list[int],
    occupied_keys: set[tuple[int, int, int]],
) -> tuple[tuple[int, int, int] | None, int | None]:
    bar_idx, s_idx, col = key
    if s_idx >= len(source_tuning_pitches):
        return None, None
    pitch = source_tuning_pitches[s_idx] + fret + 12
    result = assign_chord_pitches([pitch], target_tuning_pitches)
    if (not result.ok) or not result.notes:
        return None, None
    assigned = result.notes[0]
    target_key = (bar_idx, assigned.string - 1, col)
    if target_key in occupied_keys and target_key != key:
        return None, None
    if assigned.fret < 0:
        return None, None
    return target_key, assigned.fret
