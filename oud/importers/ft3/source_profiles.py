from __future__ import annotations

from dataclasses import dataclass

from petrucci.core.model import Piece


@dataclass(frozen=True, slots=True)
class _SourceTuningProfile:
    composer: str
    title_fragment: str
    key: str
    strings: int
    tuning: str
    provenance: str
    subtitle_fragment: str | None = None
    part: str | None = None

    def matches(self, piece: Piece) -> bool:
        title = (piece.title or "").casefold()
        subtitle = (piece.subtitle or "").casefold()
        composer = (piece.composer or "").casefold()
        key = (piece.key or piece.raw_metadata.get("lkey", "")).casefold()
        return (
            self.composer.casefold() == composer
            and self.title_fragment.casefold() in title
            and self.key.casefold() == key
            and self.strings == piece.strings
            and (self.subtitle_fragment is None or self.subtitle_fragment.casefold() in subtitle)
            and (self.part is None or self.part.casefold() == (piece.part or "").casefold())
        )


_SOURCE_TUNING_PROFILES = (
    _SourceTuningProfile(
        composer="John Danyel",
        title_fragment="Anne Green, her leaves be green",
        key="Bbm",
        strings=9,
        tuning="d-2e-2f2a-2b-2f3b-3d4g4",
        provenance="Danyel 1606 scordatura; Gerbode sounding pitch",
    ),
    _SourceTuningProfile(
        composer="John Dowland",
        title_fragment="Queen Elizabeth's Galliard",
        key="GM",
        strings=7,
        tuning="d3g3c4f4a4d5g5",
        provenance="Gerbode companion MIDI sounding octave",
    ),
    _SourceTuningProfile(
        composer="Francesco Spinacino",
        title_fragment="Recercar 16",
        key="Dm",
        strings=6,
        tuning="f+2b2e3g+3c+4f+4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Robert White",
        title_fragment="Fantasy 4",
        key="Fm",
        strings=6,
        tuning="a2d3g3b3e4a4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Robert White",
        title_fragment="Fantasy 5",
        key="Cm",
        strings=6,
        tuning="a2d3g3b3e4a4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Robert White",
        title_fragment="Fantasy 6",
        key="Fm",
        strings=6,
        tuning="a2d3g3b3e4a4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Karl Friedrich Abel",
        title_fragment="Sonata in C Major",
        key="CM",
        strings=9,
        tuning="d-2e-2e2f+2b2e3g+3c+4f+4",
        provenance="Gerbode companion MIDI sounding pitch",
        subtitle_fragment="1. Moderato",
        part="archlute",
    ),
    _SourceTuningProfile(
        composer="Guillaume Costeley",
        title_fragment="terre les eaux",
        key="FM",
        strings=7,
        tuning="e2a2d3g3b3e4a4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Gregorio Huet",
        title_fragment="Fantasy",
        key="Dm",
        strings=7,
        tuning="d-2f+2b2e3g+3c+4f+4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Orlando di Lasso",
        title_fragment="La nuict froide et sombre",
        key="Fm",
        strings=7,
        tuning="b1e2a2d3f+3b3e4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="Marin Marais",
        title_fragment="Rondeau 130",
        key="Cm",
        strings=13,
        tuning="f+1g+1b-1b1d-2e-2e2f+2b2e3g+3c+4f+4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
    _SourceTuningProfile(
        composer="John Dowland",
        title_fragment="Unquiet Thoughts",
        key="Gm",
        strings=8,
        tuning="c2b-1f2b-2e-3g3c4f4",
        provenance="Gerbode companion MIDI sounding pitch",
    ),
)

_EXTENDED_BASS_TUNINGS = {
    9: "d2e2f2g2c3f3a3d4g4",
    10: "c2d2e2f2g2c3f3a3d4g4",
    11: "b1c2d2e2f2g2c3f3a3d4g4",
    12: "a1b1c2d2e2f2g2c3f3a3d4g4",
    13: "g1a1b1c2d2e2f2g2c3f3a3d4g4",
    14: "f1g1a1b1c2d2e2f2g2c3f3a3d4g4",
}


def _apply_extended_bass_default(piece: Piece) -> None:
    tuning = _EXTENDED_BASS_TUNINGS.get(piece.strings)
    ensemble = (piece.ensemble or "").casefold()
    explicit_course_count = f"{piece.strings}-course" in ensemble
    extended_instrument = any(label in ensemble for label in ("archlute", "baroque", "theorbo"))
    if tuning and (explicit_course_count or extended_instrument):
        piece.tuning = tuning
        piece.tuning_source = "FT3 ensemble default; diatonic extended basses"


def apply_ft3_source_tuning(piece: Piece) -> None:
    """Supply documented tuning omitted by a recognized FT3 source."""
    if piece.tuning:
        return
    for profile in _SOURCE_TUNING_PROFILES:
        if profile.matches(piece):
            piece.tuning = profile.tuning
            piece.tuning_source = profile.provenance
            return
    _apply_extended_bass_default(piece)
