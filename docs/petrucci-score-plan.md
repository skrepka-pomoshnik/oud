# Petrucci score renderer

## Purpose

Petrucci is a typed top-level package in the Oud wheel. It provides canonical
music records, deterministic layout, semantic cell geometry, and terminal-safe
painting. It imports neither `oud` nor `curses`.

Petrucci does not own playback clocks, editor state, target selection, grading,
colors, themes, or product-specific labels. Consumer adoption and release
rollout belong in the consuming repository, not Oud's backlog.

## Public contract

The source-independent path is:

```text
caller records -> NotationScore -> ScoreLayout -> SemanticFrame
```

- `petrucci.score` owns immutable staffs, measures, events, pitches, lyrics,
  spans, exact `Fraction` timing, and validation.
- `petrucci.flow` adapts a compact timed event stream and retains source IDs for
  every split notation segment.
- `petrucci.layout` returns systems, staff rows, event locations, onsets,
  clipping metadata, structural roles, and integer geometry.
- `petrucci.terminal` paints pretty or terminal-safe glyphs without changing
  identity or geometry.
- `typeset_score()` composes layout and painting. `typeset_layout()` repaints an
  existing layout without rebuilding it.

`ScoreTypesetResult.cells_for(event_id)` returns every visible cell owned by an
event or span. A caller decorates those coordinates using its own state:

```python
result = typeset_layout(layout, options=options)
attrs = {}
for event_id, caller_style in styles.items():
    for cell in result.cells_for(event_id):
        attrs[cell] = caller_style
```

Petrucci deliberately has no hit, miss, pending, current-target, confidence, or
numeric-result API. If caller decoration later needs transport through the
renderer, that requires a source-neutral opaque-token contract proven by more
than one consumer.

## Viewports

Vertical following selects `system_offset`. Horizontal following separates
layout width from paint width:

```python
options = ScoreTypesetOptions(
    width=40,
    height=18,
    layout_width=160,
    x_offset=60,
)
result = typeset_score(score, options=options)
```

The 160-column score is laid out once. Changing `x_offset` clips and translates
the same geometry into a 40-column frame. `typeset_layout()` keeps the original
`ScoreLayout` object, and visible event cells remain addressable after
translation. The caller chooses the origin; Petrucci assigns no meaning to it.

## Module ownership

Canonical notation layout is split by responsibility:

- `notation_horizontal`: onset measurement and system fitting;
- `notation_state`: clef, key, accidental, pitch, and slot state;
- `notation_elements`: notes, rests, stems, beams, ledgers, and event glyphs;
- `notation_annotations`: lyrics, spans, preamble, and continuation geometry;
- `notation_types`: private immutable records shared by those stages;
- `notation_layout`: orchestration, row allocation, and measure placement.

Tablature rendering is similarly split:

- `system_plan`: bar membership and justified width planning;
- `render_spacing` and `render_geometry`: source-to-display coordinates;
- `render_marks`: fingering, ornament, tuplet, tie, and span cues;
- `render_rhythm_rows`: flags, durations, and span-row painting;
- `render_staff_rows`: staff, melody, lyric, and cursor-map operations;
- `render_playback`: Oud Piece playback-cell projection;
- `render_system`: orchestration.

The Piece adapters preserve Oud's established tablature and imported-score
behavior. Another application should adapt directly to `NotationScore` or
`FlowEvent`; it must not depend on Piece, FT3, editor, or TUI modules.

## Supported notation

The canonical score path supports treble and bass staffs, notes, chords, rests,
whole through 64th durations, dots, stems, flags and beams, ledger lines,
key-aware accidentals, clef/key/meter changes, barlines and repeats, endings,
tuplets, grace notes, ties and slurs with system continuations, fermatas,
dynamics, ornaments, pitch labels, lyrics, measured wrapping, clipping, and
vertical or horizontal viewport translation.

Pretty and safe glyph modes preserve the same event IDs and structural roles.
Unknown or inconsistent canonical input raises an explicit validation error.

## Acceptance

The contract is protected by tests that require:

1. resolving every public symbol without importing `oud` or `curses`;
2. exact identity for repeated pitches, rests, chords, lyrics, overlaps, and
   measure-crossing splits;
3. event-to-segment and event-to-cell lookup without glyph parsing;
4. caller-owned decoration with no result-policy type in Petrucci;
5. horizontal viewport movement over one existing layout;
6. deterministic clipping and identity in pretty and safe modes;
7. narrow and normal layouts without illegal collisions;
8. no application-layer imports from generic code.

## Non-goals

- Product-specific adapters or rollout.
- Audio, pitch detection, grading, progression, or UI orchestration.
- Native FT3 writing or source-preservation fields in canonical notation.
- Pixel-identical print engraving or replacing LilyPond for PDF output.
- A separately published Petrucci distribution before its API is stable.
