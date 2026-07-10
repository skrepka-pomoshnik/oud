#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oud.editor.init import init_state  # noqa: E402
from oud.petrucci import TypesetOptions, typeset_piece  # noqa: E402


def _svg(lines: list[str], *, title: str) -> str:
    cell_width = 9.2
    row_height = 18
    padding = 24
    title_height = 42
    columns = max((len(line) for line in lines), default=1)
    width = int(columns * cell_width + padding * 2)
    height = int(title_height + len(lines) * row_height + padding)
    rows: list[str] = []
    for index, line in enumerate(lines):
        css_class = "status" if index >= len(lines) - 2 else "screen"
        y = title_height + (index + 1) * row_height
        text = html.escape(line.rstrip()) or "&#160;"
        rows.append(
            f'  <text class="{css_class}" x="{padding}" y="{y}" '
            f'xml:space="preserve">{text}</text>',
        )
    body = "\n".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
  <title id="title">oud terminal tablature editor</title>
  <desc id="description">A real oud renderer frame showing {html.escape(title)}.</desc>
  <style>
    .screen, .status {{
      font-family: "DejaVu Sans Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 14px;
      letter-spacing: 0;
    }}
    .screen {{ fill: #e8e9eb; }}
    .status {{ fill: #89d185; font-weight: 700; }}
    .window-title {{
      fill: #b6bac2;
      font-family: "DejaVu Sans", sans-serif;
      font-size: 13px;
      letter-spacing: 0;
    }}
  </style>
  <rect width="{width}" height="{height}" rx="8" fill="#101216"/>
  <path d="M8 0h{width - 16}a8 8 0 0 1 8 8v34H0V8a8 8 0 0 1 8-8z" fill="#252932"/>
  <rect x="16" y="15" width="12" height="12" rx="2" fill="#e56b6f"/>
  <rect x="34" y="15" width="12" height="12" rx="2" fill="#e8b65a"/>
  <rect x="52" y="15" width="12" height="12" rx="2" fill="#70c58b"/>
  <text class="window-title" x="76" y="25">oud - {html.escape(title)}</text>
{body}
</svg>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the README TUI screenshot as SVG.")
    parser.add_argument("--source", default="lutemusic/pavan_01_8C.ft3")
    parser.add_argument("--output", default="docs/oud-tui.svg")
    parser.add_argument("--width", type=int, default=108)
    parser.add_argument("--height", type=int, default=30)
    args = parser.parse_args(argv)

    state = init_state(args.source, config_path="config.toml")
    state.screen_width = max(60, args.width)
    state.screen_height = max(18, args.height)
    state.message = ""
    state.settings.update(
        {
            "layout": "auto",
            "justify": "smart",
            "showdur": "on",
            "showspans": "off",
        },
    )
    result = typeset_piece(
        state.piece,
        options=TypesetOptions(
            width=state.screen_width,
            height=state.screen_height,
            bar_width=state.bar_width,
            cursor=(state.cursor_bar, state.cursor_string, state.cursor_col),
            include_status=True,
            settings=state.settings,
        ),
        overrides=state.overrides,
        durations=state.durations,
        ornaments=state.ornaments,
        annotations=state.annotations,
        highlights=state.highlights,
        dotted=state.dotted,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
        glisses=state.glisses,
        stave_breaks=state.stave_breaks,
    )
    lines = list(result.lines)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_svg(lines, title=Path(args.source).name), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
