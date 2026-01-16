from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Dict

DEFAULT_SETTINGS: Dict[str, str] = {
    "style": "french",
    "measures": "start",
    "tuning": "",
    "strings": "6",
    "flagstyle": "standard",
    "time": "C",
    "key": "C",
    "countdots": "off",
    "keys": "vim+arrows",
    "spacing": "12",
    "linelen": "80",
    "staffthick": "1",
    "fontstyle": "modern",
    "charstyle": "standard",
    "midipatch": "24",
    "tempo": "90",
    "grid": "off",
    "showdur": "off",
    "showextras": "off",
    "showtactus": "off",
    "italianorient": "normal",
    "frenchc": "normal",
    "frenche": "normal",
}


def load_settings(path: str) -> Dict[str, str]:
    data: Dict[str, str] = dict(DEFAULT_SETTINGS)
    file_path = Path(path)
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


def save_settings(path: str, settings: Dict[str, str]) -> None:
    file_path = Path(path)
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
