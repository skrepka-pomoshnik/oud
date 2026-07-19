from petrucci.tab_style import resolve_tab_style_policy


def test_resolve_tab_style_policy_maps_scattered_settings_to_single_bundle() -> None:
    policy = resolve_tab_style_policy(
        {
            "style": "italian",
            "basslabels": "slash",
            "flagstyle": "englishgrid",
            "flaglean": "left",
            "flagstems": "double",
            "dotplacement": "afterstem",
            "tiecuestyle": "paren",
            "tienoteheads": "parenthesize",
            "slurcuestyle": "bracket",
            "holdcuestyle": "paren",
            "glisscuestyle": "slash",
            "italianorient": "reverse",
            "viewinvert": "off",
            "showfingerings": "on",
            "showornaments": "off",
        },
    )
    assert policy.style == "italian"
    assert policy.basslabels == "slash"
    assert policy.flagstyle == "englishgrid"
    assert policy.flaglean == "left"
    assert policy.stem_width == 2
    assert policy.dotplacement == "afterstem"
    assert policy.tiecuestyle == "paren"
    assert policy.tienoteheads == "parenthesize"
    assert policy.slurcuestyle == "bracket"
    assert policy.holdcuestyle == "paren"
    assert policy.glisscuestyle == "slash"
    assert policy.reverse_rows is True
    assert policy.showfingerings is True
    assert policy.showornaments is False
