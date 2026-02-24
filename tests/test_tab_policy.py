from oud.core.model import Bar, Chord, Note
from oud.core.tab_policy import (
    TAB_NOTATION_PRESETS,
    apply_tabnotation_preset,
    fret_label,
    hold_span_chars,
    rows_reversed,
    show_time_cue_for_bar,
    slur_span_chars,
    string_label,
    system_display_indices_for_bars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
    time_cue_reserved_width,
    time_cue_side_pad,
    time_sig_inline_rows,
    visual_row_indices,
)


def test_fret_label_french_and_italian() -> None:
    assert fret_label("french", 0) == "a"
    assert fret_label("french", 9) == "k"
    assert fret_label("italian", 10) == "x"


def test_fret_label_french_alt_c() -> None:
    assert fret_label("french", 2, french_c_shape="alt") == "r"


def test_string_label_uses_bass_fallback_when_tuning_missing() -> None:
    labels = ["g", "d", "a", "f", "c", "g", "", ""]
    assert string_label(actual=6, total_strings=8, tuning_labels=labels, basslabels="numeric") == " 7"
    assert string_label(actual=7, total_strings=8, tuning_labels=labels, basslabels="slash") == "//"


def test_time_sig_inline_rows_formats_common_and_numeric() -> None:
    assert time_sig_inline_rows("C", "C") == [" ", "C", " "]
    assert time_sig_inline_rows("3/4", "O") == [" 3"]
    assert time_sig_inline_rows("O", "O", style_mode="numeric") == [" 3"]
    assert time_sig_inline_rows("C", "C", style_mode="numeric") == [" 4"]
    assert time_sig_inline_rows("O", "O", style_mode="fraction") == [" 3", " /", " 4"]


def test_time_cue_visibility_policy_for_first_bar_and_meter_change() -> None:
    assert show_time_cue_for_bar(bar_index=0, current_time_value="C", prev_time_value=None, sig_label="C") is True
    assert show_time_cue_for_bar(bar_index=3, current_time_value="C", prev_time_value="C", sig_label="C") is False
    assert show_time_cue_for_bar(bar_index=3, current_time_value="O", prev_time_value="C", sig_label="O") is True
    assert show_time_cue_for_bar(bar_index=2, current_time_value="C", prev_time_value="O", sig_label="") is False


def test_time_cue_padding_policy() -> None:
    assert time_cue_side_pad(show_time_cue=False, scale_bar=True) == 0
    assert time_cue_side_pad(show_time_cue=True, scale_bar=False) == 0
    assert time_cue_side_pad(show_time_cue=True, scale_bar=True) == 2
    assert time_cue_reserved_width(show_time_cue=True, scale_bar=True) == 4


def test_rows_reversed_policy_matches_settings_semantics() -> None:
    assert rows_reversed(style="french", italian_orient="normal", viewinvert="off") is False
    assert rows_reversed(style="italian", italian_orient="reverse", viewinvert="off") is True
    assert rows_reversed(style="french", italian_orient="normal", viewinvert="on") is True


def test_visual_row_indices_reverses_only_when_requested() -> None:
    indices = [0, 1, 2, 6]
    assert visual_row_indices(indices, reverse=False) == [0, 1, 2, 6]
    assert visual_row_indices(indices, reverse=True) == [6, 2, 1, 0]


def test_system_display_indices_for_bars_hides_unused_bass_rows() -> None:
    bars = [
        Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
        Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0)])]),
        Bar(notes=[Note(8, 1, 0)]),
    ]
    assert system_display_indices_for_bars(bars[:1], total_strings=8) == [0, 1, 2, 3, 4, 5]
    assert system_display_indices_for_bars(bars[:2], total_strings=8) == [0, 1, 2, 3, 4, 5, 6]
    assert system_display_indices_for_bars(bars, total_strings=8) == [0, 1, 2, 3, 4, 5, 6, 7]


def test_apply_tabnotation_preset_updates_settings_bundle() -> None:
    settings = {"showdur": "off", "showextras": "off"}
    assert apply_tabnotation_preset(settings, "full") is True
    assert settings["tabnotation"] == "full"
    for key, value in TAB_NOTATION_PRESETS["full"].items():
        assert settings[key] == value
    assert apply_tabnotation_preset(settings, "missing") is False


def test_tie_span_chars_policy() -> None:
    assert tie_span_chars("bracket") == ("[", "]", "-")
    assert tie_span_chars("paren") == ("(", ")", "-")
    assert tie_span_chars("hide") is None


def test_slur_and_hold_span_chars_policy() -> None:
    assert slur_span_chars("paren") == ("(", ")", "~")
    assert slur_span_chars("bracket") == ("[", "]", "~")
    assert slur_span_chars("hide") is None
    assert hold_span_chars("angle") == ("<", ">", "_")
    assert hold_span_chars("paren") == ("(", ")", "_")
    assert hold_span_chars("hide") is None


def test_tie_notehead_hidden_cols_policy() -> None:
    ties = [(0, 1, 3), (1, 0, 2), (0, 4, 4)]
    assert tie_notehead_hidden_cols(ties, bar_index=0, mode="show") == set()
    assert tie_notehead_hidden_cols(ties, bar_index=0, mode="hide") == {3, 4}
    assert tie_notehead_hidden_cols(ties, bar_index=0, mode="parenthesize") == set()
    assert tie_notehead_parenthesize_cols(ties, bar_index=0, mode="show") == set()
    assert tie_notehead_parenthesize_cols(ties, bar_index=0, mode="parenthesize") == {3, 4}


def test_apply_tabnotation_preset_is_idempotent_and_overridable() -> None:
    settings = {"showdur": "off", "showextras": "off", "showtactus": "off"}
    assert apply_tabnotation_preset(settings, "full") is True
    snapshot = dict(settings)
    assert apply_tabnotation_preset(settings, "full") is True
    assert settings == snapshot
    settings["showdur"] = "off"
    assert settings["tabnotation"] == "full"
    assert settings["showdur"] == "off"
