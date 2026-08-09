from petrucci.cue_placement import place_parenthesize_tie_cues


def test_parenthesized_tie_cues_use_shared_collision_priority() -> None:
    annotations = [" ", " ", "A"]
    ornaments = [" ", " ", " "]
    ties = ["-", " ", " "]

    place_parenthesize_tie_cues(
        ann_cells=annotations,
        orn_cells=ornaments,
        tie_cells=ties,
        slur_cells=None,
        hold_cells=None,
        gliss_cells=None,
        paren_tie_cols={2},
    )

    assert annotations == [" ", " ", "A"]
    assert ties == ["-", "(", ")"]
