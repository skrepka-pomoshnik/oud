import pytest

from petrucci.engraving.layout.fitting import BoxFitOptions, MeasuredBox, fit_measured_boxes


def test_fit_measured_boxes_wraps_from_natural_width_and_justifies_nonfinal_system() -> None:
    systems = fit_measured_boxes(
        tuple(MeasuredBox(f"measure-{index}", min_width=6, natural_width=10) for index in range(5)),
        options=BoxFitOptions(available_width=32, gap=1, max_stretch_per_box=4),
    )

    assert [[box.id for box in system.boxes] for system in systems] == [
        ["measure-0", "measure-1", "measure-2"],
        ["measure-3", "measure-4"],
    ]
    assert systems[0].width == 32
    assert systems[0].filled
    assert systems[1].width == 21
    assert not systems[1].filled


def test_fit_measured_boxes_keeps_forced_and_final_systems_natural() -> None:
    systems = fit_measured_boxes(
        (
            MeasuredBox("a", 4, 8),
            MeasuredBox("b", 4, 8, break_after=True),
            MeasuredBox("c", 4, 8),
        ),
        options=BoxFitOptions(available_width=40, gap=1),
    )

    assert [system.width for system in systems] == [17, 8]
    assert all(not system.filled for system in systems)


def test_fit_measured_boxes_marks_oversized_single_box_as_clipped() -> None:
    systems = fit_measured_boxes(
        (MeasuredBox("dense", 20, 50),),
        options=BoxFitOptions(available_width=24),
    )

    assert systems[0].boxes[0].width == 24
    assert systems[0].boxes[0].clipped


def test_measured_box_rejects_invalid_contract() -> None:
    with pytest.raises(ValueError, match="natural width"):
        MeasuredBox("bad", min_width=8, natural_width=4)


def test_fit_measured_boxes_can_justify_final_system_to_full_width() -> None:
    systems = fit_measured_boxes(
        (
            MeasuredBox("a", 4, 8),
            MeasuredBox("b", 4, 8, break_after=True),
            MeasuredBox("c", 4, 8),
        ),
        options=BoxFitOptions(available_width=40, gap=1, justify_last_system=True),
    )

    assert [system.width for system in systems] == [17, 40]
    assert not systems[0].filled
    assert systems[1].filled
