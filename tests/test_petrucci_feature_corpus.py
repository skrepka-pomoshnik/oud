from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from oud.exports.export_tab import export_tab
from oud.exports.lilypond import export_lilypond
from oud.exports.midi import export_midi
from oud.importers.ft3 import load_ft3
from oud.importers.tab import load_tab
from petrucci import (
    EventKind,
    NotationScore,
    Piece,
    PieceAdapterError,
    SpanKind,
    TypesetOptions,
    notation_score_from_piece,
    typeset_piece,
)
from petrucci.core.music.tuning import tuning_preset
from scripts.corpus.fetch import load_manifest, manifest_paths

MANIFEST = Path("tests/fixtures/ft3/manifests/petrucci-feature-excerpts.json")


def _source_key(value: str | Path) -> str:
    rendered = Path(value).as_posix()
    relative = rendered.partition("tests/fixtures/ft3/corpus/")[2]
    return relative or rendered


def _source_paths(manifest_names: list[str]) -> dict[tuple[str, str], Path]:
    paths: dict[tuple[str, str], Path] = {}
    for manifest_name in manifest_names:
        manifest = load_manifest(Path(manifest_name))
        paths.update(
            ((manifest_name, _source_key(entry.path)), path)
            for entry, path in zip(manifest.files, manifest_paths(manifest), strict=True)
        )
    return paths


def _digest(value: bytes | str) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _score(piece: Piece) -> NotationScore | None:
    try:
        return notation_score_from_piece(piece)
    except PieceAdapterError:
        return None


def _score_events(score: NotationScore | None) -> tuple[Any, ...]:
    if score is None:
        return ()
    return tuple(event for staff in score.staffs for measure in staff.measures for event in measure.events)


def _features(piece: Piece) -> list[str]:
    score = _score(piece)
    staffs = score.staffs if score else ()
    events = _score_events(score)
    chords = tuple(chord for bar in piece.bars for chord in bar.chords)
    notes = tuple(note for chord in chords for note in chord.notes)
    flags = {
        "bass_courses": any(note.string > 6 for note in notes),
        "chords": any(len(chord.notes) > 1 for chord in chords),
        "lyrics": any(staff.lyrics for staff in staffs),
        "ornaments": any(note.left_ornament or note.right_ornament for note in notes)
        or any(event.ornament for event in events),
        "polyphonic_notation": len(staffs) > 1,
        "rests": any(event.kind is EventKind.REST for event in events),
        "tablature": bool(chords),
        "ties": any(span.kind is SpanKind.TIE for staff in staffs for span in staff.spans),
    }
    return sorted(name for name, present in flags.items() if present)


def _semantics(piece: Piece) -> dict[str, int]:
    score = _score(piece)
    staffs = score.staffs if score else ()
    events = _score_events(score)
    chords = tuple(chord for bar in piece.bars for chord in bar.chords)
    notes = tuple(note for chord in chords for note in chord.notes)
    return {
        "bars": len(piece.bars),
        "strings": piece.strings,
        "tab_events": len(chords),
        "tab_chord_events": sum(len(chord.notes) > 1 for chord in chords),
        "max_course": max((note.string for note in notes), default=0),
        "notation_staffs": len(staffs),
        "notation_events": len(events),
        "notation_rests": sum(event.kind is EventKind.REST for event in events),
        "lyrics": sum(len(staff.lyrics) for staff in staffs),
        "ties": sum(span.kind is SpanKind.TIE for staff in staffs for span in staff.spans),
        "tuplets": sum(event.tuplet is not None for event in events),
        "grace_notes": sum(event.grace for event in events),
    }


def _tab_projection(piece: Piece) -> tuple[object, ...]:
    return tuple(
        (
            bar.time_sig,
            tuple(
                (
                    chord.note_type,
                    bool(chord.dotted),
                    tuple(sorted((note.string, note.fret) for note in chord.notes)),
                )
                for chord in bar.chords
            ),
        )
        for bar in piece.bars
    )


def _projection_digest(piece: Piece) -> str:
    encoded = json.dumps(_tab_projection(piece), ensure_ascii=True, separators=(",", ":"))
    return _digest(encoded)


