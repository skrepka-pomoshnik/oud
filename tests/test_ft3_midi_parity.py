from __future__ import annotations

from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from oud.exports.midi import export_midi
from oud.importers.ft3 import build_durations, load_ft3


def _variable_length(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, position


def _event_status(track: bytes, position: int, running: int | None) -> tuple[int, int, int | None]:
    status = track[position]
    if status < 0x80:
        if running is None:
            message = "MIDI running status has no preceding channel event"
            raise ValueError(message)
        return running, position, running
    position += 1
    return status, position, status if status < 0xF0 else running


def _track_note_ons(track: bytes, ppq: int) -> Counter[tuple[Fraction, int]]:
    result: Counter[tuple[Fraction, int]] = Counter()
    position = 0
    tick = 0
    running: int | None = None
    while position < len(track):
        delta, position = _variable_length(track, position)
        tick += delta
        status, position, running = _event_status(track, position, running)
        if status == 0xFF:
            position += 1
            length, position = _variable_length(track, position)
            position += length
        elif status in (0xF0, 0xF7):
            length, position = _variable_length(track, position)
            position += length
        else:
            kind = status & 0xF0
            pitch = track[position]
            position += 1
            if kind not in (0xC0, 0xD0):
                velocity = track[position]
                position += 1
                if kind == 0x90 and velocity:
                    result[(Fraction(tick, ppq), pitch)] += 1
    return result


def _midi_note_ons(path: Path) -> Counter[tuple[Fraction, int]]:
    data = path.read_bytes()
    assert data[:4] == b"MThd"
    header_length = int.from_bytes(data[4:8], "big")
    ppq = int.from_bytes(data[12:14], "big")
    position = 8 + header_length
    result: Counter[tuple[Fraction, int]] = Counter()
    while position < len(data):
        assert data[position : position + 4] == b"MTrk"
        size = int.from_bytes(data[position + 4 : position + 8], "big")
        track_start = position + 8
        result.update(_track_note_ons(data[track_start : track_start + size], ppq))
        position = track_start + size
    return result


@pytest.mark.parametrize(
    ("stem", "reference_count", "generated_count", "minimum_exact_overlap"),
    [
        ("chromatica_pavana", 1278, 1278, 1277),
        ("01_felice_fu_quel_anon", 133, 133, 120),
        ("menuett", 234, 226, 193),
        ("can_she_excuse", 524, 532, 444),
        ("phrygian_fantasy", 380, 380, 380),
    ],
)
def test_ft3_export_tracks_companion_midi_evidence(
    tmp_path: Path,
    stem: str,
    reference_count: int,
    generated_count: int,
    minimum_exact_overlap: int,
) -> None:
    ft3_path = Path("lutemusic") / f"{stem}.ft3"
    reference = _midi_note_ons(Path("lutemusic") / f"{stem}.mid")
    piece = load_ft3(str(ft3_path))
    generated_path = tmp_path / f"{stem}.mid"
    export_midi(str(generated_path), piece, {}, build_durations(piece), 32)
    generated = _midi_note_ons(generated_path)

    assert sum(reference.values()) == reference_count
    assert sum(generated.values()) == generated_count
    assert sum((reference & generated).values()) >= minimum_exact_overlap


def test_empty_folle_companion_midi_is_not_accepted_as_parity_evidence(tmp_path: Path) -> None:
    reference = _midi_note_ons(Path("lutemusic/Folle_cor.mid"))
    piece = load_ft3("lutemusic/Folle_cor.ft3")
    generated_path = tmp_path / "Folle_cor.mid"
    export_midi(str(generated_path), piece, {}, build_durations(piece), 32)

    assert not reference
    assert sum(_midi_note_ons(generated_path).values()) == 1030
