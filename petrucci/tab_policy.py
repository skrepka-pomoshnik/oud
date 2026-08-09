from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from petrucci.model import Bar


TAB_NOTATION_PRESETS: dict[str, dict[str, str]] = {
    # LilyPond-like default tab: compact cues, minimal rhythm extras.
    "minimal": {
        "showdur": "off",
        "showspans": "off",
        "showtuplets": "off",
        "showfingerings": "off",
        "showornaments": "off",
        "showextras": "off",
        "showft3extras": "off",
        "ft3fingering": "both",
        "ft3ornaments": "both",
        "showtactus": "off",
        "flagredundant": "on",
        "timesigstyle": "symbol",
        "tiecuestyle": "bracket",
        "tienoteheads": "show",
        "slurcuestyle": "paren",
        "holdcuestyle": "angle",
        "glisscuestyle": "hide",
    },
    # Approximation of \\tabFullNotation in our ASCII/TUI model.
    "full": {
        "showdur": "on",
        "showspans": "on",
        "showtuplets": "on",
        "showfingerings": "on",
        "showornaments": "on",
        "showextras": "on",
        "showft3extras": "on",
        "ft3fingering": "both",
        "ft3ornaments": "both",
        "showtactus": "on",
        "flagredundant": "off",
        "timesigstyle": "fraction",
        "tiecuestyle": "paren",
        "tienoteheads": "show",
        "slurcuestyle": "paren",
        "holdcuestyle": "angle",
        "glisscuestyle": "slash",
    },
}


def apply_tabnotation_preset(settings: dict[str, str], mode: str) -> bool:
    preset = TAB_NOTATION_PRESETS.get(mode)
    if preset is None:
        return False
    settings.update(preset)
    settings["tabnotation"] = mode
    return True


def fret_label(
    style: str,
    fret: int,
    *,
    french_c_shape: str = "normal",
    label_mode: str = "auto",
) -> str:
    mode = (label_mode or "auto").strip().lower()
    if mode == "numeric":
        return str(fret)
    if style == "italian" and mode != "letters":
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
    if not 0 <= fret < len(letters):
        return "?"
    letter = letters[fret]
    if french_c_shape in ("historical", "alt") and letter == "c":
        return "r"
    return letter


def bar_has_multifret_tokens(
    bar: Bar,
    *,
    style: str,
    french_c_shape: str = "normal",
    label_mode: str = "auto",
) -> bool:
    for note in bar.notes:
        if (
            len(
                fret_label(
                    style,
                    note.fret,
                    french_c_shape=french_c_shape,
                    label_mode=label_mode,
                ),
            )
            > 1
        ):
            return True
    for chord in bar.chords:
        for note in chord.notes:
            if (
                len(
                    fret_label(
                        style,
                        note.fret,
                        french_c_shape=french_c_shape,
                        label_mode=label_mode,
                    ),
                )
                > 1
            ):
                return True
    return False


def multifret_event_gap(
    *,
    style: str,
    policy: str,
    has_multifret: bool,
) -> int:
    if not has_multifret:
        return 2
    if style != "italian":
        return 2
    mode = (policy or "collision-safe").strip().lower()
    if mode == "tight":
        return 2
    if mode == "separated":
        return 3
    return 4


def rows_reversed(*, style: str, italian_orient: str, viewinvert: str) -> bool:
    return viewinvert == "on" or (style == "italian" and italian_orient == "reverse")


def visual_row_indices(indices: list[int], *, reverse: bool) -> list[int]:
    return list(reversed(indices)) if reverse else list(indices)


def system_display_indices_for_bars(
    bars: list[Bar],
    *,
    total_strings: int,
    edited_strings: set[int] | None = None,
) -> list[int]:
    base_strings = min(6, total_strings)
    indices = list(range(base_strings))
    used_bass = {idx for idx in edited_strings or set() if base_strings <= idx < total_strings}
    for bar in bars:
        for note in bar.notes:
            idx = note.string - 1
            if base_strings <= idx < total_strings:
                used_bass.add(idx)
        for chord in bar.chords:
            for note in chord.notes:
                idx = note.string - 1
                if base_strings <= idx < total_strings:
                    used_bass.add(idx)
    indices.extend(sorted(used_bass))
    return indices


def bass_fallback_label(actual: int, basslabels: str) -> str:
    if basslabels == "slash":
        return "/" * max(1, actual - 5)
    return str(actual + 1)


def string_label(
    *,
    actual: int,
    total_strings: int,
    tuning_labels: list[str],
    basslabels: str,
    width: int = 2,
) -> str:
    if actual >= 6 and basslabels != "tuning":
        label_value = bass_fallback_label(actual, basslabels)
    elif actual < len(tuning_labels):
        fallback = bass_fallback_label(actual, basslabels) if actual >= 6 else str(total_strings - actual)
        label_value = tuning_labels[actual] or fallback
    else:
        label_value = bass_fallback_label(actual, basslabels) if actual >= 6 else str(total_strings - actual)
    if len(label_value) > width:
        label_value = label_value[:width]
    return f"{label_value:>{width}}"


