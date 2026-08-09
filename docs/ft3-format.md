# FT3 Reverse-Engineered Specification

This document describes the FT3 subset implemented by `oud`, based on the bundled
Gerbode corpus, binary comparisons, published PDFs, and regression fixtures. FT3
is proprietary; this is not an official Fronimo specification.

Status terms:

- **Confirmed**: repeated corpus evidence and a regression fixture.
- **Inferred**: consistent corpus/PDF evidence, but no vendor specification.
- **Unsupported**: deliberately outside the importer contract.

Implementation:

- `oud/importers/ft3.py`: stable `load_ft3`/duration facade and container orchestration
- `oud/importers/_ft3_metadata.py`, `_ft3_tab.py`, `_ft3_score.py`: metadata, tablature, and score assembly
- `oud/importers/_ft3_text*.py`, `_ft3_note_records.py`: vocal, lyric, editorial, and note records
- `oud/importers/_ft3_duration.py`, `_ft3_extras.py`: normalization, fingering, and ornament flags
- `scripts/ft3_audit.py`: corpus residual and unknown-record inventory

## 1. Container

### Compression

**Confirmed.** Files may be plain binary or gzip-compressed. Gzip is detected by
the `1f 8b` magic bytes.

### Main regions

**Confirmed.** `CPiece` starts title/metadata material and `CBar` starts the score
body. Body records are separated by:

```text
03 80
```

The importer starts bar parsing at `CBar`; bytes in `CPiece` must never be
interpreted as bar 1.

## 2. Metadata

**Confirmed for the corpus.** `CPiece` contains length-prefixed or RTF strings.
The first fields are title, subtitle, composer, and footnote. Section-style text
also supplies key, type, difficulty, ensemble, part, instrumentation, arranger,
source, editor, comment, publisher, volume, page, style, and tuning.

Unknown metadata remains in `Piece.raw_metadata`. The importer never invents a
value for an absent field.

## 3. Body Record Mapping

The `CBar` stream can contain several record shapes.

### Tablature

**Confirmed.** Ordinary records contain tablature chord/note objects. Each such
record maps to one logical `Piece.bars` entry.

### Mixed voice and tablature scores

**Confirmed.** A run of standard-note records followed by an equal-sized tab run
is parallel notation, not extra bars. A multiple of the tab-run length maps to
multiple standard staffs. This covers the bundled vocal/lute and three-voice
plus lute scores.

**Confirmed for polyphonic notation.** A visible standard staff can use multiple
parallel voice lanes. La Couperin stores two 77-record musical lanes, each with
one short non-bar padding record, followed by 77 tablature bars. Both voices map
to one labeled imported staff and retain separate source-voice provenance.

### Score-only polyphony

**Confirmed for the corpus.** When every body record is a standard-note record,
the ensemble metadata supplies staff labels and the record count divides evenly
into logical bars. `oud` maps all voices separately. Every note staff receives
one imported entry per logical bar, including rests and empty measures.

### Annotation groups

**Confirmed for the corpus.** Three Ich records have a large object index at
bytes `28..29`, marker `02 00` at bytes `30..31`, and length-prefixed edition
text such as `p`, `cresc.`, `BI`, `BII`, and `BIV`. They are annotation groups,
not tablature bars or system breaks. They attach to the following logical bar.

### Score terminator

**Inferred.** One Passacaglia record follows the final appendix bar. Its signature
starts `00 00 00 11 00 00 ff`, has no musical/text object, and is represented as
a typed `score-terminator` source record rather than a visible bar.

## 4. Tablature Bar Header

The first 32 bytes are a control/header region.

### Meter

**Confirmed subset.** `byte0 & 0x07` selects:

| Value | Meaning |
| --- | --- |
| `01` | common time (`C`) |
| `02` | cut time (`C|`) |
| `03` | triple meter (`3/4`) |
| `06` | fraction using denominator byte 8 and numerator byte 9 |

Byte 0 also carries bar and edition flags. In particular, `08` occurs alongside
`01`, `02`, and `06`; it is not part of the meter code. Masking it recovers 19
explicit meter records in 14 files in the fixed corpus, including the `3/2`
shown in the published four-part Gesualdo PDF.

An explicit meter remains active until another explicit meter appears. If a
file has no explicit meter, duration sums provide a conservative initial guess.

### Repeats, endings, and closing bars

**Confirmed by binary/PDF comparison.** The observed flags are:

