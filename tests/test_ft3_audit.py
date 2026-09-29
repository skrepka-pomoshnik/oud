import json
from pathlib import Path

import pytest

from scripts.corpus import audit as ft3_audit
from scripts.corpus.audit import audit_file


@pytest.mark.ft3_corpus
def test_ft3_audit_reports_typed_source_records_without_unresolved_values() -> None:
    can_she_excuse = audit_file(Path("tests/fixtures/ft3/corpus/05_can_she_excuse/can_she_excuse.ft3"))
    assert can_she_excuse["note_extra_residuals"] == {}
    assert can_she_excuse["vocal_flag_residuals"] == {}
    assert can_she_excuse["source_record_kinds"] == {"note-lyrics": 40}
    assert can_she_excuse["unknown_source_records"] == 0

    willoughby = audit_file(Path("tests/fixtures/ft3/corpus/willoughby_duet.ft3"))
    assert willoughby["note_extra_residuals"] == {}

    now_o_now = audit_file(Path("tests/fixtures/ft3/corpus/now_o_now.ft3"))
    assert now_o_now["source_record_kinds"] == {"note": 1, "note-lyrics": 47}
    assert now_o_now["unknown_source_records"] == 0


def test_ft3_audit_main_reports_json_for_file(tmp_path: Path, monkeypatch, capsys) -> None:
    source = tmp_path / "score.ft3"
    source.touch()
    report = {
        "path": str(source),
        "note_extra_residuals": {"0x0001": 1},
        "vocal_flag_residuals": {},
        "source_record_kinds": {},
        "unknown_source_records": 0,
        "warnings": [],
    }
    monkeypatch.setattr(ft3_audit, "audit_file", lambda _path: report)

    assert ft3_audit.main([str(source), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["files"] == 1
    assert payload["unresolved_files"] == 1


def test_ft3_audit_main_text_lists_only_unresolved_files(tmp_path: Path, monkeypatch, capsys) -> None:
    clean_path = tmp_path / "clean.ft3"
    bad_path = tmp_path / "bad.ft3"
    clean_path.touch()
    bad_path.touch()

    def fake_audit(path: Path) -> dict[str, object]:
        return {
            "path": str(path),
            "note_extra_residuals": {},
            "vocal_flag_residuals": {},
            "source_record_kinds": {},
            "unknown_source_records": 0,
            "warnings": ["partial"] if path == bad_path else [],
        }

    monkeypatch.setattr(ft3_audit, "audit_file", fake_audit)

    assert ft3_audit.main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert str(bad_path) in output
    assert str(clean_path) not in output
    assert "warnings: ['partial']" in output
    assert "Scanned 2 file(s): 1 with unresolved" in output
