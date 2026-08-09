from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from oud.importers.ft3 import load_ft3
from petrucci import PieceAdapterError, notation_score_from_piece
from petrucci.core.model import Piece
from scripts.corpus.fetch import fetch_manifest, load_manifest, manifest_paths
from scripts.corpus.audit import audit_piece
from scripts.corpus import fetch as fetch_ft3_corpus

RANDOM_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-random-75.json")
EXPANDED_RANDOM_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-random-75-v2.json")
RANDOM_50_V3_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-random-50-v3.json")
RANDOM_63_V4_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-random-63-v4.json")
RANDOM_37_V5_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-random-37-v5.json")
FIXED_115_V6_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-fixed-115-v6.json")
FIXED_85_V7_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-fixed-85-v7.json")
FIXED_14_V8_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-fixed-14-v8.json")
NOTE_INPUT_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-note-input-100.json")
REGRESSION_MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-regression.json")
FIXED_RANDOM_MANIFESTS = (
    RANDOM_MANIFEST,
    EXPANDED_RANDOM_MANIFEST,
    RANDOM_50_V3_MANIFEST,
    RANDOM_63_V4_MANIFEST,
    RANDOM_37_V5_MANIFEST,
    FIXED_115_V6_MANIFEST,
    FIXED_85_V7_MANIFEST,
    FIXED_14_V8_MANIFEST,
)


@pytest.fixture(scope="module")
def fixed_pieces() -> dict[Path, Piece]:
    paths = [path for manifest_path in FIXED_RANDOM_MANIFESTS for path in manifest_paths(load_manifest(manifest_path))]
    missing = [_relative(path) for path in paths if not path.is_file()]
    if missing:
        pytest.skip("fetch all fixed random corpora before running external corpus tests")
    return {path: load_ft3(str(path)) for path in paths}


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(Path.cwd().resolve()))