def time_sig_inline_rows(
    raw_time_value: str,
    sig_label: str,
    *,
    style_mode: str = "symbol",
) -> list[str]:
    raw = (raw_time_value or "").strip()
    mode = style_mode or "symbol"
    raw_rows = _raw_time_sig_rows(raw, mode)
    if raw_rows is not None:
        return raw_rows
    return _label_time_sig_rows((sig_label or "").strip(), mode)


def _raw_time_sig_rows(raw: str, mode: str) -> list[str] | None:
    preset = _preset_time_sig_rows(raw, mode, raw=True)
    if preset is not None:
        return preset
    return _slash_time_sig_rows(raw, fraction=mode == "fraction")


def _preset_time_sig_rows(value: str, mode: str, *, raw: bool) -> list[str] | None:
    if mode == "numeric":
        numeric = {
            "C": " 4",
            "c": " 4",
            "4/4": " 4",
            "C|": " 2",
            "c|": " 2",
            "2/2": " 2",
            "O": " 3",
            "o": " 3",
            "3/4": " 3",
        }
        if not raw:
            numeric = {"C": " 4", "C|": " 2", "O": " 3"}
        row = numeric.get(value)
        return [row] if row is not None else None
    if mode == "fraction":
        fractions = {
            "C": [" 4", " /", " 4"],
            "c": [" 4", " /", " 4"],
            "C|": [" 2", " /", " 2"],
            "c|": [" 2", " /", " 2"],
            "2/2": [" 2", " /", " 2"],
            "O": [" 3", " /", " 4"],
            "o": [" 3", " /", " 4"],
        }
        if not raw:
            fractions = {key: rows for key, rows in fractions.items() if key in {"C", "C|", "O"}}
        return fractions.get(value)
    return None


def _slash_time_sig_rows(value: str, *, fraction: bool) -> list[str] | None:
    if "/" not in value:
        return None
    left, right = (part.strip() for part in value.split("/", 1))
    if fraction and left and right:
        return [f"{left[:2]:>2}", " /", f"{right[:2]:>2}"]
    return [left[:2].rjust(2)] if left else None


def _label_time_sig_rows(text: str, mode: str) -> list[str]:
    if not text:
        return []
    preset = _preset_time_sig_rows(text, mode, raw=False)
    if preset is not None:
        return preset
    return _symbolic_time_sig_rows(text)


def _symbolic_time_sig_rows(text: str) -> list[str]:
    if text in {"C", "O"}:
        # Common/cut time cue centered in staff without stem clutter.
        return [" ", text[:1], " "]
    if text == "C|":
        return [" ", "C|", " "]
    fraction = _slash_time_sig_rows(text, fraction=True)
    if fraction is not None:
        return fraction
    return [f"{text[:2]:>2}", "  ", "  "]


def show_time_cue_for_bar(
    *,
    bar_index: int,
    current_time_value: str,
    sig_label: str,
    prev_time_value: str | None = None,
) -> bool:
    if not sig_label:
        return False
    if bar_index == 0:
        return True
    if prev_time_value is None:
        return False
    return prev_time_value != current_time_value


def time_cue_side_pad(*, show_time_cue: bool, scale_bar: bool) -> int:
    # Reserve a small auftact lane inside the bar for the in-staff meter cue.
    return 2 if (show_time_cue and scale_bar) else 0


def time_cue_reserved_width(*, show_time_cue: bool, scale_bar: bool) -> int:
    return time_cue_side_pad(show_time_cue=show_time_cue, scale_bar=scale_bar) * 2


def tie_span_chars(style_mode: str) -> tuple[str, str, str] | None:
    mode = (style_mode or "bracket").strip().lower()
    if mode == "hide":
        return None
    if mode == "paren":
        return ("(", ")", "-")
    return ("[", "]", "-")


def slur_span_chars(style_mode: str) -> tuple[str, str, str] | None:
    mode = (style_mode or "paren").strip().lower()
    if mode == "hide":
        return None
    if mode == "bracket":
        return ("[", "]", "~")
    return ("(", ")", "~")


def hold_span_chars(style_mode: str) -> tuple[str, str, str] | None:
    mode = (style_mode or "angle").strip().lower()
    if mode == "hide":
        return None
    if mode == "paren":
        return ("(", ")", "_")
    return ("<", ">", "_")


def gliss_span_chars(style_mode: str) -> tuple[str, str, str] | None:
    mode = (style_mode or "slash").strip().lower()
    if mode == "hide":
        return None
    if mode == "paren":
        return ("(", ")", "/")
    if mode == "angle":
        return ("<", ">", "/")
    return ("/", "\\", "/")


def tie_notehead_hidden_cols(
    ties: list[tuple[int, int, int]],
    *,
    bar_index: int,
    mode: str,
) -> set[int]:
    if (mode or "show").strip().lower() != "hide":
        return set()
    hidden: set[int] = set()
    for b, _start, end in ties:
        if b != bar_index:
            continue
        hidden.add(end)
    return hidden


def tie_notehead_parenthesize_cols(
    ties: list[tuple[int, int, int]],
    *,
    bar_index: int,
    mode: str,
) -> set[int]:
    if (mode or "show").strip().lower() != "parenthesize":
        return set()
    cols: set[int] = set()
    for b, _start, end in ties:
        if b != bar_index:
            continue
        cols.add(end)
    return cols
