from oud.core.tab_assign_policy import (
    AssignmentPolicy,
    assign_chord_pitches,
)

LUTE_6 = [67, 62, 57, 53, 48, 43]  # high -> low (string 1..6)


def test_assign_chord_pitches_basic_unique_strings() -> None:
    result = assign_chord_pitches([67, 64, 60], LUTE_6)
    assert result.ok is True
    assert len({n.string for n in result.notes}) == 3
    assert [n.pitch for n in result.notes] == [67, 64, 60]
    assert all(n.fret >= 0 for n in result.notes)


def test_assign_chord_pitches_respects_minimum_fret() -> None:
    policy = AssignmentPolicy(minimum_fret=1)
    result = assign_chord_pitches([67], LUTE_6, policy=policy)
    assert result.ok is True
    assert result.notes[0].string == 2
    assert result.notes[0].fret == 5


def test_assign_chord_pitches_restrain_open_strings_prefers_fretted_option() -> None:
    loose = assign_chord_pitches([67], LUTE_6, policy=AssignmentPolicy(restrain_open_strings=False))
    tight = assign_chord_pitches([67], LUTE_6, policy=AssignmentPolicy(restrain_open_strings=True))
    assert loose.ok and tight.ok
    assert loose.notes[0].fret == 0
    assert tight.notes[0].fret > 0


def test_assign_chord_pitches_forced_string() -> None:
    result = assign_chord_pitches([64], LUTE_6, forced_strings={0: 3})
    assert result.ok is True
    assert result.notes[0].string == 3
    assert result.notes[0].fret == 7


def test_assign_chord_pitches_forced_string_out_of_range_diagnostic() -> None:
    result = assign_chord_pitches([64], LUTE_6, forced_strings={0: 9})
    assert result.ok is False
    assert any(d.code == "forced_string_out_of_range" for d in result.diagnostics)


def test_assign_chord_pitches_forced_string_impossible_diagnostic() -> None:
    # Pitch below forced string open pitch -> negative fret, impossible.
    result = assign_chord_pitches([40], LUTE_6, forced_strings={0: 1})
    assert result.ok is False
    assert any(d.code == "forced_string_impossible" for d in result.diagnostics)


def test_assign_chord_pitches_max_stretch_constraint() -> None:
    # Without stretch limit this fits.
    ok = assign_chord_pitches([67, 64, 60], LUTE_6, policy=AssignmentPolicy(minimum_fret=1))
    assert ok.ok is True
    constrained = assign_chord_pitches(
        [67, 64, 60],
        LUTE_6,
        policy=AssignmentPolicy(minimum_fret=1, max_stretch=1),
    )
    assert constrained.ok is False
    assert any(d.code == "max_stretch_exceeded" for d in constrained.diagnostics)


def test_assign_chord_pitches_duplicate_pitchs_use_different_strings() -> None:
    result = assign_chord_pitches([67, 67], LUTE_6)
    assert result.ok is True
    assert result.notes[0].string != result.notes[1].string
    assert sorted(n.fret for n in result.notes) == [0, 5]
