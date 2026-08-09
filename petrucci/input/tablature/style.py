from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TabStylePolicy:
    style: str
    basslabels: str
    flagstyle: str
    flaglean: str
    flagstems: str
    dotplacement: str
    tiecuestyle: str
    tienoteheads: str
    slurcuestyle: str
    holdcuestyle: str
    glisscuestyle: str
    italianorient: str
    viewinvert: str
    showfingerings: bool
    showornaments: bool

    @property
    def stem_width(self) -> int:
        return 2 if self.flagstems == "double" else 1

    @property
    def reverse_rows(self) -> bool:
        return self.viewinvert == "on" or (self.style == "italian" and self.italianorient == "reverse")


def resolve_tab_style_policy(settings: dict[str, str]) -> TabStylePolicy:
    show_ft3 = settings.get("showft3extras", "on")
    return TabStylePolicy(
        style=settings.get("style", "french"),
        basslabels=settings.get("basslabels", "tuning"),
        flagstyle=settings.get("flagstyle", "standard"),
        flaglean=settings.get("flaglean", "right"),
        flagstems=settings.get("flagstems", "single"),
        dotplacement=settings.get("dotplacement", "afterflag"),
        tiecuestyle=settings.get("tiecuestyle", "bracket"),
        tienoteheads=settings.get("tienoteheads", "show"),
        slurcuestyle=settings.get("slurcuestyle", "paren"),
        holdcuestyle=settings.get("holdcuestyle", "angle"),
        glisscuestyle=settings.get("glisscuestyle", "hide"),
        italianorient=settings.get("italianorient", "normal"),
        viewinvert=settings.get("viewinvert", "off"),
        showfingerings=settings.get("showfingerings", show_ft3) == "on",
        showornaments=settings.get("showornaments", show_ft3) == "on",
    )
