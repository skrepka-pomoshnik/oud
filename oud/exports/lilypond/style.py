from __future__ import annotations

from typing import Literal

LilyPondProfile = Literal["classic", "petrucci"]


def profile_name(settings: dict[str, str]) -> LilyPondProfile:
    """Return the requested publication profile, defaulting to Oud's house style."""
    if settings.get("lyprofile") == "classic":
        return "classic"
    return "petrucci"


def paper_block(settings: dict[str, str]) -> list[str]:
    """Build deterministic paper policy independently of score semantics."""
    paper_size = settings.get("lypapersize", "a4")
    if paper_size not in {"a4", "letter"}:
        paper_size = "a4"
    if profile_name(settings) == "classic":
        return [f'#(set-default-paper-size "{paper_size}")', r"\paper { indent = 0\mm }"]
    return [
        f'#(set-default-paper-size "{paper_size}")',
        "#(set-global-staff-size 16)",
        r"\paper {",
        r"  indent = 22\mm",
        r"  short-indent = 0\mm",
        "  ragged-last = ##f",
        "  ragged-bottom = ##t",
        "  ragged-last-bottom = ##t",
        r"  top-margin = 10\mm",
        r"  bottom-margin = 10\mm",
        r"  left-margin = 12\mm",
        r"  right-margin = 12\mm",
        "  top-system-spacing.basic-distance = #8",
        "  top-system-spacing.minimum-distance = #6",
        "  markup-system-spacing.basic-distance = #8",
        "  markup-system-spacing.minimum-distance = #6",
        "  system-system-spacing.basic-distance = #8",
        "  system-system-spacing.minimum-distance = #6",
        "  score-system-spacing.basic-distance = #8",
        "  score-system-spacing.minimum-distance = #6",
        "  oddFooterMarkup = ##f",
        "  evenFooterMarkup = ##f",
        "}",
    ]


def score_overrides(settings: dict[str, str]) -> tuple[str, ...]:
    """Return score-level optical rules for the selected profile."""
    if profile_name(settings) == "classic":
        return ()
    return (r"    \override BarNumber.font-size = #-1",)


def tab_staff_overrides(settings: dict[str, str]) -> tuple[str, ...]:
    """Return a restrained movable-type hierarchy for tablature output."""
    if profile_name(settings) == "classic":
        return ()
    return (
        r"    \override StaffSymbol.thickness = #0.7",
        r"    \override BarLine.hair-thickness = #0.9",
        r"    \override BarLine.thick-thickness = #4.0",
        r"    \override TabNoteHead.font-size = #-1",
        r"    \override Stem.thickness = #0.9",
        r"    \override Beam.beam-thickness = #0.48",
    )
