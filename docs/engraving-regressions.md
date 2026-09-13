# Engraving regression provenance

`tests/fixtures/ft3/manifests/engraving-quality-matrix.json` is the shared acceptance inventory for
Petrucci's terminal proof renderer and the LilyPond publication exporter. Each
case records one semantic feature family, the proof-rendering contract, the
publication-export contract, and the exact upstream regression family whose
quality invariant was translated. Oud does not copy upstream fixtures or claim
pixel identity; it adopts their small, executable failure cases. The test helper
builds one deterministic source-independent fixture per case and drives both
proof and export assertions from that record.

LilyPond export uses the `petrucci` profile by default. This profile applies a
restrained movable-type hierarchy to paper margins, staff rules, barlines,
tablature noteheads, stems, and beams. `:set lyprofile=classic` selects the
minimal unstyled LilyPond layout for comparison and diagnosis.

LilyPond 2.26 is the publication baseline. LilyPond 2.24 remains a
second-grade compatibility target using the same semantics but an explicit
2.24 source declaration. Configure both choices in `config.toml`:

```toml
[settings]
lilypond = "lilypond-2.26"
lilypondversion = "2.26"
```

For compatibility testing, point `lilypond` at the older executable and set
`lilypondversion = "2.24"`. Oud never silently falls back to another binary.

Mixed scores place the vocal staff above its lyrics and tablature by default.
`lybarsperline=0` and `lysystemsperpage=0` retain automatic publication
planning; scores with eight or more simultaneous lyric stanzas use a bounded
four-bar, two-system-per-page plan so LilyPond does not compress the text into
unreadable systems. Positive values override those automatic limits. Imported
editorial cues remain registered with their source bars. Publication tablature
prints rhythm stems and flags by default; `lytabrhythm=minimal` suppresses them
without changing the terminal `tabnotation` policy.

Petrucci keeps small typed fixtures that reproduce transferable engraving
invariants. It does not copy or vendor LilyPond or MuseScore fixture files.

The standalone ASCII example in `tests/test_petrucci_voce_ascii.py` uses
`GlyphMode.ASCII`, `TerminalNoteheads(filled="*", open="o")`, and
`LayoutMetrics(event_gap=1, barline_gap=1)`. It hides pitch labels to save a row
while retaining five staff lines, stems, meter, rests, and event identities.
`barline_gap` reserves extra columns before barlines in ordinary respaced layout;
its default is zero, and fixed proportional layouts retain their exact time
coordinates. This setting does not add vertical padding.

## Experimental advanced terminal mode

### Solid blocks for Alacritty

`GlyphMode.BLOCK` uses upper/lower half blocks and full blocks rather than
braille dots. One character column is one pixel wide and two pixels high;
staff lines and musical shapes use the same continuous drawing surface.
This trades horizontal density for recognizable filled and hollow shapes.

The preview's opt-in `--spacing compact` uses minimum onset gaps, disables
justification, trims horizontal padding and the prefix reservation, and hides
the single-voice example's label. Staff spacing and musical masks are unchanged.
The reusable `NotationLayoutPolicy.compact_spacing` option removes only the
extra duration-based gaps; collision reservations, lyrics and event ordering
remain part of layout. It does not compress a fixed proportional timeline.

```bash
uv run python -m scripts.notation_preview --mode block --spacing compact --width 96 --color always --palette paper
```

```bash
uv run python -m scripts.notation_preview --mode block --width 96
```

