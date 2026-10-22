from pathlib import Path

import pytest

from oud.importers.ft3 import load_ft3
from oud.importers.ft3.score import _BodyEntry, _ensemble_staff_labels, _parallel_note_tab_plan
from petrucci import notation_score_from_piece
from petrucci.core.model import Bar


def _write_parallel_fixture(
    tmp_path: Path,
    *,
    tab_first: bool,
    lanes: int,
    ensemble: str = "6-course lute, bass",
    ensemble_field: str = "ensemble",
) -> Path:
    # Authored miniature using the same structured-note framing as the vocal
    # fragment regression, with three quarter notes in each 3/4 measure.
    header = bytearray(32)
    header[0] = 0x06
    header[8:10] = b"\x04\x03"
    notation = bytes(header) + bytes.fromhex("010000000001330500000000013308000000000400")
    tab = bytes(32) + bytes.fromhex("020000000261000000")
    note_records = [notation] * (2 * lanes)
    tab_records = [tab, tab]
    records = tab_records + note_records if tab_first else note_records + tab_records
    path = tmp_path / f"parallel-{tab_first}-{lanes}.ft3"
    metadata = b"CPiece{\\rtf1 Test}\n" + f"{ensemble_field}:{ensemble}\n".encode("ascii")
    path.write_bytes(metadata + b"CBar" + b"\x03\x80".join(records))
    return path


@pytest.mark.parametrize("tab_first", [False, True])
@pytest.mark.parametrize("lanes", [1, 2])
@pytest.mark.parametrize("ensemble_field", ["ensemble", "instrumentation"])
def test_parallel_serialization_preserves_measures_and_voices(
    tmp_path: Path,
    tab_first: bool,
    lanes: int,
    ensemble_field: str,
) -> None:
    path = _write_parallel_fixture(tmp_path, tab_first=tab_first, lanes=lanes, ensemble_field=ensemble_field)
    piece = load_ft3(str(path))

    assert len(piece.bars) == 2
    assert piece.imported_score is not None
    staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    assert len(staffs) == 1
    assert staffs[0].label == "bass"
    assert [bar.source_bar_index for bar in staffs[0].bars] == [0, 1]
    assert [len(bar.melody_events) for bar in staffs[0].bars] == [3 * lanes] * 2
    for bar in staffs[0].bars:
        assert {event.voice for event in bar.melody_events} == set(range(lanes))
        for voice in range(lanes):
            events = [event for event in bar.melody_events if event.voice == voice]
            assert [event.onset_index for event in events] == [0, 1, 2]
            assert [event.text for event in events] == ["d", "a", "d'"]
            assert [event.note_type for event in events] == [4, 4, 4]
    score = notation_score_from_piece(piece)
    assert len(score.staffs) == 1
    assert len(score.staffs[0].measures) == 2


@pytest.mark.parametrize("tab_first", [False, True])
@pytest.mark.parametrize("ensemble_field", ["ensemble", "instrumentation"])
def test_parallel_serialization_preserves_distinct_staffs(
    tmp_path: Path,
    tab_first: bool,
    ensemble_field: str,
) -> None:
    path = _write_parallel_fixture(
        tmp_path,
        tab_first=tab_first,
        lanes=2,
        ensemble="6-course lute, alto, soprano",
        ensemble_field=ensemble_field,
    )
    piece = load_ft3(str(path))

    assert piece.imported_score is not None
    staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    assert [staff.label for staff in staffs] == ["soprano", "alto"]
    assert [[bar.source_bar_index for bar in staff.bars] for staff in staffs] == [[0, 1], [0, 1]]
    assert all(len(bar.melody_events) == 3 for staff in staffs for bar in staff.bars)
    score = notation_score_from_piece(piece)
    assert len(score.staffs) == 2
    assert [len(staff.measures) for staff in score.staffs] == [2, 2]


@pytest.mark.parametrize(
    ("annotations", "labels"),
    [
        ({"instrumentation": "6-course, bass"}, ["6-course", "bass"]),
        ({"ensemble": "alto", "instrumentation": "bass"}, ["alto"]),
        ({}, []),
    ],
)
def test_ensemble_annotation_alias_is_explicit(annotations: dict[str, str], labels: list[str]) -> None:
    assert _ensemble_staff_labels(annotations) == labels


@pytest.mark.parametrize(
    ("kinds", "ensemble"),
    [
        ([], "bass"),
        (["tab", "tab"], "bass"),
        (["raw", "raw"], "bass"),
        (["raw", "tab", "raw"], "bass"),
        (["tab", "raw", "tab"], "bass"),
        (["tab", "tab", "raw", "raw", "raw"], "bass"),
        (["tab", "raw"], "6-course lute"),
        (["tab", "raw", "raw", "raw"], "alto, soprano"),
    ],
)
def test_parallel_mapping_does_not_guess_incomplete_or_interleaved_lanes(kinds: list[str], ensemble: str) -> None:
    entries = [_BodyEntry(kind, b"", Bar(), "note-staff-raw" if kind == "raw" else None) for kind in kinds]
    assert _parallel_note_tab_plan(entries, {"ensemble": ensemble}) is None


@pytest.mark.parametrize("tab_first", [False, True])
def test_parallel_padding_keeps_its_lane_and_measure(tab_first: bool) -> None:
    tabs = [_BodyEntry("tab", b"tab", Bar(), None)] * 2
    note = _BodyEntry("raw", b"note", Bar(), "note-staff-raw")
    padding = _BodyEntry("raw", b"layout", Bar(), "layout-raw")
    notation = [note, padding, note, note, padding, note]
    entries = tabs + notation if tab_first else notation + tabs

    plan = _parallel_note_tab_plan(entries, {"ensemble": "6-course lute, bass"})
    assert plan is not None
    tab_entries, mapped, labels = plan
    assert tab_entries == tabs
    assert labels == ["bass"]
    assert [(entry.bar_index, entry.staff_index, entry.voice_index) for entry in mapped if entry.entry is padding] == [
        (0, 0, 0),
        (0, 0, 1),
    ]
    assert [(entry.bar_index, entry.staff_index, entry.voice_index) for entry in mapped if entry.entry is note] == [
        (0, 0, 0),
        (1, 0, 0),
        (0, 0, 1),
        (1, 0, 1),
    ]


@pytest.mark.ft3_corpus
@pytest.mark.parametrize(
    ("relative_path", "bar_count"),
    [
        ("Dowland/13_dowlands_adieu_TB.ft3", 21),
        ("Holborne/almain_BT.ft3", 14),
        ("Holborne/ecce_quam_bonum_BT.ft3", 24),
    ],
)
def test_cached_tab_first_scores_keep_notation_in_each_measure(relative_path: str, bar_count: int) -> None:
    path = Path("downloads/gerbode/ft3") / relative_path
    if not path.is_file():
        pytest.skip("needs the locally preserved Gerbode score; no network fetch")
    piece = load_ft3(str(path))

    assert len(piece.bars) == bar_count
    assert piece.imported_score is not None
    staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    assert len(staffs) == 1
    assert [bar.source_bar_index for bar in staffs[0].bars] == list(range(bar_count))
    assert all(bar.melody_events for bar in staffs[0].bars)
    score = notation_score_from_piece(piece)
    assert len(score.staffs) == 1
    assert len(score.staffs[0].measures) == bar_count
