from __future__ import annotations


def tuning_count(tuning: str) -> int:
    count = 0
    idx = 0
    while idx < len(tuning):
        ch = tuning[idx]
        if ch.isalpha():
            count += 1
            idx += 1
            if idx < len(tuning) and tuning[idx] in "+-#b":
                idx += 1
            while idx < len(tuning) and tuning[idx].isdigit():
                idx += 1
        else:
            idx += 1
    return count


def tuning_preset(value: str) -> str | None:
    presets = {
        "renaissance": "g2c3f3a3d4g4",
        "renaissance7": "f2g2c3f3a3d4g4",
        "renaissance8": "e2f2g2c3f3a3d4g4",
        "renaissance9": "d2e2f2g2c3f3a3d4g4",
        "renaissance10": "c2d2e2f2g2c3f3a3d4g4",
        "renaissance11": "b1c2d2e2f2g2c3f3a3d4g4",
        "renaissance12": "a1b1c2d2e2f2g2c3f3a3d4g4",
        "renaissance13": "g1a1b1c2d2e2f2g2c3f3a3d4g4",
        "guitar": "e4a3d3f+3b2e2",
        "dminor": "a4b-4c4d4e4f4g4a3d3f3a2d2f2",
        "sharp": "c4d4e4f+4g4a3d3g3b2d2f+2",
        "flat": "c4d4e-4f4g4a3d3g3a+2d2f2",
    }
    return presets.get(value)


def parse_bass_strings(value: str) -> list[str]:
    if not value:
        return []
    tokens: list[str] = []
    for part in value.replace(",", " ").split():
        token = part.strip()
        if not token:
            continue
        if not any(ch.isalpha() for ch in token):
            continue
        tokens.append(token)
    return tokens
