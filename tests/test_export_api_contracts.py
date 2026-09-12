from inspect import Parameter, signature

import pytest

from oud.exports.export_tab import export_ascii, export_tab, export_tab_to_file
from oud.exports.midi.runtime import export_midi
from petrucci.rendering.api import render_piece


@pytest.mark.parametrize(
    ("function", "positional_count"),
    [
        (render_piece, 5),
        (export_tab, 4),
        (export_ascii, 4),
        (export_tab_to_file, 5),
        (export_midi, 5),
    ],
)
def test_export_boundaries_keep_optional_controls_keyword_only(function, positional_count: int) -> None:
    parameters = list(signature(function).parameters.values())
    assert all(parameter.kind is Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters[:positional_count])
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters[positional_count:])
