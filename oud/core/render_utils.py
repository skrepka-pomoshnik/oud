from __future__ import annotations

from oud.core.model import Bar


def format_fret(  # noqa: PLR0911
    style: str,
    fret: int,
    french_c: str = "normal",
    french_e: str = "normal",
) -> str:
    if style == "italian":
        if 0 <= fret <= 9:
            return str(fret)
        if fret == 10:
            return "x"
        return str(fret)
    letters = [
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
    ]
    if 0 <= fret < len(letters):
        letter = letters[fret]
        if french_c == "alt" and letter == "c":
            return "r"
        if french_e == "tail" and letter == "e":
            return "E"
        return letter
    return "?"


def bar_cells(
    bar: Bar,
    strings: int,
    bar_width: int,
    style: str,
    french_c: str = "normal",
    french_e: str = "normal",
) -> list[list[str]]:
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    next_col = [0 for _ in range(strings)]

    for note in bar.notes:
        s_idx = note.string - 1
        if s_idx < 0 or s_idx >= strings:
            continue
        col = next_col[s_idx]
        if col >= bar_width:
            continue
        text = format_fret(style, note.fret, french_c=french_c, french_e=french_e)
        if len(text) > 2:
            text = text[-2:]
        for offset, ch in enumerate(text):
            if col + offset >= bar_width:
                break
            cells[s_idx][col + offset] = ch
        next_col[s_idx] = min(bar_width, col + max(1, len(text)) + 1)

    return cells


def note_type_to_denom(note_type: int) -> int | None:
    mapping = {
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        6: 16,
        7: 32,
        8: 64,
        9: 128,
        10: 256,
    }
    return mapping.get(note_type)


def chord_positions(
    bar: Bar, bar_width: int, default_duration: int,
) -> list[tuple[int, int, bool]]:
    chords = bar.chords or []
    denoms: list[int] = []
    dotted: list[bool] = []
    for chord in chords:
        denom = note_type_to_denom(chord.note_type) or default_duration
        denoms.append(denom)
        dotted.append(bool(chord.dotted))
    if not denoms:
        return []
    max_denom = max(denoms)
    base = max_denom * 2
    units: list[int] = []
    for denom, dot in zip(denoms, dotted, strict=False):
        u = max(1, base // denom)
        if dot:
            u = max(1, (u * 3) // 2)
        units.append(u)
    total = sum(units)
    if total <= 0:
        return []
    positions: list[tuple[int, int, bool]] = []
    cum = 0
    for denom, dot, u in zip(denoms, dotted, units, strict=False):
        pos = min(bar_width - 1, (cum * (bar_width - 1)) // total)
        positions.append((pos, denom, dot))
        cum += u
    return positions


def bar_cells_from_chords(
    bar: Bar,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    french_c: str = "normal",
    french_e: str = "normal",
) -> list[list[str]]:
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    positions = chord_positions(bar, bar_width, default_duration)
    if not positions:
        return cells
    for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if 0 <= s_idx < strings and 0 <= col < bar_width:
                cells[s_idx][col] = format_fret(
                    style,
                    note.fret,
                    french_c=french_c,
                    french_e=french_e,
                )
    return cells


def duration_display(duration: int, dotted: bool = False) -> str:
    if duration == 16:
        text = "6"
    elif duration == 32:
        text = "3"
    else:
        text = str(duration)
    return f"{text}." if dotted else text


def duration_flag(duration: int) -> str:
    mapping = {
        1: "W",
        2: "w",
        4: "0",
        8: "1",
        16: "2",
        32: "3",
        64: "4",
        128: "5",
    }
    return mapping.get(duration, "?")


def flag_count(denom: int) -> int:
    if denom <= 4:
        return 0
    count = 0
    value = denom // 4
    while value > 1:
        count += 1
        value //= 2
    return count


def flag_row_style(  # noqa: C901
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    stem: str,
    flag: str,
    dot: str = ".",
    stem_width: int = 1,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    dot_positions: list[int] = []
    for col, denom, dotted in positions:
        row[col] = stem
        for extra in range(1, max(1, stem_width)):
            pos = col + extra
            if pos < bar_width and row[pos] == " ":
                row[pos] = stem
        slash_count = flag_count(denom)
        for i in range(slash_count):
            pos = col + max(1, stem_width) + i
            if pos < bar_width:
                row[pos] = flag
        if dotted:
            pos = col + max(1, stem_width) + slash_count
            if pos < bar_width:
                dot_positions.append(pos)
    for pos in dot_positions:
        idx = pos
        while idx < bar_width and row[idx] != " ":
            idx += 1
        if idx < bar_width:
            row[idx] = dot
    return row


def flag_row(positions: list[tuple[int, int, bool]], bar_width: int) -> list[str]:
    return flag_row_style(positions, bar_width, stem="|", flag="\\")


def stem_row_style(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    stem: str,
    stem_width: int = 1,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col, _denom, _dotted in positions:
        row[col] = stem
        for extra in range(1, max(1, stem_width)):
            pos = col + extra
            if pos < bar_width and row[pos] == " ":
                row[pos] = stem
    return row


def flag_positions_from_durations(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    positions: list[tuple[int, int, bool]] = []
    last: int | None = None
    for col in range(bar_width):
        found = None
        explicit = False
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                explicit = True
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last or explicit:
            is_dotted = dotted is not None and (bar_index, col) in dotted
            positions.append((col, found, is_dotted))
            last = found
    return positions
