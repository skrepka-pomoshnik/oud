# Petrucci score-rendering plan

## Decision

Petrucci remains inside `oud` and Oud remains its primary consumer. The next
library milestone is proper standard-notation rendering for Oud's imported note
and vocal staffs. A second application such as Voce must be able to use the same
public score, layout, and terminal-painting contracts without importing Oud's
editor, FT3 parser, or tablature model.

This is not a plan for a universal music framework or an immediate standalone
package. It extracts the small rendering contract already needed by two real
consumers. Existing tablature behavior and `typeset_piece()` remain supported
while standard notation moves to the new path first.

## Current status

The reusable vertical slice is implemented: strict immutable score records,
measured system fitting, content-derived staff rows, semantic elements and
event-onset lookup, complete event-to-system locations, ASCII-safe/Unicode
terminal painting, typed feedback overlays, the Oud note/lyric adapter, and a
neutral consumer fixture. The built wheel imports without initializing curses
and includes `py.typed`. All public symbols can be resolved and the score path
can render without loading curses; portable text attributes are translated only
by Oud's `CursesScreen` adapter.

Narrow clipping preserves the complete canonical event-ID set, while only
placed events receive onset/cell coordinates. `EventLocation` still maps every
event to its staff, measure, and system. Measure numbers, endings, slurs/ties,
ornaments, fermatas, dynamics, result annotations, and lyrics use disjoint
reserved rows. Accidentals track key and measure state, including natural
cancellation and explicit/courtesy display. Numeric pitch, timing, and
confidence feedback is converted into semantic layout elements before terminal
painting rather than written over finished score cells. By default only systems
containing annotated events reserve that row; `reserve_feedback_lane=True`
keeps a stable row on every system for hosts that prefer fixed geometry during
live grading.

The FT3 adapter now normalizes same-onset chords and independent voices with
per-voice clocks, and carries meter, repeat/endings, beams, fermatas, dynamics,
observed `+` ornaments, courtesy accidentals, square editorial brackets, and
confirmed tie continuations. It remains strict about inconsistent durations,
ornaments, pitches, meter overflow, and lyric onsets. `include_lyrics=False` is
an explicit note-only migration mode, not a fallback.

This is not completion of the Oud migration. Dense independent voices still
need engraving collision rules, imported tuplets/spans and mid-score clef/key
changes remain, and the legacy vocal renderer remains active in Oud. Those
concrete release gates are tracked in `TODO.md`.

## Boundaries

The dependency direction will be:

```text
consumer score/event model
        |
        v
notation adapter -> canonical notation score
                           |
                           v
                    semantic layout
                           |
             +-------------+-------------+
             v                           v
       terminal painter             future painter
             |
             v
       semantic frame -> curses/diff/refresh
```

The generic score and layout modules use only the Python standard library. They
must not import `oud.core`, `oud.editor`, `oud.tui`, `oud.exports`, FT3 types, or
curses. Oud-specific conversion belongs in an adapter. Terminal damage tracking
and playback/cursor updates happen after immutable score layout.

## Public contract

The first stable surface will be small and explicit:

- `oud.petrucci.score`: immutable `NotationScore`, `NotationStaff`,
  `NotationMeasure`, `NotationEvent`, `WrittenPitch`, and `LyricSyllable` records.
  Every staff, measure, event, and lyric has a caller-supplied, non-empty, unique
  string ID. Onsets and durations use `Fraction`; a note event can contain one or
  more written pitches, while a rest contains none.
- `oud.petrucci.layout`: typed viewport and policy records, measured boxes, onset
  maps, complete `EventLocation` records, row allocation, system breaking, and
  immutable `ScoreLayout` output. Positioned elements retain source IDs and
  semantic roles. Coordinates are deterministic integer layout units supplied
  by the painter's metrics.
- `oud.petrucci.terminal`: display-cluster-safe painting from `ScoreLayout` to a
  `SemanticFrame`. The frame contains glyph and style planes plus element-role
  and element-ID maps. ASCII-safe and Unicode-pretty glyph policies are explicit.
- `oud.petrucci.typeset_score()`: convenience composition of layout and terminal
  painting. It returns both `ScoreLayout` and `SemanticFrame`.
- `oud.petrucci.typeset_piece()`: the existing Oud facade remains compatible. It
  delegates imported standard-notation staffs through the canonical adapter;
  the tablature path can migrate later without blocking the score renderer.

Renderer configuration is grouped into three typed values: notation policy,
viewport, and transient overlay state. Unknown or inconsistent canonical input
raises a documented validation error. There is no process-global renderer or
silent alternate representation.

## Standard-notation scope

The initial useful slice supports five-line treble and bass staffs; written
pitch and octave; rests; ledger lines; whole through 64th durations; dots;
stems; key-aware accidentals; time and key signatures; measure barlines;
measured system wrapping; and current-event highlighting. This is enough for a
proper monophonic Voce score-flow view and immediately improves Oud vocal-only
scores.

The second slice adds chords and independent voices, beam groups and partial
beams, ties/slurs with explicit system continuations, tuplets, clef/key/meter
changes, repeats/endings, fermatas, dynamics, and lyrics sharing the same onset
map as notes. These features cover Oud's mixed and polyphonic FT3 viewer cases.

Singing grades remain consumer domain data. Petrucci accepts an optional overlay
per event ID with `current`, `pending`, `hit`, `missed`, or `uncertain` state and
optional pitch error, timing error, confidence, and short annotation. Layout is
unchanged by state-only overlay updates unless feedback text requests a reserved
row. Overlays for canonical events outside the current viewport are valid and
remain unpainted; overlays for IDs absent from the score are rejected.

