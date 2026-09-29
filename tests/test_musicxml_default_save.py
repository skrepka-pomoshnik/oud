"""MusicXML is the default save format; Oud-written MusicXML reopens as a native document (TODO C16)."""

from __future__ import annotations

from pathlib import Path

from oud.editor.core.document import DocumentMode
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write, cmd_write_default
from oud.editor.services.io.loading import cmd_open
from tests.helpers_keyscript import press_keys

FOREIGN_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1"><work><work-title>Foreign</work-title></work>
<part-list><score-part id="P1"><part-name>Lute</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>1</divisions>
<time><beats>4</beats><beat-type>4</beat-type></time>
<staff-details><staff-lines>6</staff-lines></staff-details></attributes>
<note><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><type>whole</type>
<notations><technical><string>1</string><fret>0</fret></technical></notations></note>
</measure></part></score-partwise>
"""


def _config(tmp_path: Path) -> str:
    return str(tmp_path / "config.toml")


def test_a_new_document_saves_as_musicxml_and_reopens_natively(tmp_path: Path) -> None:
    state = init_state(None, config_path=_config(tmp_path))
    press_keys(state, ["i", "a", "b", 27])

    assert not cmd_write_default(state, "")
    assert state.cmdline == "w untitled.musicxml"

    target = tmp_path / "piece.musicxml"
    assert cmd_write(state, str(target))
    assert "<software>Oud</software>" in target.read_text(encoding="utf-8")

    reopened = init_state(str(target), config_path=_config(tmp_path))
    assert reopened.document_mode is DocumentMode.NATIVE
    assert reopened.write_path == str(target)
    assert [[(n.string, n.fret) for n in c.notes] for c in reopened.piece.bars[0].chords] == [[(1, 0)], [(1, 1)]]

    press_keys(reopened, ["x"])
    assert cmd_write_default(reopened, "")
    again = init_state(str(target), config_path=_config(tmp_path))
    assert [[(n.string, n.fret) for n in c.notes] for c in again.piece.bars[0].chords] == [[(1, 1)]]


def test_a_missing_musicxml_path_names_the_new_document(tmp_path: Path) -> None:
    missing = tmp_path / "new.musicxml"
    state = init_state(str(missing), config_path=_config(tmp_path))

    assert state.piece.import_warnings == []
    assert not cmd_write_default(state, "")
    assert state.cmdline == f"w {missing}"


def test_foreign_musicxml_is_never_the_default_target(tmp_path: Path) -> None:
    source = tmp_path / "foreign.musicxml"
    source.write_text(FOREIGN_MUSICXML, encoding="utf-8")
    state = init_state(str(source), config_path=_config(tmp_path))

    assert state.document_mode is DocumentMode.IMPORTED_PROJECTION
    assert state.write_path is None
    assert not cmd_write_default(state, "")
    assert state.cmdline == f"w {tmp_path / 'foreign.oud.musicxml'}"
    assert source.read_text(encoding="utf-8") == FOREIGN_MUSICXML


def test_opening_oud_musicxml_with_e_is_native(tmp_path: Path) -> None:
    target = tmp_path / "piece.musicxml"
    first = init_state(None, config_path=_config(tmp_path))
    press_keys(first, ["i", "a", 27])
    assert cmd_write(first, str(target))

    state = init_state(None, config_path=_config(tmp_path))
    cmd_open(state, str(target), no_path_msg="no path")

    assert state.document_mode is DocumentMode.NATIVE
    assert state.write_path == str(target)


def test_tab_documents_keep_saving_to_tab(tmp_path: Path) -> None:
    source = tmp_path / "piece.tab"
    source.write_text("b\n0a\nb\ne\n", encoding="utf-8")
    state = init_state(str(source), config_path=_config(tmp_path))

    assert state.write_path == str(source)
    assert cmd_write_default(state, "")
    assert source.read_text(encoding="utf-8").startswith("% Written by oud")


def test_other_destinations_are_refused(tmp_path: Path) -> None:
    state = init_state(None, config_path=_config(tmp_path))
    target = tmp_path / "piece.pdf"

    assert not cmd_write(state, str(target))
    assert state.message == "Save destination must end in .musicxml, .xml or .tab"
    assert not target.exists()
