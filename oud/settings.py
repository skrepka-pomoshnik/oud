from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

try:
    tomllib: ModuleType = importlib.import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - fallback for Python < 3.11
    tomllib = importlib.import_module("tomli")


def _resolve_config_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    config_home = Path.home() / ".config" / "oud" / path
    if config_home.exists():
        return config_home
    return cwd_path

DEFAULT_SETTINGS: dict[str, str] = {
    "style": "french",
    "measures": "every",
    "measuresstep": "10",
    "tuning": "g2c3f3a3d4g4",
    "tuninglabels": "relative",
    "strings": "6",
    "showtuning": "on",
    "flagstyle": "standard",
    "flagstems": "single",
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
    "spacing": "12",
    "layout": "auto",
    "justify": "stretch",
    "beatsnap": "off",
    "barpad": "1",
    "maxbars": "0",
    "barsperline": "0",
    "chordwrap": "0",
    "linelen": "80",
    "flagredundant": "on",
    "staffthick": "1",
    "fontstyle": "modern",
    "lynoteheads": "classic",
    "charstyle": "standard",
    "midipatch": "24",
    "midigate": "85",
    "tempo": "90",
    "soundfont": "",
    "bassstrings": "",
    "basslabels": "tuning",
    "grid": "off",
    "showdur": "off",
    "showspans": "off",
    "showfingerings": "on",
    "showornaments": "on",
    "showextras": "off",
    "showft3extras": "on",
    "ft3fingering": "both",
    "ft3ornaments": "both",
    "showtactus": "off",
    "italianorient": "normal",
    "italianmultifret": "on",
    "viewinvert": "off",
    "frenchc": "normal",
    "maxrepeats": "30",
    "minimumfret": "0",
    "maxstretch": "0",
    "restrainopenstrings": "off",
    "newbars": "8",
}


def load_settings(path: str) -> dict[str, str]:
    data: dict[str, str] = dict(DEFAULT_SETTINGS)
    file_path = _resolve_config_path(path)
    if not file_path.exists():
        return data
    try:
        with file_path.open("rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return data
    settings = raw.get("settings", {})
    if not isinstance(settings, dict):
        return data
    for key, value in settings.items():
        if key not in data:
            continue
        if isinstance(value, str):
            data[key] = value
        elif isinstance(value, int):
            data[key] = str(value)
    if data.get("layout") == "stretch":
        data["layout"] = "auto"
        data["justify"] = "edge"
    return data


def save_settings(path: str, settings: dict[str, str]) -> None:
    file_path = _resolve_config_path(path)
    merged = load_settings(path)
    merged.update(settings)
    if file_path.parent:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[settings]"]
    for key in sorted(merged.keys()):
        value = merged[key]
        if value == "":
            continue
        if value.isdigit():
            lines.append(f"{key} = {value}")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    content = "\n".join(lines) + "\n"
    file_path.write_text(content, encoding="utf-8")
