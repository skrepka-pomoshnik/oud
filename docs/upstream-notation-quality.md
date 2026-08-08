# Upstream notation quality cases

Petrucci translates behavioral invariants from mature notation projects into tests of its own public contracts. It does not copy upstream implementation code or claim support for features outside Petrucci's model.

## Pinned references

- LilyPond `v2.24.4`, notation and tablature regression inputs: <https://gitlab.com/lilypond/lilypond/-/tree/v2.24.4/input/regression>
- MuseScore `v4.6.0`, engraving duration and note tests: <https://github.com/musescore/MuseScore/tree/v4.6.0/src/engraving/tests>
- MuseScore `v4.6.0`, TablEdit round-trip data: <https://github.com/musescore/MuseScore/tree/v4.6.0/src/importexport/tabledit/tests/data>
- MuseScore `v4.6.0`, tablature visual-test scores: <https://github.com/musescore/MuseScore/tree/v4.6.0/vtest/scores>

## Translated invariants

| Upstream quality case | Petrucci coverage |
| --- | --- |
| Repeated half/double duration commands | Every whole-through-128th base duration halves and doubles reversibly, with explicit boundary errors. |
| Dotted duration entry | Zero through four dots round-trip through `NotatedDuration` and canonical `duration_notation`. |
| Default duration propagation | Omitting duration on a later entry reuses the transaction's typed duration. |
| Note pitch/TPC serialization | Typed `WrittenPitch` spelling, including double accidentals, survives entry unchanged. |
| Enharmonic ties | Ties require equal sounding pitch, while endpoint spellings remain unchanged. |
| Alternate guitar tunings | Every string/fret pair through fret 18 round-trips under standard, drop-D, lute, and extended-bass tunings. |
| Minimum fret and open strings | Open strings remain candidates unless `restrain_open_strings` is enabled. |
| Open strings in high-position chords | Open strings do not contribute to fretted-hand stretch and remain assignable. |
| Explicit/default strings | Forced string choices are exact; automatic choices are deterministic. |
| Negative fret requests | Petrucci rejects them with a stable diagnostic rather than silently recalculating or inventing data. |
| Duplicate chord pitches | Equal pitches use distinct strings; overfull chords fail without partial output. |

## Deliberate non-claims

Petrucci does not currently implement LilyPond's visual negative-fret modes, tied-tab-note hiding across line breaks, grace-note size changes, fret diagrams, or MuseScore's GUI command/undo framework. Those upstream tests are not marked as passing. Their relevant model additions should be implemented before translating their assertions.
