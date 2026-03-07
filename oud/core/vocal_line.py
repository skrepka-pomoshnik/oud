from __future__ import annotations

from dataclasses import dataclass

from oud.core.model import Bar, Chord, LyricEvent

_DIATONIC_BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "h": 11}


@dataclass(frozen=True)
class VocalEvent:
    onset_index: int
    chord_index: int
    pitch: int
    note_type: int
    dotted: bool
    text: str = ""


def token_pitch_value(token: str) -> int | None:
    raw = token.strip().lower()
    if not raw:
        return None
    letter = next((ch for ch in raw if ch in _DIATONIC_BASE), None)
    if letter is None:
        return None
    pitch = 60 + _DIATONIC_BASE[letter]
    pitch += raw.count("#")
    if "b" in raw and letter != "b":
        pitch -= 1
    pitch += 12 * raw.count("'")
    pitch -= 12 * raw.count(",")
    return pitch


def chord_top_pitch(chord: Chord, tuning_pitches: list[int] | None) -> int | None:
    if not chord.notes or not tuning_pitches:
        return None
    pitches: list[int] = []
    for note in chord.notes:
        idx = note.string - 1
        if 0 <= idx < len(tuning_pitches):
            pitches.append(tuning_pitches[idx] + note.fret)
    return max(pitches) if pitches else None


def infer_vocal_events(
    bar: Bar,
    *,
    tuning_pitches: list[int] | None,
) -> list[VocalEvent]:
    if not bar.chords:
        return []
    anchor_events = _anchor_melody_events(bar)
    if anchor_events:
        out: list[VocalEvent] = []
        for onset_index, chord_index, text in anchor_events:
            if not (0 <= chord_index < len(bar.chords)):
                continue
            chord = bar.chords[chord_index]
            pitch = token_pitch_value(text)
            if pitch is None:
                pitch = chord_top_pitch(chord, tuning_pitches)
            if pitch is None:
                continue
            out.append(
                VocalEvent(
                    onset_index=onset_index,
                    chord_index=chord_index,
                    pitch=pitch,
                    note_type=chord.note_type,
                    dotted=bool(chord.dotted),
                    text=text,
                ),
            )
        if out:
            return out
    out = []
    for onset_index, chord in enumerate(bar.chords):
        pitch = chord_top_pitch(chord, tuning_pitches)
        if pitch is None:
            continue
        out.append(
            VocalEvent(
                onset_index=onset_index,
                chord_index=onset_index,
                pitch=pitch,
                note_type=chord.note_type,
                dotted=bool(chord.dotted),
            ),
        )
    return out


def lyric_anchor_onsets(bar: Bar) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for row in getattr(bar, "lyric_event_rows", None) or []:
        for ev in row:
            if not _lyric_anchor_text(ev):
                continue
            if ev.onset_index in seen:
                continue
            seen.add(ev.onset_index)
            out.append(ev.onset_index)
    out.sort()
    return out


def _anchor_melody_events(bar: Bar) -> list[tuple[int, int, str]]:
    explicit = [
        ev for ev in getattr(bar, "melody_events", None) or [] if (ev.text or "").strip()
    ]
    if explicit:
        return [(ev.onset_index, ev.onset_index, ev.text) for ev in explicit]
    # Structured FT3 lyrics are often available without an explicit melody lane.
    # Anchoring melody to lyric onsets drops chord attacks and produces sparse,
    # musically misleading note rows; use full chord fallback instead.
    return []


def _lyric_anchor_text(ev: LyricEvent) -> str:
    text = (ev.text or "").strip()
    if not text:
        return ""
    return text
