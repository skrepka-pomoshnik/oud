from __future__ import annotations

from petrucci.model import Bar, Chord, Note
from petrucci.render_utils import chord_slot_positions


def duration_value(key: int, style: str) -> int | None:
    ctrl_map = {
        1: 1,
        2: 2,
        3: 4,
        4: 8,
        5: 16,
        6: 32,
        7: 64,
    }
    french_map = {
        ord("1"): 1,
        ord("2"): 2,
        ord("3"): 4,
        ord("4"): 8,
        ord("5"): 16,
        ord("6"): 32,
        ord("7"): 64,
    }
    if style == "italian":
        return ctrl_map.get(key)
    return french_map.get(key)


def denom_to_note_type(denom: int) -> int | None:
    mapping = {
        1: 2,
        2: 3,
        4: 4,
        8: 5,
        16: 6,
        32: 7,
        64: 8,
        128: 9,
        256: 10,
    }
    return mapping.get(denom)


def is_french_fret(ch: str) -> bool:
    return ch in "abcdefghiklmnopqrst"


def is_italian_fret(ch: str) -> bool:
    return ch.isdigit() or ch == "x"


def french_to_fret(ch: str) -> int | None:
    letters = "abcdefghiklmnopqrst"
    if ch in letters:
        return letters.index(ch)
    return None


def fret_to_french(fret: int) -> str | None:
    letters = "abcdefghiklmnopqrst"
    if 0 <= fret < len(letters):
        return letters[fret]
    return None


def italian_to_fret(ch: str) -> int | None:
    if ch.isdigit():
        return int(ch)
    if ch == "x":
        return 10
    return None


def fret_to_italian(fret: int) -> str | None:
    if 0 <= fret <= 9:
        return str(fret)
    if fret == 10:
        return "x"
    return None


def chord_index_at_col(
    bar: Bar,
    bar_width: int,
    col: int,
    *,
    exact: bool = False,
) -> int | None:
    if not bar.chords:
        return None
    default_duration = 4
    positions = chord_slot_positions(bar, bar_width, default_duration)
    for idx, (pos, _denom, _dot) in enumerate(positions):
        if pos == col:
            return idx
    if positions:
        if exact:
            return None
        nearest = min(
            enumerate(positions),
            key=lambda item: abs(item[1][0] - col),
        )
        return nearest[0]
    # Fallback for bars that currently contain only empty chords.
    if len(bar.chords) == 1:
        return 0
    step = max(1, bar_width // len(bar.chords))
    return min(len(bar.chords) - 1, max(0, col) // step)


def set_chord_note(
    bar: Bar,
    bar_width: int,
    col: int,
    string: int,
    fret: int | None,
) -> bool:
    idx = chord_index_at_col(bar, bar_width, col, exact=fret is None)
    if idx is None:
        return False
    chord = bar.chords[idx]
    for note in chord.notes:
        if note.string == string:
            if fret is None:
                chord.notes = [n for n in chord.notes if n.string != string]
                if not chord.notes:
                    bar.chords.pop(idx)
            else:
                note.fret = fret
            return True
    if fret is not None:
        chord.notes.append(Note(string=string, fret=fret, raw_pos=0))
        return True
    return False


def insert_chord(bar: Bar, bar_width: int, col: int) -> None:
    note_type = bar.chords[-1].note_type if bar.chords else 4
    dotted = bar.chords[-1].dotted if bar.chords else False
    idx = chord_index_at_col(bar, bar_width, col)
    chord = Chord(note_type=note_type, dotted=dotted, grid=None)
    if idx is None:
        bar.chords.append(chord)
        return
    bar.chords.insert(idx, chord)


def delete_chord(bar: Bar, bar_width: int, col: int) -> bool:
    if col < 0 or col >= bar_width:
        return False
    idx = chord_index_at_col(bar, bar_width, col, exact=True)
    if idx is None:
        return False
    bar.chords.pop(idx)
    return True
