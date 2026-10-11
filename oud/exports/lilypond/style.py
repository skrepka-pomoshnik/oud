from __future__ import annotations

from typing import Literal

# Measured on Sarge Gerbode's Fronimo PDFs: about eight bars per system, boxed bar numbers every fifth bar,
# italic serif course letters, thin stems and beams in a row above the staff.
GERBODE_STAFF_SIZE = 18
GERBODE_INDENT_MM = 8
GERBODE_SCORE_OVERRIDES = (
    r"    \override BarNumber.font-size = #-3",
    r"    \override BarNumber.stencil = #(make-stencil-boxer 0.1 0.25 ly:text-interface::print)",
    "    barNumberVisibility = #(every-nth-bar-number-visible 5)",
    r"    \override BarNumber.break-visibility = #end-of-line-invisible",
)
GERBODE_TAB_OVERRIDES = (
    r"    \override StaffSymbol.thickness = #0.7",
    r"    \override BarLine.hair-thickness = #0.9",
    r"    \override BarLine.thick-thickness = #4.0",
    r"    \override TabNoteHead.font-family = #'roman",
    r"    \override TabNoteHead.font-shape = #'italic",
    r"    \override TabNoteHead.font-series = #'medium",
    r"    \override Stem.thickness = #0.7",
    r"    \override Beam.beam-thickness = #0.4",
    "    \\override Beam.damping = #+inf.0",
    r"    \override Stem.length = #5",
)

LilyPondProfile = Literal["classic", "petrucci", "gerbode"]


def profile_name(settings: dict[str, str]) -> LilyPondProfile:
    """Return the requested publication profile, defaulting to Oud's house style."""
    requested = settings.get("lyprofile")
    if requested == "classic":
        return "classic"
    if requested == "gerbode":
        return "gerbode"
    return "petrucci"


def paper_block(settings: dict[str, str]) -> list[str]:
    """Build deterministic paper policy independently of score semantics."""
    paper_size = settings.get("lypapersize", "a4")
    if paper_size not in {"a4", "letter"}:
        paper_size = "a4"
    if profile_name(settings) == "classic":
        return [f'#(set-default-paper-size "{paper_size}")', r"\paper { indent = 0\mm }"]
    gerbode = profile_name(settings) == "gerbode"
    return [
        f'#(set-default-paper-size "{paper_size}")',
        f"#(set-global-staff-size {GERBODE_STAFF_SIZE if gerbode else 16})",
        r"\paper {",
        rf"  indent = {GERBODE_INDENT_MM if gerbode else 22}\mm",
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
    if profile_name(settings) == "gerbode":
        return GERBODE_SCORE_OVERRIDES
    return (r"    \override BarNumber.font-size = #-1",)


def tab_staff_overrides(settings: dict[str, str]) -> tuple[str, ...]:
    """Return a restrained movable-type hierarchy for tablature output."""
    if profile_name(settings) == "classic":
        return ()
    if profile_name(settings) == "gerbode":
        return GERBODE_TAB_OVERRIDES
    return (
        r"    \override StaffSymbol.thickness = #0.7",
        r"    \override BarLine.hair-thickness = #0.9",
        r"    \override BarLine.thick-thickness = #4.0",
        r"    \override TabNoteHead.font-size = #-1",
        r"    \override Stem.thickness = #0.9",
        r"    \override Beam.beam-thickness = #0.48",
    )