The standalone preview defaults to plain ASCII; block mode is opt-in.
ASCII and experimental braille modes remain available. No image protocol,
external music font or application-specific Alacritty configuration is needed.
Alacritty's `font.builtin_box_drawing = true` setting, enabled by default,
covers the block characters used here; see its
[configuration manual](https://alacritty.org/releases/0.14.0/config-alacritty.html).

Block mode's `ScoreTypesetOptions.width` and `layout_width` are terminal
columns: layout receives half that width (rounded down), then painting maps
each logical column to two terminal columns. Returned layout coordinates are
logical coordinates, not screen cells. Use `cells_for` and projected pitch
cues for interaction. Viewport offsets are always terminal cells. Ordinary
text is not stretched. Other modes retain their existing coordinate contracts.

Block mode remains experimental; cross-terminal visual review is still
required. Its projection, symbol variants, and fallbacks have dedicated
regressions. A successful braille test run alone does not validate this mode.

### Braille experiment

Colour can separate the staff from musical ink without changing geometry:

```bash
uv run python -m scripts.notation_preview --mode advanced --width 64 --color always --palette ink
uv run python -m scripts.notation_preview --mode advanced --width 64 --color always --palette paper
```

The opt-in `petrucci.terminal.ansi.colour_score` serializer consumes a
`SemanticFrame`: staff rules and barlines are subdued, notes are high-contrast,
accidentals are amber, and ties/slurs have a separate colour. `--highlight b`
demonstrates event selection only, not playback. Colour is per terminal cell;
staff dots sharing a cell with a note take that note's colour.

`--color never` is the default and preserves plain text. `--color auto` colours
only a terminal destination without `NO_COLOR`; `always` explicitly enables
ANSI true-colour output, including redirected previews. Neither palette alters
the curses editor's theme or terminal configuration. Shapes remain readable
independently of colour; colouring does not establish engraving correctness.

`GlyphMode.ADVANCED` projects musical shapes onto one braille dot grid rather
than mixing font-sized music glyphs, box drawing, and braille. `GlyphMode.ASCII`
names the existing ASCII inventory; `GlyphMode.SAFE` remains supported.
The default rendering mode is unchanged.

Run the standalone, source-independent example with:

```bash
uv run python -m scripts.notation_preview --mode advanced --width 64
uv run python -m scripts.notation_preview --mode ascii --width 64
```

`NotationLayoutPolicy(compact_beams=True)` keeps simple single-voice eighth-
and sixteenth-note beams near their notes. More complex groups retain the
existing outer beam lanes. This policy is opt-in.

Advanced mode uses two dot rows per logical pitch step, while text lanes retain
full character height. Its cell coordinates intentionally differ from ASCII;
use `cells_for` for selection and the shared projected pitch-cue overlay.
Viewport offsets remain character-cell offsets. Braille drawing is clipped to
the viewport, and notehead interiors knock out staff ink at dot resolution.

Clefs, rests, noteheads, meter digits, accidentals, stems, beams and staff lines
share that grid. Text and unsupported marks retain the ordinary glyph painter;
explicit custom noteheads also retain their one-cell contract. `LayoutElement`
span `anchor_ids` preserve source event endpoints: simple complete single-note
ties sit near their heads, while chord and broken ties retain allocated lanes.

Appearance still depends on terminal braille support and line spacing. This is
experimental, not publication-quality engraving. Polyphonic curve placement,
beam slopes and a cross-font optical regression suite remain unfinished.
No image protocol or new runtime dependency is required.

## Upstream cases mirrored locally

- Partial and grace beamlets: LilyPond `auto-beam-partial.ly`,
  `auto-beam-partial-grace.ly`, and `beam-beamlet-break.ly`; MuseScore
  `src/engraving/tests/beam_data`.
- Grouped tuplets with beams: LilyPond's tuplet and auto-beam regression family;
  MuseScore `compat114_data/tuplets*.mscx` and `compat206_data/tuplets*.mscx`.
- Broken ties and slurs: LilyPond's broken tie/slur regression family;
  MuseScore `partialtie_data`, especially `repeat_barlines.mscx`.
- Endings with repeat barlines: LilyPond `bar-line-allow-volta-hook.ly` and the
  built-in repeat-barline matrix; MuseScore `barline_data`.
- Dense multi-stanza registration: Bossinensis's *Felice fu quel dì* from the
  public Gerbode FT3/PDF pair; the executable contract checks complete coda
  syllables, final-stanza scope, four systems, two pages, staff order, and
  source-bar editorial cues rather than pixel identity.

The corresponding Petrucci tests assert semantic roles, bounded geometry,
continuation segments, collision freedom, and stable source ownership. The
curated external FT3 manifest is also compiled through the 2.26 publication
backend when available. Tests do not assert LilyPond or MuseScore pixels because
the terminal proof renderer has a different output contract.

Upstream references:

- <https://github.com/lilypond/lilypond/tree/master/input/regression>
- <https://github.com/musescore/MuseScore/tree/main/src/engraving/tests>
