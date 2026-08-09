"""Source-faithful records kept separate from editorial interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from petrucci.model import Piece


class DiplomaticSignKind(StrEnum):
    """Historical signs currently recoverable from imported FT3 scores."""

    MENSURATION = "mensuration"
    PROPORTION = "proportion"


@dataclass(frozen=True)
class SourceLocation:
    """Stable source order and coordinates independent of any renderer."""

    document_id: str
    source_record_index: int
    bar_index: int
    staff_index: int
    voice_index: int


@dataclass(frozen=True)
class DiplomaticSign:
    """A written source fact, without an imposed rhythmic interpretation."""

    id: str
    kind: DiplomaticSignKind
    location: SourceLocation
    written_value: str


@dataclass(frozen=True)
class MensurationMeaning:
    beats: int
    beat_unit: int


@dataclass(frozen=True)
class EditorialDecision:
    """An interpretation that refers to, but never rewrites, a source sign."""

    source_id: str
    effective_mensuration: MensurationMeaning | None = None
    effective_proportion: Fraction | None = None


@dataclass(frozen=True)
class SourceDocument:
    source_format: str
    signs: tuple[DiplomaticSign, ...]
    decisions: tuple[EditorialDecision, ...]


@dataclass(frozen=True)
class _SignContext:
    document_id: str
    record_index: int
    bar_index: int
    staff_index: int
    voice_index: int

    def location(self) -> SourceLocation:
        return SourceLocation(
            self.document_id,
            self.record_index,
            self.bar_index,
            self.staff_index,
            self.voice_index,
        )

    def key(self, kind: DiplomaticSignKind) -> tuple[int, int, int, DiplomaticSignKind]:
        return self.bar_index, self.staff_index, self.voice_index, kind


def _mensuration_meaning(value: str) -> MensurationMeaning | None:
    normalized = value.strip().lower()
    conventional = {"c": (4, 4), "c|": (2, 2), "o": (3, 4)}
    if normalized in conventional:
        beats, unit = conventional[normalized]
        return MensurationMeaning(beats, unit)
    if "/" not in normalized:
        return None
    beats_text, unit_text = normalized.split("/", 1)
    if not beats_text.isdigit() or not unit_text.isdigit():
        return None
    beats = int(beats_text)
    unit = int(unit_text)
    if beats <= 0 or unit <= 0:
        return None
    return MensurationMeaning(beats, unit)


def _source_sign(context: _SignContext, kind: DiplomaticSignKind, written_value: str) -> DiplomaticSign:
    source_id = f"{context.document_id}:{context.staff_index}:{context.voice_index}:{context.bar_index}:{kind.value}"
    return DiplomaticSign(source_id, kind, context.location(), written_value)


def _append_mensuration(
    signs: list[DiplomaticSign],
    decisions: list[EditorialDecision],
    seen: set[tuple[int, int, int, DiplomaticSignKind]],
    context: _SignContext,
    written_value: str,
) -> None:
    key = context.key(DiplomaticSignKind.MENSURATION)
    if key in seen:
        return
    seen.add(key)
    sign = _source_sign(context, DiplomaticSignKind.MENSURATION, written_value)
    signs.append(sign)
    decisions.append(EditorialDecision(sign.id, effective_mensuration=_mensuration_meaning(written_value)))


def _append_proportion(
    signs: list[DiplomaticSign],
    decisions: list[EditorialDecision],
    seen: set[tuple[int, int, int, DiplomaticSignKind]],
    context: _SignContext,
    proportion: tuple[int, int],
) -> None:
    key = context.key(DiplomaticSignKind.PROPORTION)
    if key in seen:
        return
    seen.add(key)
    numerator, denominator = proportion
    sign = _source_sign(context, DiplomaticSignKind.PROPORTION, f"{numerator}:{denominator}")
    signs.append(sign)
    meaning = Fraction(numerator, denominator) if numerator > 0 and denominator > 0 else None
    decisions.append(EditorialDecision(sign.id, effective_proportion=meaning))


def build_source_document(piece: Piece, *, document_id: str = "score") -> SourceDocument:
    """Project supported FT3 signs into separate diplomatic and interpretive layers."""

    imported = piece.imported_score
    if imported is None:
        return SourceDocument("native", (), ())
    signs: list[DiplomaticSign] = []
    decisions: list[EditorialDecision] = []
    seen: set[tuple[int, int, int, DiplomaticSignKind]] = set()
    for record_index, record in enumerate(imported.source_records):
        if not 0 <= record.source_bar_index < len(piece.bars):
            continue
        bar = piece.bars[record.source_bar_index]
        context = _SignContext(
            document_id,
            record_index,
            record.source_bar_index,
            record.source_staff_index,
            record.source_voice_index,
        )
        if bar.time_sig:
            _append_mensuration(signs, decisions, seen, context, bar.time_sig)
        if bar.proportion:
            _append_proportion(signs, decisions, seen, context, bar.proportion)
    return SourceDocument(imported.source_format, tuple(signs), tuple(decisions))
