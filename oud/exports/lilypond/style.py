from __future__ import annotations

from typing import Literal

# Measured on Sarge Gerbode's Fronimo PDFs: about eight bars per system, boxed bar numbers every fifth bar,
# italic serif course letters, thin stems and beams in a row above the staff.
GERBODE_STAFF_SIZE = 18
GERBODE_INDENT_MM = 0
GERBODE_FONT = "EB Garamond"
GERBODE_SCORE_OVERRIDES = (
    r"    \override BarNumber.font-size = #-3",
    r"    \override BarNumber.stencil = #(make-stencil-boxer 0.1 0.25 ly:text-interface::print)",
    "    barNumberVisibility = #(every-nth-bar-number-visible 5)",
    r"    \override BarNumber.break-visibility = #end-of-line-invisible",
    # Fronimo starts a line's first chord right after the opening barline or mensuration sign.
    r"    \override LeftEdge.space-alist.first-note = #'(fixed-space . 0.6)",
    r"    \override BarLine.space-alist.first-note = #'(fixed-space . 0.6)",
    r"    \override TimeSignature.space-alist.first-note = #'(fixed-space . 0.8)",
)
GERBODE_STEM_SCHEME = (
    "#(define (detached-stem grob)",
    "   (let* ((stil (ly:stem::print grob))",
    "          (y (ly:stencil-extent stil Y))",
    "          (x (ly:stencil-extent stil X))",
    "          (low (max (car y) (- (cdr y) 2.4))))",
    "     (if (< low (cdr y)) (ly:round-filled-box x (cons low (cdr y)) 0) point-stencil)))",
)
GERBODE_PAPER_MARKUP = (
    r"  bookTitleMarkup = \markup \fill-line {",
    r"    \fontsize #5 \fromproperty #'header:title",
    r"    \fontsize #1 \fromproperty #'header:composer",
    "  }",
    r"  oddFooterMarkup = \markup \override #'(baseline-skip . 3.5) \column {",
    r"    \fontsize #-3 \fromproperty #'header:source",
    r"    \fontsize #-3 \fromproperty #'header:tagline",
    "  }",
    "  evenFooterMarkup = ##f",
)
GERBODE_TAB_OVERRIDES = (
    r"    \override StaffSymbol.thickness = #0.7",
    r"    \override BarLine.hair-thickness = #0.9",
    r"    \override BarLine.thick-thickness = #4.0",
    r"    \override TabNoteHead.font-family = #'serif",
    r"    \override TabNoteHead.font-shape = #'italic",
    r"    \override TabNoteHead.font-series = #'medium",
    r"    \override TabNoteHead.font-size = #1.5",
    r"    \override Stem.thickness = #0.5",
    r"    \override Beam.beam-thickness = #0.16",
    r"    \override Beam.gap = #0.4",
    "    \\override Beam.damping = #+inf.0",
    # Fronimo's rhythm row floats above the staff: the stem is clipped to a short stub under the beams
    # and the beams sit at a fixed height.
    r"    \override Stem.length = #8",
    r"    \override Beam.positions = #'(5.5 . 5.5)",
)
# \tabFullNotation resets the stem stencil inside the voice, so this override is emitted after it.
# Fronimo closes a beam group at every quarter beat, whatever the meter.
GERBODE_BEAT_METERS = (("2/2", 4), ("4/4", 4), ("3/4", 3), ("3/2", 6), ("6/4", 6), ("2/4", 2))
GERBODE_VOICE_OVERRIDES = (
    r"  \override Stem.stencil = #detached-stem",
    *(
        rf"  \overrideTimeSignatureSettings {meter} #'(1 . 4) #'({' '.join('1' * beats)}) #'()"
        for meter, beats in GERBODE_BEAT_METERS
    ),
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
        *(_gerbode_font(settings) if gerbode else ()),
        *(GERBODE_PAPER_MARKUP if gerbode else ("  oddFooterMarkup = ##f", "  evenFooterMarkup = ##f")),
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


def _gerbode_font(settings: dict[str, str]) -> tuple[str, ...]:
    """Renaissance-style roman face for course letters and text; ``lyfont`` overrides the default family.

    LilyPond falls back to its own face when the family is not installed, so the name is not validated here.
    """
    family = (settings.get("lyfont") or GERBODE_FONT).replace('"', "")
    return (f'  property-defaults.fonts.serif = "{family}"',)


def scheme_helpers(settings: dict[str, str]) -> tuple[str, ...]:
    """Scheme definitions the profile's overrides refer to; emitted before the layout block."""
    return GERBODE_STEM_SCHEME if profile_name(settings) == "gerbode" else ()


def voice_overrides(settings: dict[str, str]) -> tuple[str, ...]:
    """Overrides that must follow ``\\tabFullNotation`` inside the tab voice."""
    return GERBODE_VOICE_OVERRIDES if profile_name(settings) == "gerbode" else ()
