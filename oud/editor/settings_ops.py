from __future__ import annotations

from collections.abc import Callable

from oud.core.tab_policy import apply_tabnotation_preset
from oud.core.tuning_utils import tuning_preset
from oud.editor.edit_ops import apply_override
from oud.editor.ops import (
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    italian_to_fret,
)
from oud.editor.preset_convert import apply_meta_preset_content_conversion
from oud.editor.state import EditorState
from oud.settings import DEFAULT_SETTINGS, save_settings

SetHandler = Callable[[EditorState, str], bool]

META_PRESETS: dict[str, dict[str, str]] = {
    "lute": {
        "style": "french",
        "strings": "6",
        "tuning": "g2c3f3a3d4g4",
        "italianorient": "normal",
        "viewinvert": "off",
        "basslabels": "tuning",
        "bassstrings": "",
    },
    "guitar": {
        "style": "italian",
        "strings": "6",
        "tuning": "e2a2d3g3b3e4",
        "italianorient": "reverse",
        "viewinvert": "off",
        "basslabels": "numeric",
        "bassstrings": "",
    },
}

_BOOL_KEYS = {
    "countdots",
    "flagredundant",
    "grid",
    "showdur",
    "showextras",
    "showtactus",
    "italianmultifret",
    "viewinvert",
    "showtuning",
    "restrainopenstrings",
}

_INT_KEYS = {
    "maxbars",
    "barsperline",
    "chordwrap",
    "barpad",
    "maxchords",
    "maxrepeats",
    "linelen",
    "bargap",
    "staffthick",
    "midipatch",
    "midigate",
    "tempo",
    "newbars",
    "minimumfret",
    "maxstretch",
}

_ENUM_VALUES: dict[str, tuple[set[str], str]] = {
    "style": ({"french", "italian"}, "Style must be french or italian"),
    "measures": ({"start", "every", "five"}, "Measures must be start/every/five"),
    "flagstyle": (
        {"standard", "italian", "thin", "board", "capirola", "englishgrid", "continental"},
        "Flagstyle must be standard/italian/thin/board/capirola/englishgrid/continental",
    ),
    "flagstems": ({"single", "double"}, "Flagstems must be single/double"),
    "keys": (
        {"vim", "vim+arrows", "casual", "casual+arrows"},
        "Keys must be vim/vim+arrows/casual/casual+arrows",
    ),
    "layout": (
        {"packed", "spread", "auto", "stretch"},
        "Layout must be packed/spread/auto/stretch",
    ),
    "justify": (
        {"stretch", "center", "compact", "smart", "edge"},
        "Justify must be stretch/center/compact/smart/edge",
    ),
    "scrollmode": (
        {"smooth", "page"},
        "Scrollmode must be smooth/page",
    ),
    "beatsnap": (
        {"off", "soft"},
        "Beatsnap must be off/soft",
    ),
    "timesigstyle": (
        {"symbol", "numeric", "fraction"},
        "Timesigstyle must be symbol/numeric/fraction",
    ),
    "tiecuestyle": (
        {"bracket", "paren", "hide"},
        "Tiecuestyle must be bracket/paren/hide",
    ),
    "tienoteheads": (
        {"show", "hide", "parenthesize"},
        "Tienoteheads must be show/hide/parenthesize",
    ),
    "slurcuestyle": (
        {"paren", "bracket", "hide"},
        "Slurcuestyle must be paren/bracket/hide",
    ),
    "holdcuestyle": (
        {"angle", "paren", "hide"},
        "Holdcuestyle must be angle/paren/hide",
    ),
    "tabnotation": (
        {"minimal", "full"},
        "Tabnotation must be minimal/full",
    ),
    "fontstyle": (
        {"modern", "renaissance", "baroque"},
        "Fontstyle must be modern/renaissance/baroque",
    ),
    "basslabels": ({"numeric", "slash", "tuning"}, "Basslabels must be numeric/slash/tuning"),
    "italianorient": ({"normal", "reverse"}, "Italianorient must be normal/reverse"),
    "frenchc": ({"normal", "alt"}, "Frenchc must be normal/alt"),
}