def _write_manifest(tmp_path: Path, *, url: str, digest: str, target: str = "one.ft3") -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "root": "cache",
                "files": [{"path": target, "url": url, "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_random_75_manifest_is_a_fixed_one_time_selection() -> None:
    raw = json.loads(RANDOM_MANIFEST.read_text(encoding="utf-8"))
    manifest = load_manifest(RANDOM_MANIFEST)

    assert raw["selection"]["selected"] == 75
    assert raw["selection"]["seed"] == 20260712
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(manifest.files) == 75
    assert len({entry.path for entry in manifest.files}) == 75
    assert len({entry.url for entry in manifest.files}) == 75
    assert len({entry.sha256 for entry in manifest.files}) == 75
    corpus_root = (Path.cwd() / "tests/fixtures/ft3/corpus").resolve()
    assert all(path.is_relative_to(corpus_root) for path in manifest_paths(manifest))


def test_expanded_random_75_manifest_is_new_composer_stratified_selection() -> None:
    raw = json.loads(EXPANDED_RANDOM_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(EXPANDED_RANDOM_MANIFEST)
    original = load_manifest(RANDOM_MANIFEST)

    assert raw["selection"]["selected"] == 75
    assert raw["selection"]["unique_composers"] == 75
    assert raw["selection"]["seed"] == 20260717
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(expanded.files) == 75
    assert len({entry["composer"] for entry in raw["files"]}) == 75
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in original.files)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in original.files)


def test_random_50_v3_manifest_is_new_composer_stratified_selection() -> None:
    raw = json.loads(RANDOM_50_V3_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(RANDOM_50_V3_MANIFEST)
    previous = [entry for path in FIXED_RANDOM_MANIFESTS[:2] for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 50
    assert raw["selection"]["unique_composers"] == 50
    assert raw["selection"]["seed"] == 20260719
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(expanded.files) == 50
    assert len({entry["composer"] for entry in raw["files"]}) == 50
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)


def test_random_63_v4_manifest_is_a_new_fixed_composer_stratified_selection() -> None:
    raw = json.loads(RANDOM_63_V4_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(RANDOM_63_V4_MANIFEST)
    previous = [entry for path in FIXED_RANDOM_MANIFESTS[:3] for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 63
    assert raw["selection"]["unique_composers"] == 63
    assert raw["selection"]["seed"] == 2026071963
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(expanded.files) == 63
    assert len({entry["composer"] for entry in raw["files"]}) == 63
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)


def test_random_37_v5_manifest_expands_compatibility_corpus_to_300() -> None:
    raw = json.loads(RANDOM_37_V5_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(RANDOM_37_V5_MANIFEST)
    previous_paths = (REGRESSION_MANIFEST, *FIXED_RANDOM_MANIFESTS[:4], NOTE_INPUT_MANIFEST)
    previous = [entry for path in previous_paths for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 37
    assert raw["selection"]["seed"] == 20260809
    assert raw["selection"]["unique_composers"] == 20
    assert raw["selection"]["composer_index_size"] == 195
    assert raw["selection"]["candidate_count"] == 79
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(expanded.files) == 37
    assert sum(len(load_manifest(path).files) for path in FIXED_RANDOM_MANIFESTS[:5]) == 300
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)
    assert all(
        {"format", "bars", "strings", "style", "tab_chords", "staff_kinds", "notation_events", "lyrics"} <= entry.keys()
        for entry in raw["files"]
    )


def test_fixed_115_v6_expands_compatibility_corpus_to_415() -> None:
    raw = json.loads(FIXED_115_V6_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(FIXED_115_V6_MANIFEST)
    previous = [entry for path in FIXED_RANDOM_MANIFESTS[:5] for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 115
    assert raw["selection"]["candidate_count"] == 115
    assert "checksum-ordered" in raw["selection"]["method"]
    assert len(expanded.files) == 115
    assert sum(len(load_manifest(path).files) for path in FIXED_RANDOM_MANIFESTS[:6]) == 415
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)
    assert all(
        {"format", "bars", "strings", "style", "tab_chords", "staff_kinds", "notation_events", "lyrics"} <= entry.keys()
        for entry in raw["files"]
    )


def test_fixed_85_v7_expands_compatibility_corpus_to_500() -> None:
    raw = json.loads(FIXED_85_V7_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(FIXED_85_V7_MANIFEST)
    previous = [entry for path in FIXED_RANDOM_MANIFESTS[:6] for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 85
    assert raw["selection"]["candidate_count"] == 87
    assert raw["selection"]["composer_index_size"] == 195
    assert raw["selection"]["unique_composers"] == 10
    assert "SHA-256 URL-ordered" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(expanded.files) == 85
    assert sum(len(load_manifest(path).files) for path in FIXED_RANDOM_MANIFESTS[:7]) == 500
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)
    assert all(
        {"format", "bars", "strings", "style", "tab_chords", "staff_kinds", "notation_events", "lyrics"} <= entry.keys()
        for entry in raw["files"]
    )


def test_fixed_14_v8_closes_every_direct_index_semantic_variant() -> None:
    raw = json.loads(FIXED_14_V8_MANIFEST.read_text(encoding="utf-8"))
    expanded = load_manifest(FIXED_14_V8_MANIFEST)
    previous = [entry for path in FIXED_RANDOM_MANIFESTS[:-1] for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 14
    assert raw["selection"]["candidate_count"] == 14
    assert "previously unresolved" in raw["selection"]["method"]
    assert len(expanded.files) == 14
    assert sum(len(load_manifest(path).files) for path in FIXED_RANDOM_MANIFESTS) == 514
    assert {entry.url for entry in expanded.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in expanded.files}.isdisjoint(entry.sha256 for entry in previous)


@pytest.mark.parametrize(
    "manifest_path",
    (RANDOM_37_V5_MANIFEST, FIXED_115_V6_MANIFEST, FIXED_85_V7_MANIFEST, FIXED_14_V8_MANIFEST),
)
def test_expansion_metadata_matches_verified_payloads(
    manifest_path: Path,
    fixed_pieces: dict[Path, Piece],
) -> None:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = load_manifest(manifest_path)
    for expected, path in zip(raw["files"], manifest_paths(manifest), strict=True):
        piece = fixed_pieces[path]
        staff_kinds = (
            Counter(staff.kind for staff in piece.imported_score.staffs) if piece.imported_score else Counter()
        )
        try:
            score = notation_score_from_piece(piece)
        except PieceAdapterError:
            score = None
        notation_events = (
            sum(len(measure.events) for staff in score.staffs for measure in staff.measures) if score else 0
        )
        lyrics = sum(len(staff.lyrics) for staff in score.staffs) if score else 0

        assert expected["format"] == "ft3"
        assert expected["bars"] == len(piece.bars)
        assert expected["strings"] == piece.strings
        assert expected["style"] == piece.style
        assert expected["tab_chords"] == sum(len(bar.chords) for bar in piece.bars)
        assert expected["staff_kinds"] == dict(sorted(staff_kinds.items()))
        assert expected["notation_events"] == notation_events
        assert expected["lyrics"] == lyrics


def test_v7_pdf_confirmed_postfix_ornaments_are_fully_decoded(fixed_pieces: dict[Path, Piece]) -> None:
    paths = manifest_paths(load_manifest(FIXED_85_V7_MANIFEST))
    notes = [note for path in paths for bar in fixed_pieces[path].bars for chord in bar.chords for note in chord.notes]
    plus_notes = [note for note in notes if note.ft3_extras and note.ft3_extras & 0xFE00 == 0x0A00]
    star_notes = [note for note in notes if note.ft3_extras and note.ft3_extras & 0xFE00 == 0x4000]

    assert plus_notes
    assert len(star_notes) == 9
    assert all(note.right_ornament == "+" and note.ft3_extra_residual is None for note in plus_notes)
    assert all(note.right_ornament == "*" and note.ft3_extra_residual is None for note in star_notes)


def test_ft3_payload_suffixes_are_ignored() -> None:
    patterns = set(Path(".gitignore").read_text(encoding="utf-8").splitlines())
    assert {"*.ft3", "*.ft3.gz", "*.ft3.txt"} <= patterns


@pytest.mark.parametrize("manifest_path", FIXED_RANDOM_MANIFESTS)
def test_fixed_random_payloads_load_without_semantic_audit_failures(
    manifest_path: Path,
    fixed_pieces: dict[Path, Piece],
) -> None:
    manifest = load_manifest(manifest_path)
    paths = manifest_paths(manifest)
    missing = [_relative(path) for path in paths if not path.is_file()]
    if missing:
        pytest.skip(f"fetch {manifest_path} before running external corpus tests")

    bad_hashes = [
        _relative(path)
        for entry, path in zip(manifest.files, paths, strict=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.sha256
    ]
    assert bad_hashes == []

    pieces = {path: fixed_pieces[path] for path in paths}
    assert len(pieces) == len(manifest.files)
    assert all(piece.bars for piece in pieces.values())
    assert {_relative(path) for path, piece in pieces.items() if piece.import_warnings} == set()

    unresolved = set()
    for path, piece in pieces.items():
        report = audit_piece(piece, path=path)
        if any(
            report[key]
            for key in ("note_extra_residuals", "vocal_flag_residuals", "unknown_source_records", "warnings")
        ):
            unresolved.add(_relative(path))
    assert unresolved == set()


def test_random_50_v3_preserves_new_ornaments_layout_and_headings(fixed_pieces: dict[Path, Piece]) -> None:
    paths = manifest_paths(load_manifest(RANDOM_50_V3_MANIFEST))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        pytest.skip(f"fetch {RANDOM_50_V3_MANIFEST} before running external corpus tests")
    by_name = {path.name: fixed_pieces[path] for path in paths}

    tombeau_notes = [
        note for bar in by_name["tombeau_sur_logy.ft3"].bars for chord in bar.chords for note in chord.notes
    ]
    assert sum(note.left_ornament == "parenthesis" for note in tombeau_notes) == 3
    assert sum(note.right_ornament == "under-hook" for note in tombeau_notes) == 9

    hierusalem = by_name["hierusalem.ft3"]
    assert hierusalem.imported_score is not None
    assert [record.kind for record in hierusalem.imported_score.source_records] == ["layout"]

    scales = by_name["fingering_easy_scales.ft3"]
    assert scales.imported_score is not None
    assert [record.kind for record in scales.imported_score.source_records] == ["text"] * 3
    headings = [
        text
        for staff in scales.imported_score.staffs
        if staff.kind == "comment"
        for bar in staff.bars
        for text in bar.editorial_text
    ]
    assert headings == ["C (natural hexachord)", "G (hard hexachord)", "F (soft hexachord)"]


def test_expanded_corpus_preserves_newly_decoded_score_semantics(fixed_pieces: dict[Path, Piece]) -> None:
    paths = manifest_paths(load_manifest(EXPANDED_RANDOM_MANIFEST))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        pytest.skip(f"fetch {EXPANDED_RANDOM_MANIFEST} before running external corpus tests")

    by_name = {path.name: fixed_pieces[path] for path in paths}
    berchem = by_name["13_o_sio_potesi_donna.ft3"]
    assert len(berchem.bars) == 59
    assert berchem.imported_score is not None
    berchem_notes = [staff for staff in berchem.imported_score.staffs if staff.kind == "note"]
    assert [(staff.label, len(staff.bars)) for staff in berchem_notes] == [("alto", 59), ("bass", 59)]
    assert all(
        event.accidental_flags is not None
        for staff in berchem_notes
        for bar in staff.bars
        for event in bar.melody_events
    )

    sandrin_events = [event for bar in by_name["douce_memoire_song_sandrin.ft3"].bars for event in bar.melody_events]
    assert sum(event.courtesy_accidental for event in sandrin_events) == 15

    lully_events = [event for bar in by_name["recit_de_la_beaute_double.ft3"].bars for event in bar.melody_events]
    assert sum(event.editorial_brackets for event in lully_events) == 2
    assert sum(event.tie_from_previous for event in lully_events) == 1

    mozart_notes = [
        note
        for bar in by_name["mozart_variations.ft3"].bars
        for chord in bar.chords
        for note in chord.notes
        if note.ft3_extras == 0x3C00
    ]
    assert [(note.string, note.fret, note.ft3_extra_residual) for note in mozart_notes] == [(9, 0, None)]
    mozart = by_name["mozart_variations.ft3"]
    assert mozart.imported_score is not None
    assert all(staff.kind != "note" for staff in mozart.imported_score.staffs)
    assert any(
        row.kind == "control" and row.text.strip() == "'_6"
        for staff in mozart.imported_score.staffs
        for bar in staff.bars
        for row in bar.text_rows
    )

    gesualdo = by_name["gesualdo_gagliarda_4.ft3"]
    assert gesualdo.imported_score is not None
    gesualdo_notes = [staff for staff in gesualdo.imported_score.staffs if staff.kind == "note"]
    assert [staff.bars[0].time_sig for staff in gesualdo_notes] == ["3/2"] * 4
    canonical = notation_score_from_piece(gesualdo)
    assert len(canonical.staffs) == 4
    assert [
        (staff.measures[0].time_signature.beats, staff.measures[0].time_signature.beat_unit)
        for staff in canonical.staffs
        if staff.measures[0].time_signature is not None
    ] == [(3, 2)] * 4

    mace_notes = [
        note
        for bar in by_name["praeludium_02.ft3"].bars
        for chord in bar.chords
        for note in chord.notes
        if note.ft3_extras == 0x1600
    ]
    assert [(note.left_ornament, note.ft3_extra_residual) for note in mace_notes] == [("'", None)]


def test_fixed_notation_subset_has_explicit_strict_adaptation_outcomes(
    fixed_pieces: dict[Path, Piece],
) -> None:
    notation = []
    rejected: dict[str, str] = {}
    for path, piece in fixed_pieces.items():
        if piece.imported_score is None or not any(staff.kind == "note" for staff in piece.imported_score.staffs):
            continue
        try:
            notation.append((path, notation_score_from_piece(piece)))
        except PieceAdapterError as exc:
            rejected[_relative(path)] = str(exc)

    assert len(notation) == 49
    assert rejected == {
        "tests/fixtures/ft3/corpus/note-input-100/028/disperate_speranze_S.ft3": (
            "tie target 'piece:staff:1:bar:12:event:2:0' has no preceding event with a shared pitch"
        ),
        "tests/fixtures/ft3/corpus/note-input-100/045/come_raggio_del_sol_D.ft3": (
            "tie target 'piece:staff:0:bar:33:event:2:0' has no preceding event with a shared pitch"
        ),
        "tests/fixtures/ft3/corpus/random-50-v3/041/sonata_CM_01_moderato.ft3": (
            "event group 'piece:staff:0:bar:0:event:0:0' has inconsistent durations"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/001/sonata_CM_02_minuetto.ft3": (
            "event group 'piece:staff:0:bar:0:event:0:0' has inconsistent durations"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/012/disperate_speranze_4.ft3": (
            "tie target 'piece:staff:0:bar:7:event:3:0' has no preceding event with a shared pitch"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/037/courant_duet.ft3": (
            "event group 'piece:staff:0:bar:0:event:0:0' has inconsistent durations"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/040/come_raggio_del_sol_G.ft3": (
            "event group 'piece:staff:0:bar:0:event:0:0' has inconsistent durations"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/043/rondeau_130.ft3": (
            "tie target 'piece:staff:0:bar:26:event:4:0' has no preceding event with a shared pitch"
        ),
        "tests/fixtures/ft3/corpus/random-63-v4/050/passacaille_B.ft3": (
            "tie target 'piece:staff:0:bar:0:event:0:0' has no preceding event with a shared pitch"
        ),
    }
    assert all(score.staffs for _path, score in notation)
    assert all(line.text.strip() for _path, score in notation for staff in score.staffs for line in staff.lyric_lines)


def test_random_corpus_demotes_ascii_control_fragments_from_note_staffs(fixed_pieces: dict[Path, Piece]) -> None:
    paths = manifest_paths(load_manifest(RANDOM_MANIFEST))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        pytest.skip(f"fetch {RANDOM_MANIFEST} before running external corpus tests")
    by_name = {path.name: fixed_pieces[path] for path in paths}

    sonata = by_name["sonata_CM_01_moderato_T.ft3"]
    assert sonata.imported_score is not None
    assert all(staff.kind != "note" for staff in sonata.imported_score.staffs)
    assert any(
        row.kind == "control" and row.text.strip() == "4"
        for staff in sonata.imported_score.staffs
        for bar in staff.bars
        for row in bar.text_rows
    )

    semper = by_name["09_semper_dowland_semper_dolens.ft3"]
    assert semper.imported_score is not None
    assert all(staff.kind != "note" for staff in semper.imported_score.staffs)


def test_couperin_duet_maps_two_note_voices_to_one_77_bar_staff(fixed_pieces: dict[Path, Piece]) -> None:
    path = Path("tests/fixtures/ft3/corpus/random-75/054/la_couperin_duet.ft3")
    if not path.is_file():
        pytest.skip("fetch tests/fixtures/ft3/manifests/ft3-random-75.json before running external corpus tests")

    piece = fixed_pieces[path.resolve()]
    assert len(piece.bars) == 77
    assert piece.import_warnings == []
    assert piece.imported_score is not None
    note_staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    assert [(staff.label, len(staff.bars)) for staff in note_staffs] == [("6-course bass viol 1", 77)]
    assert {event.voice for bar in note_staffs[0].bars for event in bar.melody_events} == {0, 1}
    assert {record.source_voice_index for record in piece.imported_score.source_records} == {0, 1}


def test_fetch_manifest_downloads_once_and_then_only_verifies(tmp_path: Path, monkeypatch) -> None:
    payload = b"external fixture"
    digest = hashlib.sha256(payload).hexdigest()
    path = _write_manifest(
        tmp_path,
        url="https://browse.lutemusic.org/example.ft3",
        digest=digest,
    )
    calls: list[str] = []

    def fake_download(url: str) -> bytes:
        calls.append(url)
        return payload

    monkeypatch.setattr(fetch_ft3_corpus, "_download", fake_download)
    manifest = load_manifest(path)

    assert fetch_manifest(manifest, repo_root=tmp_path) == fetch_ft3_corpus.FetchResult(fetched=1, present=0)
    assert fetch_manifest(manifest, repo_root=tmp_path) == fetch_ft3_corpus.FetchResult(fetched=0, present=1)
    assert calls == ["https://browse.lutemusic.org/example.ft3"]
    assert (tmp_path / "cache/one.ft3").read_bytes() == payload


def test_fetch_manifest_refuses_existing_mismatched_payload(tmp_path: Path, monkeypatch) -> None:
    payload = b"expected"
    path = _write_manifest(
        tmp_path,
        url="https://browse.lutemusic.org/example.ft3",
        digest=hashlib.sha256(payload).hexdigest(),
    )
    target = tmp_path / "cache/one.ft3"
    target.parent.mkdir()
    target.write_bytes(b"different")
    monkeypatch.setattr(fetch_ft3_corpus, "_download", lambda _url: payload)

    with pytest.raises(fetch_ft3_corpus.ManifestError, match="refusing to replace"):
        fetch_manifest(load_manifest(path), repo_root=tmp_path)
    assert target.read_bytes() == b"different"


@pytest.mark.parametrize(
    ("url", "target"),
    [
        ("http://browse.lutemusic.org/one.ft3", "one.ft3"),
        ("https://example.com/one.ft3", "one.ft3"),
        ("https://browse.lutemusic.org/one.ft3", "../one.ft3"),
    ],
)
def test_manifest_rejects_unsafe_sources_and_destinations(tmp_path: Path, url: str, target: str) -> None:
    path = _write_manifest(tmp_path, url=url, digest="0" * 64, target=target)
    with pytest.raises(fetch_ft3_corpus.ManifestError):
        load_manifest(path)
