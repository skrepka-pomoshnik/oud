from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oud.core.ft3 import load_ft3
from scripts import fetch_ft3_corpus
from scripts.corpus_smoke import scan_files
from scripts.fetch_ft3_corpus import fetch_manifest, load_manifest, manifest_paths
from scripts.ft3_audit import audit_file

RANDOM_MANIFEST = Path("corpus/ft3-random-75.json")


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
    assert all(path.is_relative_to((Path.cwd() / "lutemusic").resolve()) for path in manifest_paths(manifest))


def test_ft3_payload_suffixes_are_ignored() -> None:
    patterns = set(Path(".gitignore").read_text(encoding="utf-8").splitlines())
    assert {"*.ft3", "*.ft3.gz", "*.ft3.txt"} <= patterns


def test_random_75_payloads_load_without_semantic_audit_failures() -> None:
    manifest = load_manifest(RANDOM_MANIFEST)
    paths = manifest_paths(manifest)
    missing = [_relative(path) for path in paths if not path.is_file()]
    if missing:
        pytest.skip("fetch corpus/ft3-random-75.json before running external corpus tests")

    bad_hashes = [
        _relative(path)
        for entry, path in zip(manifest.files, paths, strict=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.sha256
    ]
    assert bad_hashes == []

    results = scan_files(paths)
    assert len(results) == 75
    assert [result.path for result in results if result.error] == []
    warned = {_relative(Path(result.path)) for result in results if result.warnings}
    assert warned == set()

    unresolved = set()
    for path in paths:
        report = audit_file(path)
        if any(
            report[key]
            for key in ("note_extra_residuals", "vocal_flag_residuals", "unknown_source_records", "warnings")
        ):
            unresolved.add(_relative(path))
    assert unresolved == set()


def test_couperin_duet_maps_two_note_voices_to_one_77_bar_staff() -> None:
    path = Path("lutemusic/random-75/054/la_couperin_duet.ft3")
    if not path.is_file():
        pytest.skip("fetch corpus/ft3-random-75.json before running external corpus tests")

    piece = load_ft3(str(path))
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
