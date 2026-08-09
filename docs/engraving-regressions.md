# Engraving regression provenance

`corpus/engraving-quality-matrix.json` is the shared acceptance inventory for
Petrucci's terminal proof renderer and the LilyPond publication exporter. Each
case records one semantic feature family, the proof-rendering contract, the
publication-export contract, and the exact upstream regression family whose
quality invariant was translated. Oud does not copy upstream fixtures or claim
pixel identity; it adopts their small, executable failure cases.

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

Petrucci keeps small typed fixtures that reproduce transferable engraving
invariants. It does not copy or vendor LilyPond or MuseScore fixture files.

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

The corresponding Petrucci tests assert semantic roles, bounded geometry,
continuation segments, collision freedom, and stable source ownership. They do
not assert LilyPond or MuseScore pixels because the terminal proof renderer has
a different output contract.

Upstream references:

- <https://github.com/lilypond/lilypond/tree/master/input/regression>
- <https://github.com/musescore/MuseScore/tree/main/src/engraving/tests>
