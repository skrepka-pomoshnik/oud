from __future__ import annotations

from petrucci.model import Bar
from petrucci.time_utils import parse_time_signature_value

TICKS_PER_QUARTER = 480
BASE_NOTE_VELOCITY = 80
DEFAULT_VOCAL_PATCH = 53


def note_on(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x90 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def note_off(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x80 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def program_change(channel: int, program: int) -> bytes:
    return bytes([0xC0 | (channel & 0x0F), program & 0x7F])


def meta_tempo(bpm: int) -> bytes:
    mpqn = int(60_000_000 / max(1, bpm))
    return bytes([0xFF, 0x51, 0x03, (mpqn >> 16) & 0xFF, (mpqn >> 8) & 0xFF, mpqn & 0xFF])


def meter_for_bar(bar: Bar, settings: dict[str, str]) -> tuple[int, int]:
    if bar.time_sig and (parsed := parse_time_signature_value(bar.time_sig)) is not None:
        return parsed
    if parsed := parse_time_signature_value(settings.get("time", "")):
        return parsed
    return 4, 4


def accent_velocity(start: int, beats: int, unit: int, base: int = BASE_NOTE_VELOCITY) -> int:
    beat_ticks = max(1, TICKS_PER_QUARTER * 4 // max(1, unit))
    if start % beat_ticks:
        return base
    beat_index = (start // beat_ticks) % max(1, beats)
    accents = {4: (18, 0, 8, 0), 3: (16, 0, 0)}
    pattern = accents.get(beats)
    boost = pattern[beat_index] if pattern is not None else (14 if beat_index == 0 else 0)
    return min(127, base + boost)


def end_of_track() -> bytes:
    return bytes([0xFF, 0x2F, 0x00])


def vlq(value: int) -> bytes:
    value = max(0, value)
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    out.reverse()
    return bytes(out)


def write_track(events: list[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda item: item[0])
    data = bytearray()
    last_time = 0
    for time, payload in events:
        data.extend(vlq(time - last_time))
        data.extend(payload)
        last_time = time
    data.extend(vlq(0))
    data.extend(end_of_track())
    return b"MTrk" + len(data).to_bytes(4, "big") + data
