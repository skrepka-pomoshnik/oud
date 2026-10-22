# Gerbode coverage checkpoint, 2026-10-22

The local preserved set currently contains 787 distinct FT3 payloads across
`tests/fixtures/ft3/corpus/` and `downloads/gerbode/ft3/`, deduplicated by SHA-256.
All 787 load and generate LilyPond source. The semantic audit finds no residual
note/vocal bits, unknown source records or import warnings in this set.
There are 371,483 decoded tablature notes; 383 scores use more than six courses.
These results establish neither complete FT3 decoding nor visual parity with
Fronimo. In particular, zero residual bits does not prove correct onset,
pitch, staff mapping or layout interpretation.

The first terminal viewport renders at both 80x24 and 120x40 for 775 files:
1,550 nonempty views within their bounds. Twelve files are rejected at both
sizes by the strict notation adapter. Unmatched tie targets occur in
`disperate_speranze_S`, `come_raggio_del_sol_D`, `sonata_CM_01_moderato`,
`sonata_CM_02_minuetto`, `disperate_speranze_4`, `rondeau_130` and
`passacaille_B`. Conflicting durations in a grouped event occur in
`come_raggio_del_sol_G`, `13_dowlands_adieu_TB`, `almain_BT`,
`ecce_quam_bonum_BT` and `milano_041_parts`. These remain unsupported canonical
projections; the audit does not suppress their errors or invent tie targets.

The 60-file PDF sample compiles completely: 46 reference page counts match,
37 exact system counts match, and 42 are within one system. The sample is the
first 60 locally available pairs in the fixed `batch2.json` order, not a random
sample or a substitute for inspecting mixed and notation-only scores.

## Corrections in this checkpoint

- LilyPond output specifies each recorded course when display and source
  tunings agree. Equal pitches on different courses and unisons retain their
  source choices. An explicit target tuning that differs retains the existing
  pitch-reassignment behavior.
- Single-note durations precede course and fingering attachments, as required
  by LilyPond syntax. Chord attachments remain inside the chord.
- The default French fret table covers the editor's full alphabet, including
  frets 11, 12 and 14. The audit found 66 notes at these frets; the old
  eleven-label table made LilyPond warn and print a dot. User-supplied fret
  labels remain explicit overrides.
- The PDF comparison tool applies a source's declared tuning and style before
  export, rather than applying default settings to every source.

The original course/unison tests failed before the course fix. A high-fret
fixture reproduced the missing-label warning with both LilyPond 2.24 and 2.26;
the same fixture now exercises correct course syntax, unisons, high frets,
fingerings and additional bass courses. The four curated LilyPond digests were
updated for the intentional source change. Their semantic, terminal, TAB and
MIDI goldens remain unchanged.

## Reproduce local checks

```bash
uv run python -m scripts.corpus.audit tests/fixtures/ft3/corpus
uv run python -m scripts.corpus.audit downloads/gerbode/ft3
uv run python -m scripts.corpus.render_compare downloads/gerbode/batch2.json \
  --limit 60 --jobs 2 --json /tmp/gerbode-render-report.json
```

The two audit commands count their files separately, including duplicates;
787 above is their combined checksum-deduplicated count. The batch manifest,
FT3 files and reference PDFs are local ignored inputs, never redistributed.
Reference comparisons measure page/system counts, not musical correctness.
PDF bar counts are estimates and can mistake meter changes for short bars or
miss barlines crossed by other ink.

## Remaining reference differences

Validation at this checkpoint: 2,217 tests pass, 23 are skipped, and Petrucci
coverage is 95.52%. Architecture, Ruff lint/format and Ty checks pass. This
includes warning-free 2.24/2.26 compilation of the original course/high-fret
microcase. The baseline MusicXML module-size failure was resolved by extracting
measure marks under the existing `oud.exports.musicxml` import path.

The generated `57_mrs_vaux_jig_8C` page was inspected beside its reference PDF.
It compiles, but its opening pickup/meter placement, rhythm signs, beam groups,
fret-letter shapes and bass-course presentation still differ. These require
source and engraving evidence before claiming Fronimo parity.
The first source record also falls back to scanning because its initial object
does not frame as an ordinary item-count sequence. Its opening event boundaries
and durations therefore need decoder investigation, not just optical changes.

Authored break recovery also remains partial: the previous 311-file audit
matched every break in 149 files. Equal layout-tail values can span adjacent
systems, and mixed scores do not yet use that heuristic. Do not insert guessed
breaks merely to improve aggregate page counts.

The open C9-C12 items in `TODO.md` retain the broader decoding, MIDI, mixed
staff registration and publication acceptance work. Experimental braille and
block renderers are not a prerequisite for those fixes.