def _set_bool(state: EditorState, key: str, value: str) -> bool:
    if value not in ("on", "off"):
        state.message = f"{key.capitalize()} must be on/off"
        return False
    state.settings[key] = value
    return True


def _set_int(state: EditorState, key: str, value: str) -> bool:
    if not value.isdigit():
        state.message = f"{key.capitalize()} must be int"
        return False
    state.settings[key] = value
    return True


def _set_enum(state: EditorState, key: str, value: str) -> bool:
    allowed, error = _ENUM_VALUES[key]
    if value not in allowed:
        state.message = error
        return False
    if key == "layout" and value == "stretch":
        state.settings["layout"] = "auto"
        state.settings["justify"] = "edge"
        return True
    if key == "tabnotation":
        return apply_tabnotation_preset(state.settings, value)
    if key == "style":
        current = state.settings.get("style", "french")
        if value != current:
            convert_overrides(state, value)
    state.settings[key] = value
    return True


def _set_strings(state: EditorState, value: str) -> bool:
    try:
        count = int(value)
    except ValueError:
        state.message = "Invalid strings value"
        return False
    if count < 4 or count > 13:
        state.message = "Strings must be 4-13"
        return False
    state.piece.strings = count
    state.cursor_string = min(state.cursor_string, count - 1)
    state.settings["strings"] = str(count)
    return True


def _set_measuresstep(state: EditorState, value: str) -> bool:
    if not value.isdigit() or int(value) < 1:
        state.message = "Measuresstep must be >=1"
        return False
    state.settings["measuresstep"] = value
    return True


def _set_tuning(state: EditorState, value: str) -> bool:
    preset = tuning_preset(value)
    state.settings["tuning"] = preset if preset else value
    return True


def _set_spacing(state: EditorState, value: str) -> bool:
    try:
        spacing = int(value)
    except ValueError:
        state.message = "Spacing must be int"
        return False
    state.bar_width = max(4, spacing)
    state.settings["spacing"] = str(spacing)
    return True


def _set_title(state: EditorState, value: str) -> bool:
    state.piece.title = value
    state.modified = True
    return True


def _set_author(state: EditorState, value: str) -> bool:
    state.piece.author = value
    state.modified = True
    return True


def _set_composer(state: EditorState, value: str) -> bool:
    state.piece.composer = value
    state.modified = True
    return True


def _set_charstyle(state: EditorState, value: str) -> bool:
    state.settings["charstyle"] = value
    return True


def _set_time_or_key(state: EditorState, key: str, value: str) -> bool:
    state.settings[key] = value
    return True


def _set_soundfont(state: EditorState, value: str) -> bool:
    state.settings["soundfont"] = value
    return True


def _apply_meta_preset(state: EditorState, name: str) -> bool:
    preset = META_PRESETS.get(name)
    if preset is None:
        return False
    conversion_note = apply_meta_preset_content_conversion(state, name, target_preset=preset)
    style = preset.get("style")
    if style is not None:
        _set_enum(state, "style", style)
    strings = preset.get("strings")
    if strings is not None:
        _set_strings(state, strings)
    tuning = preset.get("tuning")
    if tuning is not None:
        _set_tuning(state, tuning)
    for key, value in preset.items():
        if key in {"style", "strings", "tuning"}:
            continue
        state.settings[key] = value
    state.message = f"Applied preset: {name}" + (f" ({conversion_note})" if conversion_note else "")
    return True


def set_preset_names() -> tuple[str, ...]:
    return tuple(sorted(META_PRESETS.keys()))