| Location | Bit | Meaning |
| --- | --- | --- |
| byte 0 | `10` | right repeat |
| byte 0 | `20` | first ending |
| byte 0 | `40` | second ending |
| byte 0 | `80` | double/closing bar |
| byte 1 | `01` | double/closing bar |
| byte 1 | `02` | right repeat on structural boundary |
| byte 1 | `10` | left repeat |

The `20`/`40` interpretation is visible in Unquiet Thoughts, Czarna Krowa, and
La Corambona: `b0 01` closes the first ending and `c0 01` closes the second.
Earlier `oud` versions incorrectly treated `40` as a system break.

No per-system line-break flag occurs in the bundled logical bar stream.

### Object count and object type

For ordinary tab records, bytes `28..29` plus one give the top-level object
count used to stop scanning before trailing text/layout data. Standard-note
records use a marker `01 30` through `01 35` at bytes `30..31`.

## 5. Tablature Objects

### Chord header

**Confirmed subset.** A chord header is four bytes:

| Relative byte | Meaning |
| --- | --- |
| 0 | rhythm code; internal `note_type = value + 2` |
| 1 | dotted (`10`) and beam/grid (`02` start, `04` middle, `08` end) |
| 2..3 | object metadata not needed after item-count framing |

The preceding two-byte item count bounds the following notes. This prevents
standard-note rows and trailing edition text from becoming false tab notes.

### Note object

**Confirmed.** A tablature note is five bytes:

| Relative byte | Meaning |
| --- | --- |
| 0 | string/course code |
| 1 | fret or bass-course discriminator |
| 2..3 | little-endian extras field |
| 4 | additional bass-course discriminator bits |

Main courses use string codes `02..07`. Numeric and French letter frets are
accepted. Observed `08` forms select courses 7 and higher.

## 6. Structured Standard-Note Records

### Vocal event layout

**Confirmed for the corpus.** A structured vocal row starts with:

| Bytes | Meaning |
| --- | --- |
| 0 | first pitch-row value |
| 1..2 | first-event musical flags, little-endian |
| 3..4 | source layout flags, little-endian |
| following 7-byte records | additional events |
| final 2 bytes | event count plus one |

An additional event record is:

| Relative byte | Meaning |
| --- | --- |
| 0 | `01` marker |
| 1 | duration code |
| 2 | pitch-row value |
| 3..4 | event flags |
| 5..6 | source layout flags |

Full standard-note records use grouped objects. A group starts with a one-byte
note count; each note then occupies six bytes: duration, signed pitch row,
two-byte musical flags, and two-byte layout flags. Notes in one group share an
onset, so chords and independent source voices remain typed rather than being
flattened into successive notes.

Duration codes map as follows:

| Code | Internal note type | Duration |
| --- | --- | --- |
| `32` | 3 | half |
| `33` | 4 | quarter |
| `34` | 5 | eighth |
| `35` | 6 | sixteenth |
| `36` | 7 | thirty-second |

The first event omits its duration. `oud` derives it from the active meter and
the remaining event durations.

### Vocal flags

**Confirmed by corpus sequences and PDF output.** All vocal bits used by the
bundled corpus are decoded:

| Bit | Meaning |
| --- | --- |
| `0001` | secondary source voice selector |
| `0002` | sharp |
| `0004` | middle event in a beam group |
| `0008` | end event in a beam group |
| `0010` | dotted |
| `0040` | rest |
| `0100` | fermata |
| `1000` | flat |
| `2000` | explicit natural/key-default control |
| `4000` | square editorial brackets around the note |
| `8000` | courtesy accidental when combined with an accidental; otherwise tie continuation |

The first beam event has no beam bit. It is inferred by walking backward from
`0008` over any `0004` middle events. Beams and fermatas survive projection,
terminal rendering, and LilyPond export.

Layout values are not accidental flags. Their raw 16-bit value remains on the
event; the observed low selector `0a` is the printed `+` ornament, including its
`400a` and `408a` placement variants.

### Pitch and key handling

Pitch rows repeat `d e f g a b c` across octaves. Explicit flat/sharp flags take
precedence. Otherwise the imported key signature supplies the tonal default.

### Lyrics and editorial rows

