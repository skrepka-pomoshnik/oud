"""Shared placement rules for terminal span and parenthesis cues."""

from __future__ import annotations


def _place_open_cue(
    end_column: int,
    *,
    annotation_cells: list[str],
    span_rows: tuple[list[str], ...],
    allow_annotation_row: bool,
) -> None:
    if allow_annotation_row and 0 <= end_column < len(annotation_cells) and annotation_cells[end_column] == " ":
        annotation_cells[end_column] = "("
        return
    for row in span_rows:
        column = end_column - 1
        while 0 <= column < len(row):
            if row[column] == " ":
                row[column] = "("
                return
            column -= 1


def _place_close_cue(end_column: int, rows: tuple[list[str], ...]) -> None:
    for row in rows:
        if 0 <= end_column < len(row) and row[end_column] == " ":
            row[end_column] = ")"
            return


def place_parenthesize_tie_cues(
    *,
    ann_cells: list[str],
    orn_cells: list[str],
    tie_cells: list[str],
    slur_cells: list[str] | None,
    hold_cells: list[str] | None,
    gliss_cells: list[str] | None,
    paren_tie_cols: set[int],
    allow_ann_row: bool = True,
) -> None:
    """Place tie parenthesis cues without overwriting existing marks."""

    open_rows = (tie_cells, slur_cells or [], hold_cells or [], gliss_cells or [])
    close_rows = (tie_cells, orn_cells, slur_cells or [], hold_cells or [], gliss_cells or [])
    for end_column in paren_tie_cols:
        if not 0 <= end_column < len(tie_cells):
            continue
        _place_open_cue(
            end_column,
            annotation_cells=ann_cells,
            span_rows=open_rows,
            allow_annotation_row=allow_ann_row,
        )
        _place_close_cue(end_column, close_rows)
