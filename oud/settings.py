from __future__ import annotations

import os
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path

SETTINGS_TABLE = "settings"
_APP_CONFIG_DIR = "oud"


class SettingsFileError(OSError):
    """The settings file cannot be read or safely rewritten."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")


def config_home() -> Path:
    """Return the user configuration directory for Oud (XDG base directory)."""

    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / _APP_CONFIG_DIR


def _resolve_config_path(path: str) -> Path:
    """Resolve a config name without ever claiming an unrelated working-directory file.

    Absolute paths are used as given. A relative name is a project-local config
    only when that file already carries an Oud ``[settings]`` table; otherwise it
    lives under the user configuration directory.
    """

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    cwd_path = Path.cwd() / candidate
    if cwd_path.is_file() and _has_settings_table(cwd_path):
        return cwd_path
    return config_home() / candidate


def _load_toml(file_path: Path) -> dict[str, object]:
    try:
        with file_path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SettingsFileError(file_path, f"cannot read: {exc}") from exc


def _has_settings_table(file_path: Path) -> bool:
    try:
        return isinstance(_load_toml(file_path).get(SETTINGS_TABLE), dict)
    except SettingsFileError:
        return False


DEFAULT_SETTINGS: dict[str, str] = {
    "bottompanel": "on",
    "style": "french",
    "measures": "system",
    "measuresstep": "10",
    "tuning": "g2c3f3a3d4g4",
    "tuninglabels": "relative",
    "strings": "6",
    "showtuning": "on",
    "contrast": "normal",
    "theme": "auto",
    "flagstyle": "standard",
    "flagstems": "single",
    "flaglean": "right",
    "flagplace": "above",
    "dotplacement": "afterflag",
    "tabnotation": "minimal",
    "time": "C",
    "timesigstyle": "symbol",
    "tiecuestyle": "bracket",
    "tienoteheads": "show",
    "slurcuestyle": "paren",
    "holdcuestyle": "angle",
    "glisscuestyle": "hide",
    "key": "C",
    "countdots": "off",
    "keys": "vim+arrows",
    "movementmode": "visual",
    "completion": "prefix",
    "spacing": "12",
    "layout": "auto",
    "justify": "stretch",
    "scrollmode": "smooth",
    "playbackscroll": "on",
    "playverses": "once",
    "beatsnap": "off",
    "barpad": "1",
    "maxbars": "0",
    "barsperline": "0",
    "chordwrap": "0",
    "linelen": "0",
    "flagredundant": "on",
    "staffthick": "1",
    "fontstyle": "modern",
    "lynoteheads": "classic",
    "lyprofile": "petrucci",
    "lilypond": "lilypond-2.26",
    "lilypondversion": "2.26",
    "lybarsperline": "0",
    "lysystemsperpage": "0",
    "lytabrhythm": "full",
    "lypapersize": "letter",
    "lysourceheading": "off",
    "charstyle": "standard",
    "fretlabelmode": "auto",
    "scoreview": "score",
    "duetscoreview": "auto",
    "midipatch": "24",
    "midivocalpatch": "53",
    "midivocalinfer": "off",
    "midigate": "85",
    "tempo": "90",
    "soundfont": "",
    "bassstrings": "",
    "basslabels": "tuning",
    "showdur": "off",
    "showspans": "off",
    "showtuplets": "off",
    "showmelody": "on",
    "showlyrics": "on",
    "lyricmode": "first",
    "lyricverse": "1",
    "vocalpos": "top",
    "showfingerings": "on",
    "showornaments": "on",
    "showextras": "off",
    "showft3extras": "on",
    "ft3fingering": "both",
    "ft3ornaments": "both",
    "showtactus": "off",
    "italianorient": "normal",
    "italianmultifret": "on",
    "multifretspacing": "collision-safe",
    "viewinvert": "off",
    "frenchc": "normal",
    "maxrepeats": "30",
    "minimumfret": "0",
    "maxstretch": "0",
    "restrainopenstrings": "off",
    "newbars": "8",
}


# Properties of the open document. The config file may seed new documents with
# them, but session changes to these keys never persist.
DOCUMENT_SETTING_KEYS = frozenset({"style", "strings", "tuning", "time", "key", "tempo", "bassstrings"})


def is_preference_key(key: str) -> bool:
    return key in DEFAULT_SETTINGS and key not in DOCUMENT_SETTING_KEYS


def preference_changes(before: Mapping[str, str], after: Mapping[str, str]) -> dict[str, str]:
    """Return preference keys whose value changed; document and runtime keys are excluded."""

    return {key: value for key, value in after.items() if is_preference_key(key) and before.get(key) != value}


def _read_settings_file(file_path: Path) -> dict[str, object] | None:
    if not file_path.exists():
        return None
    try:
        raw = _load_toml(file_path)
    except SettingsFileError:
        return None
    settings = raw.get(SETTINGS_TABLE, {})
    if not isinstance(settings, dict):
        return None
    return {str(key): value for key, value in settings.items()}


def _merge_settings(data: dict[str, str], settings: Mapping[str, object]) -> None:
    for key, value in settings.items():
        if key not in data:
            continue
        if isinstance(value, str):
            data[key] = value
        elif isinstance(value, int):
            data[key] = str(value)


def load_settings(path: str) -> dict[str, str]:
    data: dict[str, str] = dict(DEFAULT_SETTINGS)
    file_path = _resolve_config_path(path)
    settings = _read_settings_file(file_path)
    if settings is None:
        return data
    _merge_settings(data, settings)
    if data.get("layout") == "stretch":
        data["layout"] = "auto"
        data["justify"] = "edge"
    return data


def _stored_settings(file_path: Path) -> dict[str, str]:
    """Return the existing ``[settings]`` values, refusing files Oud does not own."""

    if not file_path.exists():
        return {}
    raw = _load_toml(file_path)
    foreign = sorted(key for key in raw if key != SETTINGS_TABLE)
    if foreign:
        raise SettingsFileError(file_path, f"contains non-Oud tables or keys: {', '.join(foreign)}")
    table = raw.get(SETTINGS_TABLE, {})
    if not isinstance(table, dict):
        raise SettingsFileError(file_path, f"[{SETTINGS_TABLE}] is not a table")
    # Unknown keys are preserved; only scalar values can be written back.
    return {str(key): _scalar_text(value) for key, value in table.items() if isinstance(value, (str, int))}


def _scalar_text(value: str | int) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


def _toml_line(key: str, value: str) -> str:
    if value.isdigit():
        return f"{key} = {value}"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key} = "{escaped}"'


def save_settings(path: str, settings: Mapping[str, str]) -> None:
    """Merge ``settings`` into the ``[settings]`` table and replace the file atomically.

    An empty value removes the key so the built-in default applies again.
    """

    file_path = _resolve_config_path(path)
    merged = _stored_settings(file_path)
    merged.update(settings)
    lines = [f"[{SETTINGS_TABLE}]"]
    lines.extend(_toml_line(key, value) for key, value in sorted(merged.items()) if value != "")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{file_path.name}.", dir=file_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        Path(temp_name).replace(file_path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