**Confirmed for the corpus.** Carriage returns split rows. Printable runs are
tokens; low control bytes are horizontal anchors. Rows are typed as vocal,
lyrics, editorial, font, control, or unknown. Lyric anchors become verse-aware
`LyricEvent` objects. Font/control rows remain inspectable but are not displayed
as lyrics.

## 7. Edition Text and Sections

Length-prefixed text objects become dynamics or editorial annotations. Embedded
RTF titles inside a tab record introduce the following section. In the bundled
Passacaglia this recovers:

- the note “Original 2 bars seem too discordant. For originals see Appendix.”
- a page break after the main piece
- section title `Appendix`
- subtitle `Original bars 14-15`

Terminal layout forces a new system there; LilyPond emits `\pageBreak` and the
section marks.

Exact PDF line wrapping and page composition are Fronimo engraving output, not
logical score records observed in this corpus. `oud` therefore reflows ordinary
systems for the current terminal width.

## 8. Per-Note Extras

**Confirmed for every value used by the corpus.** The extras field composes
low-byte fingering bits with one high-byte mark:

| Value | Meaning |
| --- | --- |
| `0002` | right thumb |
| `0004`, `0008`, `0010` | right-hand dots 1, 2, 3 |
| `0020`, `0040`, `0080`, `0100` | left fingers 1, 2, 3, 4 |
| `0400`, `0800`, `0c00` | left `#`, `+`, `x` ornaments |
| `0600`, `0e00` | right `#`, `x` ornaments |
| `1000`, `1400` | right comma and apostrophe ornaments |
| `1600` | left apostrophe ornament |
| `1800` | under-note smile ornament |
| `1c00` | left parenthesis before the fret |
| `2000`, `2200` | right and left caret ornaments |
| `2400` | under-note `v` ornament |
| `2800` | under-fret hook ornament |
| `3400` | barre; composes with low-byte fingering |
| `3c00` | legacy open ninth-course form |
| `0200` | single arpeggio mark |
| `4a00`, `4e00`, `5200` | bottom, middle, top arpeggio segments |

These marks render in the terminal and are exported where LilyPond/MusicXML has
an equivalent. The original integer remains on `Note.ft3_extras`; any unconsumed
bit would appear in `ft3_extra_residual` and fail the corpus audit.
Multiple low-byte left-fingering bits are preserved compositionally (for
example, `00c0` is represented as `2+3`) rather than silently dropping a mark.

An empty standard-notation record can use row marker `0130`; rows `0130` through
`0135` are therefore notation markers. Mixed scores are lane-major: complete
notation lanes precede the complete tablature lane, and each lane contains the
same source-bar count.

ASCII-looking coordinate/control fragments can resemble the legacy melody-grid
fallback. A barline or empty standard-note record is promoted to musical events
only when its binary payload contains a valid encoded note run. Otherwise the
text remains a typed `control` row and cannot become a pitch, playback event, or
canonical Petrucci note.

## 9. Imported Score Model

`Piece.bars` is the tablature/editing projection. `Piece.imported_score` stores
decoded note, lyric, comment, layout, and future unknown staffs.

Source provenance is separate from musical bars:

```text
ImportedScore.source_records[]
  source_bar_index
  source_staff_index
  source_voice_index
  kind
  size
```

Current semantic source kinds are `note`, `note-lyrics`, `annotation-group`,
`barline`, `comment`, `layout`, `text`, `score-terminator`, and `unknown`. A
record is listed once even when it contributes both note and lyric content.

The viewer can focus each imported voice independently. LilyPond emits every
mapped standard staff rather than only the first voice.

## 10. Audit Contract

Run:

```bash
uv run python scripts/ft3_audit.py lutemusic
```

Each fixed corpus directory must report zero unresolved files, for example:

```text
Scanned 75 file(s): 0 with unresolved values or records.
```

Together the five random manifests cover 300 fixed external files. Tests
verify their paths, URLs, SHA-256 digests, and zero-unresolved result.

“Unresolved” means an unconsumed note-extra bit, unknown vocal flag, unknown
source record, or import warning. Typed source records are inventory, not debt.

## 11. Limits

- FT3 is import-only; `oud` never overwrites or writes proprietary FT3 data.
- The contract is the bundled corpus, not every historical Fronimo version.
- Exact glyph shapes, coordinates, braces, proportional spacing, and automatic
  PDF pagination belong to the engraving layer and are approximated/reflowed.
- Future unknown records remain typed as `unknown` and trigger the audit; they
  are never silently discarded or advertised as supported.
