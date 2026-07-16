"""Generic measured-box fitting used by score and tablature adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeasuredBox:
    id: str
    min_width: int
    natural_width: int
    stretch_weight: int = 1
    break_after: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            _invalid("measured box ID must not be empty")
        if self.min_width <= 0:
            _invalid("measured box minimum width must be positive")
        if self.natural_width < self.min_width:
            _invalid("measured box natural width must be at least its minimum width")
        if self.stretch_weight < 0:
            _invalid("measured box stretch weight must be non-negative")


@dataclass(frozen=True, slots=True)
class PlacedBox:
    id: str
    x: int
    width: int
    clipped: bool = False


@dataclass(frozen=True, slots=True)
class BoxSystem:
    boxes: tuple[PlacedBox, ...]
    width: int
    filled: bool


def fit_measured_boxes(
    boxes: tuple[MeasuredBox, ...],
    *,
    available_width: int,
    gap: int = 0,
    justify: bool = True,
    max_stretch_per_box: int = 6,
) -> tuple[BoxSystem, ...]:
    """Pack natural boxes into systems, then apply bounded justification."""

    if available_width <= 0:
        _invalid("available width must be positive")
    if gap < 0:
        _invalid("box gap must be non-negative")
    if max_stretch_per_box < 0:
        _invalid("maximum stretch must be non-negative")
    _validate_unique_ids(boxes)

    systems: list[BoxSystem] = []
    current: list[MeasuredBox] = []
    for box in boxes:
        if current and _natural_width((*current, box), gap) > available_width:
            systems.append(
                _place_system(
                    tuple(current),
                    available_width=available_width,
                    gap=gap,
                    fill=justify,
                    max_stretch_per_box=max_stretch_per_box,
                ),
            )
            current = []
        current.append(box)
        if box.break_after:
            systems.append(
                _place_system(
                    tuple(current),
                    available_width=available_width,
                    gap=gap,
                    fill=False,
                    max_stretch_per_box=max_stretch_per_box,
                ),
            )
            current = []
    if current:
        systems.append(
            _place_system(
                tuple(current),
                available_width=available_width,
                gap=gap,
                fill=False,
                max_stretch_per_box=max_stretch_per_box,
            ),
        )
    return tuple(systems)


def _place_system(
    boxes: tuple[MeasuredBox, ...],
    *,
    available_width: int,
    gap: int,
    fill: bool,
    max_stretch_per_box: int,
) -> BoxSystem:
    widths = [min(box.natural_width, available_width) for box in boxes]
    base_width = sum(widths) + (gap * max(0, len(widths) - 1))
    slack = max(0, available_width - base_width)
    if fill and slack:
        _distribute_stretch(widths, boxes, slack=slack, cap=max_stretch_per_box)
    placed: list[PlacedBox] = []
    x = 0
    for box, width in zip(boxes, widths, strict=True):
        placed.append(PlacedBox(id=box.id, x=x, width=width, clipped=box.natural_width > width))
        x += width + gap
    total = max(0, x - gap) if placed else 0
    return BoxSystem(boxes=tuple(placed), width=total, filled=fill and total == available_width)


def _distribute_stretch(
    widths: list[int],
    boxes: tuple[MeasuredBox, ...],
    *,
    slack: int,
    cap: int,
) -> None:
    remaining = slack
    added = [0] * len(widths)
    schedule = [index for index, box in enumerate(boxes) for _ in range(box.stretch_weight)]
    while remaining > 0 and schedule:
        changed = False
        for index in schedule:
            if added[index] >= cap:
                continue
            widths[index] += 1
            added[index] += 1
            remaining -= 1
            changed = True
            if remaining == 0:
                break
        if not changed:
            break


def _natural_width(boxes: tuple[MeasuredBox, ...], gap: int) -> int:
    return sum(box.natural_width for box in boxes) + (gap * max(0, len(boxes) - 1))


def _validate_unique_ids(boxes: tuple[MeasuredBox, ...]) -> None:
    ids = [box.id for box in boxes]
    if len(ids) != len(set(ids)):
        _invalid("measured box IDs must be unique")


def _invalid(message: str) -> None:
    raise ValueError(message)