def set_key_names() -> tuple[str, ...]:
    keys = set(DEFAULT_SETTINGS.keys())
    keys.update(_HANDLERS.keys())
    keys.update(_BOOL_KEYS)
    keys.update(_INT_KEYS)
    keys.update(_ENUM_VALUES.keys())
    return tuple(sorted(keys))


def set_value_options(key: str) -> tuple[str, ...]:  # noqa: PLR0911
    if key in _BOOL_KEYS:
        return ("on", "off")
    if key in _ENUM_VALUES:
        allowed, _error = _ENUM_VALUES[key]
        return tuple(sorted(allowed))
    if key == "tuning":
        # Common presets + aliases accepted by tuning_preset(); free-form tuning still allowed.
        presets = (
            "renaissance",
            "renaissance6",
            "ren6",
            "ren7",
            "ren8",
            "ren9",
            "ren10",
            "ren11",
            "ren12",
            "ren13",
            "guitar",
            "guitarlute",
            "baroque",
            "baroque11",
            "baroque13",
            "baroque-dminor",
            "baroque-sharp",
            "baroque-flat",
        )
        return tuple(sorted(set(presets)))
    if key in {"time", "timesig"}:
        return ("C", "O", "2/2", "3/4", "4/4", "6/8", "auto")
    if key == "measuresstep":
        return ("1", "5", "10")
    if key == "minimumfret":
        return ("0", "1", "2", "3", "5", "7")
    if key == "maxstretch":
        return ("0", "2", "3", "4", "5", "7")
    if key in {"strings", "staff"}:
        return tuple(str(v) for v in range(4, 14))
    if key == "set":
        return set_preset_names()
    return ()


_HANDLERS: dict[str, SetHandler] = {
    "strings": _set_strings,
    "staff": _set_strings,
    "measuresstep": _set_measuresstep,
    "tuning": _set_tuning,
    "spacing": _set_spacing,
    "title": _set_title,
    "author": _set_author,
    "composer": _set_composer,
    "charstyle": _set_charstyle,
    "time": lambda state, value: _set_time_or_key(state, "time", value),
    "timesig": lambda state, value: _set_time_or_key(state, "time", value),
    "key": lambda state, value: _set_time_or_key(state, "key", value),
    "soundfont": _set_soundfont,
}


def apply_set_command(  # noqa: C901
    state: EditorState,
    args: str,
    config_path: str,
    *,
    save_fn: Callable[[str, dict[str, str]], None] = save_settings,
) -> None:
    if not args:
        state.message = "No set args"
        return
    for token in args.split():
        if "=" not in token:
            if token in _BOOL_KEYS:
                state.settings[token] = "on"
                continue
            if token.startswith("no"):
                key = token[2:]
                if key in _BOOL_KEYS:
                    state.settings[key] = "off"
                    continue
            if _apply_meta_preset(state, token):
                continue
            state.message = f"Invalid set token: {token}"
            continue
        key, value = token.split("=", 1)
        if key in _HANDLERS:
            _HANDLERS[key](state, value)
            continue
        if key in _BOOL_KEYS:
            _set_bool(state, key, value)
            continue
        if key in _INT_KEYS:
            _set_int(state, key, value)
            continue
        if key in _ENUM_VALUES:
            _set_enum(state, key, value)
            continue
        state.message = f"Unknown set key: {key}"
    save_fn(config_path, state.settings)


def convert_overrides(state: EditorState, target_style: str) -> None:
    converted = 0
    skipped = 0
    items = list(state.overrides.items())
    for key, ch in items:
        if target_style == "italian":
            if ch == "k":
                out = "x"
            else:
                fret = french_to_fret(ch)
                out = fret_to_italian(fret) if fret is not None else None
        elif ch == "x":
            out = "k"
        else:
            fret = italian_to_fret(ch)
            out = fret_to_french(fret) if fret is not None else None
        if out is None:
            skipped += 1
            continue
        apply_override(state, key, out)
        converted += 1
    state.message = f"Converted {converted}, skipped {skipped}"
