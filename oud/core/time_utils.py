from __future__ import annotations


def parse_time_signature_value(text: str) -> tuple[int, int] | None:
    value = text.strip()
    if value in ("C", "c"):
        return 4, 4
    if value in ("O", "o"):
        return 3, 4
    if "/" in value:
        parts = value.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            if beats > 0 and unit > 0:
                return beats, unit
    return None
