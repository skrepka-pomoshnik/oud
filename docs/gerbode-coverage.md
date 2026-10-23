# Gerbode coverage checkpoint, 2026-10-22

## Lyric follow-up, 2026-10-23

The checkpoint below records the earlier audit, not a rerun of the whole
preserved set. The lyric follow-up re-audited 251 cached metadata-bearing
scores, preserving source hashes and canonical note counts. Four curated
TAB, TAB-projection and MIDI hashes also remained unchanged; affected lyric
counts and terminal/LilyPond baselines were updated.

Caldara, Dowland and Bossinensis underlay was compared with reference PDFs
across all seven generated pages and terminal proofs at 80x24 and 120x40.
The three exports compile without warnings with LilyPond 2.26 and 2.24.4;
the earlier Caldara warning evidence below is historical. See `lyrics.md`
for the supported decoder boundary and `../TODO.md` for remaining work.

Final validation: 2,284 passed, 23 skipped, zero failures; Petrucci coverage
95.53%. Ruff lint/format, Ty and architecture checks pass. This does not
establish full-corpus visual parity or resolve the remaining notation issues.

## Earlier preserved-set audit

The local preserved set currently contains 787 distinct FT3 payloads across
`tests/fixtures/ft3/corpus/` and `downloads/gerbode/ft3/`, deduplicated by SHA-256.
All 787 load and generate LilyPond source. The semantic audit finds no residual
note/vocal bits, unknown source records or import warnings in this set.
There are 371,483 decoded tablature notes; 383 scores use more than six courses.
These results establish neither complete FT3 decoding nor visual parity with
Fronimo. In particular, zero residual bits does not prove correct onset,
pitch, staff mapping or layout interpretation.

The first terminal viewport renders at both 80x24 and 120x40 for 785 files:
1,570 nonempty views within their terminal-cell bounds. Two files are rejected
at both sizes by the strict notation adapter: `come_raggio_del_sol_G` and
`milano_041_parts`, both for conflicting grouped durations. Caldara has unequal
notation/tab record counts; Milano lacks the metadata needed to register its
three notation staffs. The audit does not suppress these errors or invent tie
targets. Combining fingering marks count as part of their preceding terminal
cell, not as additional columns.

The previous 60-file PDF sample compiled completely: 46 reference page counts
matched, 37 exact system counts matched, and 42 were within one system. These
counts precede the note-tag and lane-mapping corrections. The sample is the
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
- Parallel notation lanes can precede or follow tablature. Their mapped voice
  survives the structured-vocal fallback. Dowland's `13_dowlands_adieu_TB` and
  Holborne's `almain_BT` and `ecce_quam_bonum_BT` no longer collapse all notation
  into the final measure. The mapper also accepts Gerbode's documented
  `instrumentation:` alias for `ensemble:`.
- Notation attributes are interpreted as a full word: only tag `0x8000` under
  mask `0xF8000` is grace; courtesy uses the high-word flag. The low-word sign
  bit no longer invents incoming ties. Seven former strict rejections now adapt.
- The public note-input API accepts grace groups sharing an onset with a
  principal note or rest, keeps grace insertion order before the principal,
  and still rejects timed-event collisions and ambiguous chord targets. The
  100-score note-input reconstruction test retains exact score equality.

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

Synthetic regressions cover both serialization orders, independent voices,
separate staffs, padding and ambiguous lane rejection; optional tests use the
three cached tablature-first scores without fetching or redistributing them.
The former false-tie rejection subset now adapts 56 scores instead of 49.
Only Caldara G remains rejected in that fixed subset; Milano parts is in the
additional preserved download set.

Validation at this checkpoint: 2,263 tests pass, 23 are skipped, and Petrucci
coverage is 95.52%. Architecture, Ruff lint/format and Ty checks pass. This
includes warning-free 2.24/2.26 compilation of the original course/high-fret
microcase. The baseline MusicXML module-size failure was resolved by extracting
measure marks under the existing `oud.exports.musicxml` import path.

Three additional affected scores compile under LilyPond 2.26. Abel's minuet and
Holborne's Almain compile without warnings; Caldara's D aria reports two pairs
of conflicting/discarded `\\mark` events. Inspection of the minuet and Almain
pages reveals missing grace presentation, incorrect clef/register presentation
and excess ledger lines. The minuet's generated source contains no grace
commands despite decoded grace events. Successful compilation is not PDF
acceptance; the source-clef, pitch/beam-field and grace-export work stays open.

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
