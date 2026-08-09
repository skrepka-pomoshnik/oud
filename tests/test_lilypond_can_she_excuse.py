from fractions import Fraction

from oud.exports.lilypond import lilypond_text
from oud.exports.lilypond.registration import build_lilypond_registration
from oud.importers.ft3 import load_ft3
from oud.settings import DEFAULT_SETTINGS

CAN_SHE_EXCUSE = "tests/fixtures/ft3/corpus/can_she_excuse.ft3"


def test_can_she_excuse_decodes_registered_two_verse_rows() -> None:
    piece = load_ft3(CAN_SHE_EXCUSE)

    assert piece.bars[6].lyrics == ["she proves un-", "she holds from"]
    assert piece.bars[7].lyrics == ["kind", "me"]
    assert piece.bars[9].lyrics == ["fires which van-", "high, so high"]
    assert piece.bars[14].lyrics == ["no fruit I", "can grant- ed"]


def test_can_she_excuse_uses_five_bar_gerbode_registration() -> None:
    piece = load_ft3(CAN_SHE_EXCUSE)
    registration = build_lilypond_registration(piece, dict(DEFAULT_SETTINGS))

    assert registration.system_break_after == frozenset({4, 9, 14, 19, 24, 29, 34})
    assert registration.page_break_after == frozenset({19})
    assert registration.boxed_bar_number_before == frozenset({4, 9, 14, 19, 24, 29, 34, 39})
    assert registration.measure_durations == (Fraction(3, 4),) * 40


def test_can_she_excuse_lilypond_has_registered_lute_publication_policy() -> None:
    piece = load_ft3(CAN_SHE_EXCUSE)
    text = lilypond_text(piece, {}, {}, 12, settings=dict(DEFAULT_SETTINGS))

    assert '#(set-default-paper-size "letter")' in text
    assert "Times New Roman" not in text
    assert 'instrumentName = "alto"' not in text
    assert "piece = " not in text
    assert r"\scaleDurations 2/1" in text
    assert r"\set TabStaff.additionalBassStrings" in text
    assert r"\autoBeamOff" in text
    assert r'\mark \markup { \box "5" }' in text
    assert "  d'4\n  a'4\n  d''4" in text
