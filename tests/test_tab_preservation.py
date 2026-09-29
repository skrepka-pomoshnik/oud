"""Saving a `.tab` from the original program keeps what Oud does not model (TODO C15)."""

from __future__ import annotations

from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write
from oud.exports.export_tab import HEADER, export_tab
from oud.importers.tab import parse_tab_text_data
from petrucci.core.model import Note

SOURCE = """% transcribed by hand
-P -6
$flagstyle=italian
{Title/Composer}
{Subtitle line}
{Third block}

b
S3-4
2+a&+c
x b.
[Da capo}
R2
t3a
xb
xc
T some text
2a  M2c+
bb
0a|b
.bb.

b
Y2a
MG
kg
2 N12
b!
e
"""


def _export(text: str) -> str:
    data = parse_tab_text_data(text)
    assert data is not None
    return export_tab(data.piece, {}, {}, 12, settings={"style": data.piece.style or "french"})


def test_an_unedited_file_saves_byte_identically_after_the_header() -> None:
    assert _export(SOURCE) == f"{HEADER}\n{SOURCE}"


def test_saving_twice_changes_nothing() -> None:
    once = _export(SOURCE)
    assert _export(once) == once


def test_an_edited_chord_is_rewritten_and_the_rest_is_kept() -> None:
    data = parse_tab_text_data(SOURCE)
    assert data is not None
    chord = data.piece.bars[0].chords[0]
    chord.notes.append(Note(3, 1, 0))
    data.piece.bars[0].notes = [note for c in data.piece.bars[0].chords for note in c.notes]

    lines = export_tab(data.piece, {}, {}, 12, settings={"style": "french"}).splitlines()

    assert "2+a&+c" not in lines
    assert "2acb" in lines
    assert "[Da capo}" in lines
    assert "2a  M2c+" in lines


def test_opening_and_saving_through_the_editor_keeps_the_file(tmp_path: Path) -> None:
    source = tmp_path / "source.tab"
    source.write_text(SOURCE, encoding="utf-8")
    state = init_state(str(source), config_path=str(tmp_path / "config.toml"))

    assert cmd_write(state, str(source))
    assert source.read_text(encoding="utf-8") == f"{HEADER}\n{SOURCE}"


def test_milan_files_keep_the_option_out_of_verbatim_chords() -> None:
    text = "-milan\nb\n21 3\nb\ne\n"
    out = _export(text)
    data = parse_tab_text_data(out)
    assert data is not None
    assert [(n.string, n.fret) for n in data.piece.bars[0].chords[0].notes] == [(1, 1), (3, 3)]
