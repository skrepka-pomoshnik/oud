# MusicXML support

MusicXML is Oud's default save format (`TODO.md` `C16`). This page records what
Oud writes and reads, checked on 2026-09-29 against the W3C schema and
examples. It answers one question: does a piece survive a save and a reopen,
and what happens to files that other programs wrote.

## Reference and checks

- Schema, examples, and test files: <https://github.com/w3c/musicxml> (MusicXML
  4.1). Oud writes `score-partwise` version 3.1 with the 3.1 DOCTYPE.
- **Schema validation.** `tests/test_musicxml_schema.py` validates Oud's output
  for every repo TAB file, a layered score, and an edge-case piece with
  `xmllint --schema`. It skips unless `xmllint` is installed and
  `MUSICXML_SCHEMA_DIR` names the `schema/` folder of the W3C repository:

  ```bash
  git clone --depth 1 https://github.com/w3c/musicxml
  MUSICXML_SCHEMA_DIR=$PWD/musicxml/schema uv run pytest tests/test_musicxml_schema.py
  ```

  The test copies the schema and rewrites its two `musicxml.org` imports to the
  local files. Result: all output validates. All 11 official examples
  (`docs/src/data/examples/musicxml`) validate with the same setup, so the check
  can fail.
- **Meaning, not only shape.** Every exported pitch equals the tuning plus the
  fret (198 notes of `examples/triste.tab`, 0 wrong), string 1 is the highest
  course, `staff-tuning line 1` the lowest line, and measure lengths add up.
  The official `tutorial-tablature.musicxml` reads back with the right strings,
  frets, rhythm, and tuning.

## What Oud writes

One part, `Lute`: clef `TAB` line 5, `staff-details` (`staff-lines`,
`staff-tuning`, `show-frets="letters"` for French), tempo as `metronome` and
`sound`, time signature (with `common`, `cut`, and `single-number` symbols), and
each chord as notes with `technical/string` and `technical/fret` plus the
sounding `pitch`. Facts MusicXML has no element for go to
`identification/miscellaneous` (`oud-style`, `oud-author`, `oud-tuning`), and
`encoding/software` is `Oud`; that mark makes a file reopen as a native
document. Notation staves of an imported score are further parts (pitch, rhythm,
rests, ties, lyrics, slurs and fermatas).

## Round trip of Oud's own files

Status of each field after write → read, from `tests/test_musicxml_roundtrip.py`
and a bar-by-bar probe.

| Field | Status | Notes |
|---|---|---|
| Chords, strings, frets, courses 7+ | Supported | |
| Rests and dotted values, 2 to 128th | Supported | |
| 256th notes | Partial | 480 divisions cannot hold 7.5, so the value is off by half a division |
| Time signatures (numeric, `C`, `C\|`, single number) | Supported | |
| Tuning, tempo, style, author, title, composer | Supported | |
| Repeat start `.:`, end `:.`, both `:\|:` | Supported | Fixed 2026-09-29: the start repeat was written into the next measure, so it moved one bar later on every save |
| Volta endings | Supported | Start on the first bar's left barline, stop on the last bar's right barline (added 2026-09-29) |
| Barline styles (`\|\|`, `\|.`, `:`, blank) | Supported | `\|.` was written as a plain barline until 2026-09-29 |
| Fermata on a bar | Supported | Written on the first note |
| Dynamics | Supported | Known dynamics as `dynamics`, other text as `words` |
| Key signature | Lost | Only the piece-level key is written, never a bar's; not read |
| System breaks | Lost | Neither written nor read |
| Empty bar | Supported | Written as a whole-measure rest (`rest measure="yes"`, in the meter in force); a foreign measure rest also reads as an empty bar |
| Slurs, ties, holds, ornaments, annotations, highlights | Lost | Editor-side marks: never written, in MusicXML or in `.tab`, and the save says nothing |
| Tuplets | Lost | No model: not written; the `:tuplet` command only adds a text mark, which is lost too |
| Notation staves of an imported score | Partial | Pitch, rhythm, rests, ties, lyrics, slurs, fermatas and beams are kept; fingerings, harmonics, ornaments, clefs and keys are not |

## Reading files from other programs

All 18 W3C samples load without an error. Dropped notes are reported as an import
warning (`MusicXML: N notes without tablature were not read`); it does not stop
`oud convert`.

| Content | Status | What happens |
|---|---|---|
| Tablature part (`string`, `fret`, tuning, `show-frets`) | Supported | Read exactly (`tutorial-tablature.musicxml`) |
| Standard and TAB staves in one part, or in two parts | Supported | The part or staff with `string`/`fret` notes is the tablature |
| Standard notation without tablature | Lost | Bars open empty (`tutorial-chopin-prelude`: 27 notes, 0 chords); the import warns with the note count |
| Other parts of a multi-part score | Lost | Ignored; counted in the warning (Oud's own extra parts are read) |
| Tuplets (`time-modification`) | Partial | Read by their written value (three triplet eighths are three eighths, so the bar reads 5/8 and shows the meter difference); the import warns. It used to read dotted 16ths and measure 17/32 |
| Grace notes | Lost | Not read (they used to merge into the main chord); the import warns with the count |
| Two voices | Partial | Voices merge into chords; a note lasts until the next onset, so a held bass loses its length |
| Keys, segno/coda | Lost | Not read, no warning |
| Ties, slurs, hammer-on, pull-off, bend, slide, harmonic, fingering on tab notes | Lost | Not read, no warning |
| Repeats | Supported | Forward, backward, and both |

## Next steps

`TODO.md` `C17` holds what is left: editor marks (slurs, ties, holds,
ornaments, annotations, highlights), tuplet timing, per-note durations in
polyphony, standard notation from other programs, and tab techniques. Until
then a save names the marks it cannot keep, and an import names the notes it did
not read.