## Delivery sequence

### 0. Characterize and protect the boundary

1. Record the supported imports and output of `typeset_piece()` and add wheel
   smoke coverage for importing `oud.petrucci` without curses initialization.
2. Add a dependency test for the generic modules and stop exporting private
   underscore helpers through `view_model.__all__` after internal callers move.
3. Characterize current Oud tablature and note-staff snapshots before migration.

Exit gate: the new work can be added without changing current public output, and
the dependency rule fails if generic code reaches into Oud application layers.

### 1. Canonical notation and adapters

1. Add immutable score records, stable IDs, validation, and explicit errors.
2. Normalize one authoritative form at adapter boundaries; remove renderer-side
   `getattr()` fallback for each migrated field.
3. Add an Oud adapter for imported note/lyric staffs. Add a local external-
   consumer fixture with its own event dataclass to prove that `Piece` is not
   required. Voce's `FlowNote` adapter remains in Voce.

Exit gate: repeated equal pitches have distinct IDs; invalid timing, duplicate
IDs, an empty note chord, and conflicting representations fail deterministically.

### 2. Measured semantic layout

1. Build one onset map for notes, rests, lyrics, spans, and playback selection.
2. Split horizontal work into natural measurement, content-based system fitting,
   and bounded justification. Measures and forced breaks are first-class inputs;
   events crossing a break produce explicit continuation elements.
3. Allocate staff, ledger, stem/beam, span, lyric, label, and annotation rows in
   one typed row budget before positioning elements.
4. Return immutable systems and positioned semantic elements, never character
   grids. Cache layout by canonical score, metrics, viewport, and notation policy.

Exit gate: dense and sparse measures wrap from measured content at 60, 80, and
120 columns; resize keeps the active event discoverable by ID; overlay-only
changes reuse the same layout; no positioned elements overlap illegally or leave
the viewport without an explicit clipping marker.

### 3. Proper terminal score painter

1. Paint the initial standard-notation slice from `ScoreLayout` into a
   display-width-safe `SemanticFrame` with no layout decisions in the painter.
2. Preserve element IDs and roles for noteheads, rests, staff lines, ledger
   lines, stems, accidentals, signatures, lyrics, spans, and barlines.
3. Keep ASCII-safe and Unicode-pretty glyph inventories explicit and test wide
   and combining characters. Frame diffing remains a separate terminal concern.

Exit gate: text snapshots and structural assertions pass at narrow, normal, and
wide sizes; every event maps to one or more cells; repeated pitches are
unambiguous; clipping and fallback glyph behavior are deterministic.

### 4. Oud-first migration and notation depth

1. Route Oud's vocal-only and imported note staffs through `typeset_score()`;
   then migrate mixed scores while leaving tablature on its current adapter.
2. Add the second-slice notation features from real FT3 examples, one construct
   at a time, with importer, layout, semantic-frame, and LilyPond assertions.
3. Split migrated responsibilities out of `render_system.py`,
   `render_text_lanes.py`, and `render_vocal.py`; delete each fallback only after
   its source adapter emits canonical data.

Exit gate: solo tablature snapshots do not regress; vocal-only, mixed song,
four-part vocal, and duet fixtures render every staff at 80x24 and 120x40 with
aligned lyrics, stable IDs, no clipping, and no silent fallback.

### 5. Interactive overlays and second-consumer proof

1. Add typed overlay state and semantic styling for current, pending, hit,
   missed, and uncertain events. Grading values are displayed but never computed
   by Petrucci.
2. Add a score-following acceptance fixture covering repeated pitches, rests,
   ties, lyrics, playback movement, results, and resize at several positions.
3. Document a Voce adapter from `FlowNote` and renderer injection. In Voce,
   replace the global registry with an explicitly owned renderer and consume
   only Petrucci's public API.
4. Build the Oud wheel and run a clean-environment consumer smoke test. Keep the
   package in Oud until the API survives both consumers; standalone extraction
   is a later packaging decision, not part of this milestone.

Exit gate: the external fixture imports no Oud model or application module, and
Voce can attach feedback to the correct repeated note through event IDs without
parsing terminal glyphs.

## Acceptance matrix

| Case | Required evidence |
|---|---|
| Oud solo tablature | Existing snapshots and cursor maps unchanged |
| Oud vocal-only FT3 | Complete standard staff, signatures, rests, beams, and semantic IDs |
| Oud mixed lute/song FT3 | Tablature and vocal systems align; lyrics share note onsets |
| Oud four-part/duet FT3 | Every staff is reachable and voices remain distinct |
| Neutral monophonic flow | Repeated pitches, rests, active event, and measured resize |
| Interactive result flow | Current/pending/hit/missed/uncertain roles and grade annotations by ID |
| Terminal policies | Equivalent semantic maps for ASCII-safe and Unicode-pretty output |
| Packaging | Public API works from a built wheel without editor, parser, TUI, or global setup |

Each row needs both structural tests over `ScoreLayout`/`SemanticFrame` and a
small human-readable snapshot. Full-frame snapshots alone are not sufficient.

## Explicit non-goals

- Rewriting Oud's editable `Piece` model before an adapter proves the need.
- Making FT3 source-preservation fields part of the public notation model.
- Moving grading, audio, playback clocks, or UI orchestration into Petrucci.
- Promising pixel-identical print engraving or replacing LilyPond for PDF output.
- Migrating the complete tablature renderer before the standard-score path works.
- Publishing a separate `petrucci` distribution before two consumers validate
  the API.