def _settings(piece: Piece) -> dict[str, str]:
    tuning = piece.tuning or tuning_preset(f"renaissance{piece.strings}")
    assert tuning is not None
    return {"style": piece.style or "french", "tuning": tuning}


@pytest.fixture(scope="module")
def curated_pieces() -> list[tuple[dict[str, Any], Path, Piece]]:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = _source_paths(raw["source_manifests"])
    selected = [(entry, paths[(entry["source_manifest"], entry["path"])]) for entry in raw["excerpts"]]
    if any(not path.is_file() for _entry, path in selected):
        pytest.skip("fetch the curated source manifests before running Petrucci acceptance")
    return [(entry, path, load_ft3(str(path))) for entry, path in selected]


def test_feature_manifest_is_a_source_honest_fixed_selection() -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_entries: dict[tuple[str, str], Any] = {}
    source_expectations: dict[tuple[str, str], dict[str, Any]] = {}
    for manifest_name in raw["source_manifests"]:
        manifest_path = Path(manifest_name)
        source = load_manifest(manifest_path)
        source_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_entries.update(((manifest_name, _source_key(entry.path)), entry) for entry in source.files)
        source_expectations.update(
            ((manifest_name, _source_key(entry["path"])), entry) for entry in source_raw["files"]
        )
    features = {feature for excerpt in raw["excerpts"] for feature in excerpt["features"]}

    assert raw["schema"] == 1
    assert raw["source_manifests"] == [
        "tests/fixtures/ft3/manifests/ft3-note-input-100.json",
        "tests/fixtures/ft3/manifests/ft3-random-75-v2.json",
    ]
    assert sorted(features) == raw["available_features"]
    assert set(raw["known_gaps"]) == {"grace_notes", "tablature_style_provenance", "tuplets"}
    assert len(raw["excerpts"]) == 4
    for excerpt in raw["excerpts"]:
        key = (excerpt["source_manifest"], excerpt["path"])
        source_entry = source_entries[key]
        assert excerpt["source_sha256"] == source_entry.sha256
        assert excerpt["source_url"] == source_entry.url
        assert source_expectations[key].get("style") is None
        assert excerpt["published_score"]["url"].endswith(".pdf")
        assert excerpt["published_score"]["pages"] >= 1
        assert excerpt["published_score"]["comparison"]


def test_curated_sources_match_feature_and_semantic_expectations(
    curated_pieces: list[tuple[dict[str, Any], Path, Piece]],
) -> None:
    for expected, path, piece in curated_pieces:
        assert _digest(path.read_bytes()) == expected["source_sha256"]
        assert _features(piece) == expected["features"]
        assert _semantics(piece) == expected["semantics"]


def test_curated_render_exports_and_tab_reopen_match_goldens(
    curated_pieces: list[tuple[dict[str, Any], Path, Piece]],
    tmp_path: Path,
) -> None:
    for expected, _path, piece in curated_pieces:
        settings = _settings(piece)
        output = tmp_path / expected["id"]
        output.mkdir()
        render_bar = expected["render_bar"] - 1
        rendered = typeset_piece(
            piece,
            options=TypesetOptions(
                width=100,
                height=32,
                bar_width=12,
                bar_offset=render_bar,
                cursor=(render_bar, 0, 0),
                settings=settings,
            ),
        ).text
        tab_text = export_tab(piece, {}, {}, 12, settings=settings)
        tab_path = output / "score.tab"
        tab_path.write_text(tab_text, encoding="utf-8")
        reopened = load_tab(str(tab_path), strings=piece.strings)
        lilypond_path = output / "score.ly"
        export_lilypond(str(lilypond_path), piece, {}, {}, 12, settings=settings)
        midi_path = output / "score.mid"
        export_midi(str(midi_path), piece, {}, {}, 12, settings=settings)
        goldens = expected["expectations"]

        assert _digest(rendered) == goldens["render_sha256"]
        assert _digest(tab_text) == goldens["tab_sha256"]
        assert _projection_digest(piece) == goldens["tab_projection_sha256"]
        assert _tab_projection(reopened) == _tab_projection(piece)
        assert _digest(lilypond_path.read_text(encoding="utf-8")) == goldens["lilypond_sha256"]
        assert _digest(midi_path.read_bytes()) == goldens["midi_sha256"]
