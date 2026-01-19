from __future__ import annotations

import tomllib
from pathlib import Path


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
    "measures": "start",
    "measuresstep": "1",
    "tuning": "g2c3f3a3d4g4",
    "tuninglabels": "relative",
    "strings": "6",
    "flagstyle": "standard",
    "time": "C",
    "key": "C",
    "countdots": "off",
    "keys": "vim+arrows",
    "spacing": "12",
    "spacingmode": "packed",
    "maxbars": "0",
    "linelen": "80",
    "flagredundant": "on",
    "staffthick": "1",
    "fontstyle": "modern",
    "charstyle": "standard",
    "midipatch": "24",
    "midigate": "85",
    "tempo": "90",
    "soundfont": "",
    "grid": "off",
    "showdur": "off",
    "showextras": "off",
    "showtactus": "off",
    "italianorient": "normal",
    "frenchc": "normal",
    "frenche": "normal",
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
        if isinstance(value, str):
            data[key] = value
        elif isinstance(value, int):
            data[key] = str(value)
    return data


def save_settings(path: str, settings: dict[str, str]) -> None:
    file_path = _resolve_config_path(path)
    if file_path.parent:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[settings]"]
    for key in sorted(settings.keys()):
        value = settings[key]
        if value == "":
            continue
        if value.isdigit():
            lines.append(f"{key} = {value}")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    content = "\n".join(lines) + "\n"
    file_path.write_text(content, encoding="utf-8")
