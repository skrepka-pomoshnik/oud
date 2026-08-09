from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from oud.exports.lilypond.timing import meter_duration, timed_items_duration
from petrucci.core.model import Piece

_DENSE_LYRIC_ROWS = 8
_DENSE_BARS_PER_SYSTEM = 4
_DENSE_SYSTEMS_PER_PAGE = 2
_SONG_MAX_LYRIC_ROWS = 3
_SONG_MINIMUM_BARS = 20
_SONG_BARS_PER_SYSTEM = 5
_SONG_SYSTEMS_PER_PAGE = 4
_FONT_CONTROL_TEXT = frozenset(("arial", "times new roman"))


@dataclass(frozen=True, slots=True)
class LilyPondRegistration:
    """Source-bar registration shared by every simultaneous LilyPond staff."""

    system_break_after: frozenset[int]
    page_break_after: frozenset[int]
    boxed_bar_number_before: frozenset[int]
    editorial_before: tuple[tuple[str, ...], ...]
    measure_durations: tuple[Fraction, ...]

    def command_after(self, bar_index: int) -> str | None:
        if bar_index in self.page_break_after:
            return r"\pageBreak"
        if bar_index in self.system_break_after:
            return r"\break"
        return None

    def duration_for(self, bar_index: int) -> Fraction:
        return self.measure_durations[bar_index]


def _positive_setting(settings: dict[str, str], key: str) -> int:
    value = settings.get(key, "0")
    return int(value) if value.isdigit() and int(value) > 0 else 0


def _maximum_lyric_rows(piece: Piece) -> int:
    counts = [len(bar.lyric_event_rows) for bar in piece.bars]
    if piece.imported_score is not None:
        counts.extend(
            len(bar.lyric_event_rows)
            for staff in piece.imported_score.staffs
            if staff.kind == "lyrics"
            for bar in staff.bars
        )
    return max(counts, default=0)


def _source_bar_count(piece: Piece) -> int:
    count = len(piece.bars)
    if piece.imported_score is not None:
        count = max(
            count,
            max(
                (bar.source_bar_index + 1 for staff in piece.imported_score.staffs for bar in staff.bars),
                default=0,
            ),
        )
    return count


def _source_system_breaks(piece: Piece) -> set[int]:
    breaks = {index for index, bar in enumerate(piece.bars) if bar.system_break}
    if piece.imported_score is None:
        return breaks
    bar_count = _source_bar_count(piece)
    breaks.update(
        bar.source_bar_index
        for staff in piece.imported_score.staffs
        for bar in staff.bars
        if bar.system_break and bar.source_bar_index < bar_count
    )
    return breaks


def _is_registered_song(piece: Piece, lyric_rows: int) -> bool:
    return (
        0 < lyric_rows <= _SONG_MAX_LYRIC_ROWS
        and _source_bar_count(piece) >= _SONG_MINIMUM_BARS
        and any(bar.chords for bar in piece.bars)
    )


def _system_breaks(
    piece: Piece,
    settings: dict[str, str],
    *,
    dense_lyrics: bool,
    registered_song: bool,
) -> set[int]:
    breaks = _source_system_breaks(piece)
    bars_per_system = _positive_setting(settings, "lybarsperline")
    if bars_per_system == 0 and dense_lyrics:
        bars_per_system = _DENSE_BARS_PER_SYSTEM
    if bars_per_system == 0 and registered_song:
        bars_per_system = _SONG_BARS_PER_SYSTEM
    if bars_per_system:
        breaks.update(range(bars_per_system - 1, _source_bar_count(piece) - 1, bars_per_system))
    return breaks


def _page_breaks(
    piece: Piece,
    settings: dict[str, str],
    system_breaks: set[int],
    *,
    dense_lyrics: bool,
    registered_song: bool,
) -> set[int]:
    breaks = {index - 1 for index, bar in enumerate(piece.bars) if index > 0 and bar.page_break_before}
    systems_per_page = _positive_setting(settings, "lysystemsperpage")
    if systems_per_page == 0 and dense_lyrics:
        systems_per_page = _DENSE_SYSTEMS_PER_PAGE
    if systems_per_page == 0 and registered_song:
        systems_per_page = _SONG_SYSTEMS_PER_PAGE
    if systems_per_page == 0:
        return breaks
    bar_count = _source_bar_count(piece)
    if bar_count == 0:
        return breaks
    system_ends = sorted({*system_breaks, bar_count - 1})
    breaks.update(system_ends[systems_per_page - 1 : -1 : systems_per_page])
    return breaks


def _editorial_marks(piece: Piece) -> tuple[tuple[str, ...], ...]:
    marks: list[list[str]] = [[] for _ in range(_source_bar_count(piece))]
    for index, bar in enumerate(piece.bars):
        marks[index].extend(bar.editorial_text)
    if piece.imported_score is not None:
        for staff in piece.imported_score.staffs:
            if staff.kind != "comment":
                continue
            for bar in staff.bars:
                if 0 <= bar.source_bar_index < len(marks):
                    marks[bar.source_bar_index].extend(bar.editorial_text)
    return tuple(
        tuple(
            dict.fromkeys(
                text
                for text in row
                if text.strip() and text.strip().casefold().rstrip(".") not in _FONT_CONTROL_TEXT
            ),
        )
        for row in marks
    )


def _canonical_measure_durations(piece: Piece) -> tuple[Fraction, ...]:
    imported: dict[int, Fraction] = {}
    if piece.imported_score is not None:
        for staff in piece.imported_score.staffs:
            if staff.kind != "note":
                continue
            for bar in staff.bars:
                duration = timed_items_duration(bar.melody_events)
                if duration:
                    imported.setdefault(bar.source_bar_index, duration)
    current_time = getattr(piece, "time_sig", None)
    durations: list[Fraction] = []
    for index in range(_source_bar_count(piece)):
        bar = piece.bars[index] if index < len(piece.bars) else None
        if bar is not None and bar.time_sig:
            current_time = bar.time_sig
        duration = imported.get(index, Fraction())
        if not duration and bar is not None:
            duration = timed_items_duration(bar.melody_events)
        if not duration:
            duration = meter_duration(current_time)
        if not duration and bar is not None:
            duration = timed_items_duration(bar.chords)
        durations.append(duration or Fraction(1, 4))
    return tuple(durations)


def build_lilypond_registration(piece: Piece, settings: dict[str, str]) -> LilyPondRegistration:
    lyric_rows = _maximum_lyric_rows(piece)
    dense_lyrics = lyric_rows >= _DENSE_LYRIC_ROWS
    registered_song = _is_registered_song(piece, lyric_rows)
    system_breaks = _system_breaks(
        piece,
        settings,
        dense_lyrics=dense_lyrics,
        registered_song=registered_song,
    )
    page_breaks = _page_breaks(
        piece,
        settings,
        system_breaks,
        dense_lyrics=dense_lyrics,
        registered_song=registered_song,
    )
    boxed_numbers = {*system_breaks, _source_bar_count(piece) - 1} if registered_song else set()
    return LilyPondRegistration(
        system_break_after=frozenset(system_breaks),
        page_break_after=frozenset(page_breaks),
        boxed_bar_number_before=frozenset(boxed_numbers),
        editorial_before=_editorial_marks(piece),
        measure_durations=_canonical_measure_durations(piece),
    )
