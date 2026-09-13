# Petrucci notation handoff for Voce

The notation work requested in `/tmp/petrucci_handoff.md` is complete in
Petrucci. Voce adoption remains a separate consumer task. Petrucci owns immutable
notation, layout, clipping, semantic identity, and pitch geometry; Voce continues
to own assessment, interaction, audio transport, lesson policy, and transient
sample retention.

## Public contracts

All imports below are from `petrucci`:

```python
layout_score_proportional(
    score: NotationScore,
    request: TimelineProjectionRequest,
    *,
    metrics: LayoutMetrics | None = None,
    policy: NotationLayoutPolicy | None = None,
) -> ScoreLayout

project_written_pitch(
    score: NotationScore,
    staff_id: str,
    time: Fraction,
    pitch: WrittenPitch,
    *,
    bottom_row: int,
    viewport_y_offset: int = 0,
    rounding: ProjectionRounding = ProjectionRounding.NEAREST,
) -> PitchProjection

project_continuous_pitch(
    score: NotationScore,
    staff_id: str,
    time: Fraction,
    midi: Fraction,
    *,
    bottom_row: int,
    viewport_y_offset: int = 0,
    rounding: ProjectionRounding = ProjectionRounding.NEAREST,
) -> PitchProjection

SemanticFrame.cells_for_many(
    element_ids: Iterable[str],
) -> Mapping[str, tuple[tuple[int, int], ...]]

clear_layout_cache() -> None
```

`TimelineProjectionRequest.origin` and `columns_per_whole` are exact musical
whole-note units. `preamble_width` reserves terminal columns before the timeline.
The integration correction anchors the first written notehead at its onset,
placing accidental/editorial prefixes before it. Proportional staff lines extend
through the viewport even when the last visible measure ends earlier.
Clipped right edges do not create musical barlines or reserve their spacing.
Continuous pitch projection uses exact octave-local interpolation without
allocating a 257-point table per sample. A Voce 96-note/100-sample, 100×18 local
probe improved from roughly 894–1,043 ms/frame to 32 ms for a repeated viewport
and 90–123 ms for changed/cold layouts; these are workload measurements, not
universal frame-time guarantees. Final integration validation: Ruff lint/format,
Ty and 1,665 tests pass, with 11 skips and 95.08% coverage.

The scale is never changed to resolve collisions: `ScoreLayout.timeline_collisions`
reports onset quantization and `layout_collisions(layout)` reports engraved-box
collisions. Measure boundaries, source IDs, split-segment IDs, clipped endpoints,
and continuation geometry remain available on the returned layout.

Set `NotationLayoutPolicy(show_time_signature=False)` to hide meter glyphs.
The canonical meter, validation, beaming, timing, and preamble reservation are
unchanged. Breve and dotted-breve notes and rests retain their written spelling;
Petrucci does not replace them with tied whole notes.

## Runnable examples

```bash
uv run python scripts/rendering/petrucci_overlay_example.py
uv run python scripts/rendering/petrucci_hidden_meter_example.py
```

The first combines fixed-scale layout, left clipping, indexed event highlighting,
and a fractional continuous-pitch sample. The second hides a 3/4 glyph while
printing the still-present canonical meter.

## Voce migration

| Voce responsibility being removed | Petrucci replacement |
| --- | --- |
| Relocate painted note cells and stretch connectors | `layout_score_proportional` before `paint_score` |
| Reconstruct periodic barlines from a global meter | `ScoreLayout.measure_boundaries` |
| Derive staff rows from MIDI pitch | `project_written_pitch` and `project_continuous_pitch` |
| Scan every semantic cell for every event | `SemanticFrame.cells_for_many` |
| Recover span endpoints from nearest columns | Stable source IDs plus `FlowAdaptation.notation_ids_for` |
| Drop cross-measure sustained identities | Split-segment IDs and `active_notation_event_ids` |
| Remove meter metadata to hide its glyph | `NotationLayoutPolicy(show_time_signature=False)` |

Voce should retain exact `Fraction` time through this boundary. Its viewport
selects `TimelineProjectionRequest.origin`, scale, and dimensions. Decorations
should use the returned cell index; microphone samples remain caller-owned and
must not be inserted into a score or static-layout cache.

## Cache ownership and measured lifecycle

Petrucci owns separate 64-entry LRU caches for ordinary and proportional immutable
layouts. Cache keys contain the canonical score, width/scale, metrics, and policy;
painted frames and pitch samples are not cached there. Each `SemanticFrame` owns
its own immutable ID-to-cell index. Call `clear_layout_cache()` on score-set
replacement or when the consumer needs deterministic release; it clears both
layout caches.

Reference workload on 2026-09-13: 96 quarter-note events, five repeated layouts,
five scrolling paints and indexed batch lookups, widths 80/96/112, heights 24/30,
and 66 distinct score replacements (exceeding one cache's capacity). CPython
3.13.5 reported 7.715 ms paint p95, 0.019 ms batch lookup p95, 48.009 ms resize
p95, 176.379 ms replacement-layout p95 under `tracemalloc`, 10,392.986 KiB peak
traced-heap growth, and 3.742 KiB retained after cache clearing and collection.
These are local measurements, not universal latency guarantees.

Reproduce the workload and optionally enforce ceilings with:

```bash
uv run python scripts/rendering/benchmark_flow.py \
  --events 96 --iterations 5 --replacements 66 --width 80 --height 24 \
  --max-frame-ms 1000 --max-peak-kib 65536 --max-retained-kib 1024
```

## Remaining limitations and accompaniment assessment

Terminal output is an editing proof, not publication engraving. Fixed-scale
collisions are diagnostics rather than silently nonlinear spacing. The public
pitch projection currently supports treble and bass clefs. Malformed source
measures, inaccurate pickups, lesson selection, and grading remain consumer-owned.

The optional accompaniment extraction was assessed but is not part of this
notation handoff. `NotationScore` has no canonical tempo map, repeat traversal,
or performance-option contract, while Oud's current MIDI projection depends on
application records. A future pure projection must first add explicit tempo and
bounded-repeat semantics, then return timed events with stable staff/voice/source
IDs. MIDI serialization and TiMidity process ownership must remain separate.
