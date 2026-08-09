from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.exports.export_tab import export_tab
from oud.importers.tab import load_tab
from petrucci.core.model import Bar, Piece


def test_tab_tempo_roundtrips_and_overrides_default_playback_tempo(tmp_path: Path) -> None:
    source = tmp_path / "tempo.tab"
    piece = Piece(title="Tempo", tempo=120, bars=[Bar()])
    source.write_text(export_tab(piece, {}, {}, 12, settings={"tempo": "90"}), encoding="utf-8")

    reopened = load_tab(str(source))
    state = init_state(str(source), config_path=str(tmp_path / "missing.toml"))

    assert reopened.tempo == 120
    assert state.settings["tempo"] == "120"


def test_invalid_tab_tempo_is_reported() -> None:
    piece = Piece(title="Invalid", bars=[Bar()])
    text = export_tab(piece, {}, {}, 12, settings={})
    assert "# tempo:" not in text
