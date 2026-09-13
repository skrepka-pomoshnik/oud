"""Small hand-drawn musical masks on the same dot lattice as staff geometry."""

from __future__ import annotations

from petrucci.engraving.layout.engine import LayoutElement
from petrucci.terminal.canvas.dots import DotCanvas

_DIGITS = {
    "0": ("###", "# #", "# #", "# #", "###"),
    "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"),
    "3": ("###", "  #", " ##", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"),
    "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"),
    "7": ("###", "  #", " # ", " # ", " # "),
    "8": ("###", "# #", "###", "# #", "###"),
    "9": ("###", "# #", "###", "  #", "###"),
}
_TREBLE = (
    "   # ",
    "  ## ",
    "  # #",
    "  # #",
    "  ## ",
    "  #  ",
    " ##  ",
    " #   ",
    "##   ",
    "# #  ",
    "# ## ",
    "##  #",
    "# # #",
    "# # #",
    " ### ",
    "  #  ",
    "  #  ",
    "  #  ",
    "  #  ",
    " ##  ",
    "##   ",
)
_BASS = (" ### ", "#   #", "##  #", "    #", "   # ", "  #  ", " #   ")
_ACCIDENTALS = {
    "sharp": (" # #", " # #", "####", " # #", "####", " # #", " # #"),
    "flat": ("#  ", "#  ", "#  ", "###", "# #", "## ", "#  "),
    "natural": ("#  ", "#  ", "###", "# #", "###", "  #", "  #"),
}


def stamp(
    canvas: DotCanvas,
    element: LayoutElement,
    *,
    x: int,
    y: int,
    mask: tuple[str, ...],
    priority: int,
) -> None:
    canvas.clear(x, y, max(map(len, mask)), len(mask), priority)
    for dy, row in enumerate(mask):
        for dx, pixel in enumerate(row):
            if pixel != " ":
                canvas.pixel(x + dx, y + dy, element, priority)


def notehead(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    opened = element.value in {"whole", "half", "breve"}
    mask = (" ## ", "#  #", " ## ") if opened else (" ###", "####", "### ")
    stamp(canvas, element, x=x - 1, y=y - 1, mask=mask, priority=priority)
    if element.value == "breve":
        canvas.vertical(x - 2, y - 2, y + 2, element, priority)
        canvas.vertical(x + 3, y - 2, y + 2, element, priority)


def clef(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    if element.value == "treble":
        stamp(canvas, element, x=x - 1, y=y - 8, mask=_TREBLE, priority=priority)
        return
    stamp(canvas, element, x=x - 1, y=y - 4, mask=_BASS, priority=priority)
    canvas.pixel(x + 5, y - 3, element, priority)
    canvas.pixel(x + 5, y + 1, element, priority)


def rest(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    blocks = {"whole": -3, "half": -2, "breve": -4, "1": -3, "2": -2}
    if element.value in blocks:
        height = 4 if element.value == "breve" else 2
        stamp(
            canvas,
            element,
            x=x - 1,
            y=y + blocks[element.value],
            mask=("####",) * height,
            priority=priority,
        )
        return
    hooks = {
        "eighth": 1,
        "sixteenth": 2,
        "thirty-second": 3,
        "sixty-fourth": 4,
        "one-hundred-twenty-eighth": 5,
        "8": 1,
        "16": 2,
        "32": 3,
        "64": 4,
        "128": 5,
    }
    count = hooks.get(element.value, 0)
    if not count:
        mask = (" # ", " ##", " # ", "#  ", " # ", "  #", "## ", "#  ", " # ")
        stamp(canvas, element, x=x - 1, y=y - 4, mask=mask, priority=priority)
        return
    mask = ("## #", " ###", "  # ") * count + (" #  ", "#   ")
    stamp(canvas, element, x=x - 1, y=y - 3, mask=mask, priority=priority)


def accidental(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    value = element.value.partition(":")[0]
    if value in _ACCIDENTALS:
        name, count = value, 1
    else:
        alter = int(value or "0")
        name = "sharp" if alter > 0 else "flat" if alter < 0 else "natural"
        count = max(1, abs(alter))
    for index in range(min(count, canvas.width)):
        stamp(canvas, element, x=x - 2 + index * 3, y=y - 3, mask=_ACCIDENTALS[name], priority=priority)


def meter(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    numerator, _, denominator = element.value.partition("/")
    for text, top in ((numerator, y - 3), (denominator, y + 3)):
        for index, digit in enumerate(text):
            stamp(canvas, element, x=x + index * 4, y=top, mask=_DIGITS[digit], priority=priority)
