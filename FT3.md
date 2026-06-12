# FT3 Reverse-Engineered Specification

This file documents what `oud` currently knows about the FT3 format from local
corpus analysis, parser work, and regression tests.

This is not an official Fronimo specification. It is a practical,
reverse-engineered description of the subset we currently import.

This document records the model we can justify from our own importer, corpus
analysis, and regression tests.

Status labels used below:

- `Confirmed`: strongly supported by corpus behavior and tests.
- `Inferred`: strongly suggested by corpus patterns, but still partly heuristic.
- `Heuristic`: we currently reconstruct behavior because the encoding is not yet
  fully decoded.
- `Unknown`: still not deciphered well enough.

## 1. Scope

Current FT3 support in `oud` covers:

- metadata/header extraction
- tablature bars and notes
- barline/repeat/system-break header hints
- structured vocal text records
- raw mixed-score note/text bars as imported auxiliary staves
- partial vocal note decoding
- partial FT3 per-note extras decoding

Main implementation:

- [oud/core/ft3.py](oud/core/ft3.py)
- [oud/core/ft3_text.py](oud/core/ft3_text.py)
- [oud/core/ft3_extras.py](oud/core/ft3_extras.py)
- [oud/core/key_signature.py](oud/core/key_signature.py)

Main regression coverage:

- [tests/test_ft3.py](tests/test_ft3.py)
- [tests/test_ft3_text.py](tests/test_ft3_text.py)

## 2. File-Level Structure

### 2.1 Compression

`Confirmed`

FT3 files may be:

- plain binary FT3
- gzipped FT3

Detection is by gzip magic `1f 8b`.

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `read_ft3()`

### 2.2 Chunk Separation

`Confirmed`

The parser splits major FT3 body sections using the byte delimiter:

```text
03 80
```

This is used to separate:

- metadata-ish header blocks
- `CBar` records
- FT3 text records

This is how the current importer discovers record boundaries.

## 3. Header and Metadata

### 3.1 `CPiece`

`Confirmed`

`CPiece` marks the header area.

Two observed forms:

1. length-prefixed short text
2. embedded RTF blocks

Current extraction behavior:

- tries to find RTF blocks first
- strips RTF control syntax
- falls back to short text extraction
- if title is still missing, uses filename stem

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `extract_text()`
- [oud/core/ft3.py](oud/core/ft3.py)
  `_extract_cpiece_blocks()`
- [oud/core/ft3.py](oud/core/ft3.py)
  `_strip_rtf()`

### 3.2 Metadata fields

`Confirmed`

Current metadata extraction recognizes section-style annotations in the metadata
blob after `CPiece`, including fields like:

- title / subtitle
- composer / author / arranger
- footnote
- source / editor / comment
- key
- type
- difficulty
- ensemble
- instrumentation
- part
- publisher / volume / page

The importer also canonicalizes:

- `con` -> appended into `source`

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `_parse_section_annotations()`
- [oud/core/ft3.py](oud/core/ft3.py)
  `_canonicalize_metadata_fields()`
- [oud/core/ft3.py](oud/core/ft3.py)
  `_apply_annotations()`

### 3.3 Footnote decomposition

`Heuristic`

The current importer splits `footnote` into:

- source
- editor
- comment

using multi-space separators.

This works for the local corpus, but is not guaranteed to be official FT3
structure.

## 4. Bar Stream and `CBar`

### 4.1 Bar body start

`Confirmed`

Real bar parsing starts at the first `CBar` marker, not from the earlier file
bytes. This avoids CPiece bytes polluting the first bar.

### 4.2 Mixed-score body layout

`Confirmed`

In some FT3 files, the `CBar` stream is not only tablature bars. It may contain:

- raw non-tab bars first
- tab bars after that

When the stream matches:

```text
raw raw raw ... tab tab tab ...
```

with equal prefix/suffix lengths, `oud` treats it as:

- raw mixed-score prefix
- parallel tab suffix

This is how duet/mixed vocal files like `now_o_now` are aligned.

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `_parallel_mixed_score_prefix_count()`
- [oud/core/ft3.py](oud/core/ft3.py)
  `_parallel_raw_bar_targets()`

## 5. Tablature Bar Binary Layout

### 5.1 Bar header region

`Confirmed`

Current tablature bar parsing assumes:

- the first 32 bytes are bar header / control area
- note/chord scan begins at offset `32`

Compact view:

| Offset | Meaning | Status |
| --- | --- | --- |
| `0` | time-signature / repeat / barline / system-break bits | Confirmed subset |
| `1` | repeat / barline bits | Confirmed subset |
| `8` | denominator for explicit `n/d` meter when byte0 says custom meter | Confirmed |
| `9` | numerator for explicit `n/d` meter when byte0 says custom meter | Confirmed |
| `32..` | chord + note stream | Confirmed |

### 5.2 Chord record layout

`Confirmed`

At scan position `ptr`, a chord header is recognized when:

- `bar_data[ptr + 4]` / `bar_data[ptr + 5]` look like a note starter
- and `note_type = bar_data[ptr] + 2` maps to a known denominator

Decoded chord fields:

- `note_type = bar_data[ptr] + 2`
- dotted if `bar_data[ptr + 1] & 0x10`
- grid flags:
  - `0x02` -> `start`
  - `0x04` -> `mid`
  - `0x08` -> `end`

Chord header width currently assumed: `4` bytes.

Compact layout:

| Relative byte | Meaning |
| --- | --- |
| `0` | rhythm code; `note_type = byte + 2` |
| `1` | dotted + grid flags |
| `2..3` | currently unused by tab chord import |

### 5.3 Note record layout

`Confirmed`

Each following note is read in `5`-byte groups.

For main-course notes:

- byte 0: string byte
- byte 1: fret byte
- bytes 2-3: FT3 extras bitfield
- byte 4: additional note flags / bass discriminator

Main-course decoding:

- strings `0x02..0x07` map to strings `1..6`
- fret byte:
  - ASCII `0..E` style digits for numeric frets
  - ASCII `a..z` for French letter frets

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `parse_bar()`

Compact layout:

| Relative byte | Meaning |
| --- | --- |
| `0` | string/course byte |
| `1` | fret / bass-course discriminator |
| `2` | FT3 extras low byte |
| `3` | FT3 extras high byte |
| `4` | extra flags / bass discriminator |

### 5.4 Bass-course decoding

`Inferred`

Observed special handling for byte 0 == `0x08`:

- one pattern maps to string `7`
- another maps to strings `8+` with numeric course bytes
- another pattern maps to string `8`

Current decoder handles several corpus-backed bass encodings, but this part is
still not fully generalized.

## 6. Bar Header Markers

### 6.1 Repeats and double bars

`Confirmed`

Current reverse-engineering of header bytes:

- byte1 bit `0x10` -> left repeat dots
- byte0 bit `0x10` and/or byte1 bit `0x02` -> right repeat dots
- byte0 bit `0x80` and/or byte1 bit `0x01` -> explicit double barline

Current mapping:

- left only -> `.:`
- right only -> `:.`
- both -> `:|:`
- double barline -> `||`

Bit summary:

| Byte | Bit | Meaning |
| --- | --- | --- |
| `0` | `0x10` | right repeat dots |
| `0` | `0x40` | forced system break |
| `0` | `0x80` | explicit double/closing bar |
| `1` | `0x01` | explicit double/closing bar |
| `1` | `0x02` | right repeat dots |
| `1` | `0x10` | left repeat dots |

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `_parse_bar_markers()`

### 6.2 System break hint

`Confirmed`

Header byte0 bit `0x40` currently acts as a forced system break hint.

Current mapping:

- `bar.system_break = True`

This feeds current layout/reflow logic.

### 6.3 Additional header bits

`Unknown`

Byte0 bit `0x20` is known to exist in the corpus but is not yet decoded.

Current behavior:

- importer warns that additional bar header markers exist
- only repeats, double bars, and system breaks are currently decoded

## 7. Time Signature Encoding

### 7.1 Explicit FT3 time signature decoding

`Confirmed subset`

`parse_time_signature(bar_data)` decodes explicit meter from bar header bytes.

Supported current symbolic outputs include:

- `C`
- `C|`
- `O`
- fractions like `3/4`

Current byte mapping:

| `bar_data[0] & 0x7f` | Meter |
| --- | --- |
| `0x01` | `C` |
| `0x02` | `C|` |
| `0x03` | explicit triple meter; current parser stores `3/4` |
| `0x06` | custom fraction using bytes `9/8` as `num/den` |

See:

- [oud/core/ft3.py](oud/core/ft3.py)
  `parse_time_signature()`

Important nuance:

- older reverse-engineering notes disagree on whether this code is “single
  number 3” or mensural triple.
- current parser stores it as `3/4`, because that is the clearest internal
  representation and matches the local corpus behavior better than symbolic `O`.

### 7.2 Filling missing meters

`Heuristic`

If bars have no explicit time signature, `oud` fills it from:

- explicit neighboring bars
- bar duration sums

Current sum-based inference:

- `1.5 quarter beats` -> `O`
- `2.0` -> `C|`
- `4.0` -> `C`

This is corpus-based recovery, not confirmed FT3 structure.

## 8. FT3 Text Records

FT3 text records are the hardest part of the format.

Two major classes are currently handled:

- `ascii fallback`
- `structured text records`

### 8.1 Row splitting

`Confirmed`

Structured FT3 text records use:

- `CR` (`0x0d`) as logical row separator

Rows may contain:

- printable ASCII text
- control bytes `0x01..0x1f` that act as horizontal anchors

Practical rule:

- split row on `CR`
- within a row, printable bytes build a token
- control bytes reset x-position / anchor

### 8.2 Structured row kinds

`Confirmed`

Current classifier recognizes:

- `vocal`
- `lyrics`
- `editorial`
- `font`
- `control`
- `unknown`

This classification is stored in `ImportedTextRow`.

### 8.3 ASCII fallback

`Heuristic`

When text does not decode as a structured record, importer falls back to line
heuristics:

- melody-like line detection
- lyric-like line detection

This path is intentionally marked approximate and emits warnings.

### 8.4 Structured vocal row

`Inferred`

The first structured row may encode explicit vocal melody.

Current decoder assumes:

- first byte encodes first pitch row value
- next 4 bytes encode first-event flags
- subsequent `7`-byte note records may follow:
  - `0x01`
  - note-type code
  - row value
  - flags
  - additional bytes

Current note-type code mapping:

- `0x33` -> half
- `0x34` -> quarter
- `0x35` -> eighth

This is still not a full FT3 vocal-note spec, but it is stable enough for
current corpus import.

Compact layout for the currently decoded subset:

| Byte range | Meaning |
| --- | --- |
| `0` | first note row value |
| `1..4` | first note flags |
| repeated `7`-byte groups | more note events |
| trailing `2` bytes | event-count-like value, used as a sanity check |

Supported subsequent event group:

| Relative byte | Meaning |
| --- | --- |
| `0` | must be `0x01` |
| `1` | note-type code (`0x33`, `0x34`, `0x35`) |
| `2` | row value |
| `3..4` | flags |
| `5..6` | currently opaque |

### 8.5 Vocal pitch mapping

`Inferred`

Vocal pitch rows map to letter pitches using:

```text
d e f g a b c
```

with octave suffixes added by row count.

Current implementation:

- [oud/core/ft3_text.py](oud/core/ft3_text.py)
  `_vocal_pitch_token()`

### 8.6 Lyric rows with control-byte anchors

`Confirmed`

Control bytes in structured lyric rows act as x-position anchors.

Current importer tokenizes these rows by:

- treating printable bytes as token text
- treating low control bytes as horizontal anchor resets

This is the basis for multi-verse reconstruction in raw vocal files.

## 9. Raw Mixed-Score Record Kinds

`Confirmed`

Non-tab `CBar` chunks are currently classified as:

- `barline-raw`
- `note-staff-raw`
- `note-lyric-raw`
- `text-score-raw`
- `comment-rtf-raw`
- `unknown`

Current meaning:

- `barline-raw`: mostly meter/repeat/system metadata
- `note-staff-raw`: note-staff-like chunk with little/no text
- `note-lyric-raw`: note-staff plus lyric payload
- `text-score-raw`: text-heavy raw score record

These feed `ImportedScore` rather than the tab editor core.

Classifier rule of thumb:

| Kind | Trigger |
| --- | --- |
| `barline-raw` | parsed bar has meter/barline/repeat but no tab notes |
| `note-lyric-raw` | raw payload has note markers and text |
| `note-staff-raw` | raw payload has note markers but little/no text |
| `text-score-raw` | raw payload has text but no note markers |
| `comment-rtf-raw` | raw payload contains RTF/font data |

## 10. Imported Score Model

`Confirmed`

Mixed/non-tab FT3 data is preserved in:

- `ImportedScore`
- `ImportedStaff`
- `ImportedBarContent`

Current imported staff kinds:

- `note`
- `lyrics`
- `comment`
- `barline`
- `unknown`

This is the current staging area for non-tab FT3 parity work.

## 11. Vocal Accidental Handling

### 11.1 Explicit accidental bits

`Confirmed`

Current vocal accidental flag handling:

- `0x1000` -> flat
- `0x0002` -> sharp
- `0x2000` -> natural, except in raw fallback mode

### 11.2 Tonal defaults

`Confirmed`

Default vocal accidentals are normalized from key signature using:

- [oud/core/key_signature.py](oud/core/key_signature.py)

Examples:

- `GM` -> `f#`
- `DM` -> `f#, c#`
- `Fm` -> `bb, eb, ab, db`

### 11.3 Raw fallback special case

`Heuristic`

In raw vocal fallback FT3, `0x2000` is currently not trusted as explicit natural.

Instead, default tonal accidental is preserved.

This was added because several raw mixed-score files sounded wrong otherwise.

## 12. FT3 Note Extras Bitfield

`Confirmed for current subset`

Per-note FT3 extras are decoded compositionally in:

- [oud/core/ft3_extras.py](oud/core/ft3_extras.py)

Currently recognized fingering bits:

- right hand:
  - `0x0002` -> thumb
  - `0x0004` -> dot1
  - `0x0008` -> dot2
  - `0x0010` -> dot3
- left hand:
  - `0x0020` -> `1`
  - `0x0040` -> `2`
  - `0x0080` -> `3`
  - `0x0100` -> `4`

Currently recognized ornament patterns:

- `0x4A00` -> left ornament `dot-left`
- `0x3400` -> left ornament `brackets`
- `0x0600` -> right ornament `#`
- `0x0C00` -> left ornament `x`
- `0x0800` -> left ornament `+`
- `0x0400` -> left ornament `#`

Unconsumed bits are stored as `residual`.

This decoder was rewritten as a compositional bitfield model rather than exact
whole-value matching.

Compact matrix:

| Bits | Meaning |
| --- | --- |
| `0x0002` | RH thumb |
| `0x0004` | RH dot1 |
| `0x0008` | RH dot2 |
| `0x0010` | RH dot3 |
| `0x0020` | LH 1 |
| `0x0040` | LH 2 |
| `0x0080` | LH 3 |
| `0x0100` | LH 4 |
| `0x0400` | LH ornament `#` |
| `0x0600` | RH ornament `#` |
| `0x0800` | LH ornament `+` |
| `0x0c00` | LH ornament `x` |
| `0x3400` | LH ornament `brackets` |
| `0x4a00` | LH ornament `dot-left` |

## 13. Duration Encoding and Legacy Normalization

### 13.1 Tablature note types

`Confirmed`

Current denominator mapping:

- `2 -> whole`
- `3 -> half`
- `4 -> quarter`
- `5 -> eighth`
- `6 -> sixteenth`
- `7 -> thirty-second`

See tests around `note_type_to_denominator()`.

### 13.2 Legacy rhythm shift

`Heuristic`

Some FT3 files in the corpus encode durations one step too fast.

Current repair:

- detect bars whose duration median implies a shifted encoding
- shift note types one step longer

This is not format structure, but a compatibility heuristic needed for real
corpus playback/rendering.

## 14. Current Unknowns

These are not yet decoded well enough to call specified.

### 14.1 Remaining bar header bits

- byte0 bit `0x20`
- any still-unclassified combinations beyond repeats/double bars/system breaks
- possible volta / first-ending / second-ending markers, if FT3 stores them in
  the same 32-byte bar header region

`oud` now has manual bar-level ending semantics (`ending_numbers`) for
playback/rendering, but FT3 import does not yet fill them automatically.

Current corpus evidence suggests `byte0 & 0x20` is not a simple standalone
repeat/volta flag:

- it often appears on otherwise empty bars
- it often appears immediately before a bar that already carries the explicit
  closing/repeat markers we do decode

So far it looks more like a boundary/meta marker class than a directly playable
repeat instruction.

### 14.2 Ties / slurs / holds in binary FT3

Current editor supports these semantically, but FT3 binary import does not yet
decode a confirmed encoding for them from bar records.

### 14.3 System/stave break hints beyond current `0x40`

We only decode one confirmed system-break hint today.

### 14.4 Raw mixed-score note-staff binary semantics

We still do not have a complete note-staff specification for:

- non-tab voices
- vocal note-staff layout data
- possible articulation/style flags in raw score records

### 14.5 Multi-verse raw vocal text semantics

This remains the biggest parser debt.

We currently reconstruct many bars successfully, but not yet with a guaranteed
general rule for all 3-verse raw files.

Examples:

- `now_o_now.ft3` is much improved, but still not edition-quality in every bar.

### 14.6 FT3 instrument/style/tuning fields outside current metadata extraction

Some header-level fields likely exist beyond what we map today from metadata
annotations.

### 14.7 Additional FT3 extras patterns

Several extras values remain only partially understood. Current decoder keeps
unknown residual bits rather than pretending full understanding.

## 15. Worked Examples

Keep these as sanity anchors when reimplementing.

### 15.1 Minimal tab bar with one quarter note

From test fixture shape:

```text
00..1f  = 32-byte header
20..23  = 02 00 00 00
24..28  = 02 61 00 00 00
```

Interpretation:

- chord header `02 00 00 00`
  - rhythm code `0x02` -> `note_type = 4` -> quarter
- note record `02 61 00 00 00`
  - string byte `0x02` -> string 1
  - fret byte `0x61` -> `a` -> fret 0
  - extras `0x0000`

### 15.2 Header marker examples

```text
80 01 -> ||               (double barline)
00 10 -> .:               (left repeat)
90 01 -> || + :.          (double barline + right repeat)
90 12 -> || + :|:         (double barline + both repeats)
40 00 -> system break     (forced layout break)
```

### 15.3 Explicit structured vocal row

This fixture decodes to `d a d'`:

```text
010000000001330500000000013308000000000400
a338d7bf610bd63f0000004000000040040000000000000000000000010003000843616e
```

Current importer interpretation:

- first note from row/flag prefix -> `d`
- next `0x01 0x33 ...` group -> `a`
- next `0x01 0x33 ...` group -> `d'`
- trailing text token -> lyric anchor text (`Can`)

### 15.4 Structured lyric control rows

Fixture:

```text
01 00 03 00 08 43 61 6e
57 61 73 06 73 68 65
49 07 65 78 2d
73 6f
```

Current result:

- verse 1: `Can she ex-`
- verse 2: `Was I so`

Meaning:

- low bytes like `0x06`, `0x07`, `0x08` act as x-anchors
- tokens are reconstructed in visual order into verse rows

### 15.5 Raw 3-verse mixed vocal example

Observed rows in `now_o_now`-like material:

```text
vocal:  ... 12 Now,
lyric:  Dear,
lyric:  Dear, 0b O
lyric:  when
lyric:  if
```

Current reconstructed result:

- verse 1: `Now O`
- verse 2: `Dear when`
- verse 3: `Dear if`

This is currently a reconstruction rule, not a fully confirmed FT3 semantic
spec.

## 16. Corpus Feature Matrix

Compact practical matrix for the local corpus:

| Feature | Status |
| --- | --- |
| gzipped FT3 | decoded |
| RTF `CPiece` title blocks | decoded |
| plain `CPiece` short text | decoded |
| tab bars / chord stream | decoded |
| French fret letters `a..z` | decoded |
| several bass-course encodings | partially decoded |
| explicit bar repeats | decoded |
| explicit double bars | decoded |
| system-break hint `0x40` | decoded |
| explicit structured vocal melody | decoded subset |
| structured lyric rows | decoded subset |
| editorial prose text rows | decoded subset |
| raw mixed note/text bars | partially decoded |
| 2-verse raw lyric recovery | heuristic |
| 3-verse raw lyric recovery | heuristic |
| tonal vocal accidental normalization | decoded subset |
| FT3 note extras fingering subset | decoded |
| FT3 note extras ornament subset | decoded subset |
| ties/slurs/holds in FT3 binary | unknown |
| remaining header bits beyond current set | unknown |
| full non-tab score semantics | unknown |

## 17. Reimplementation Checklist

If another person is recreating the parser from scratch, the minimum useful
implementation order is:

1. read gzip/plain FT3
2. split on `03 80`
3. parse `CPiece` title/RTF blocks
4. start bar parsing only after first `CBar`
5. implement 32-byte bar header + chord/note stream parser
6. implement header bits:
   - repeats
   - double barline
   - system break
7. implement explicit meter decoding
8. implement FT3 extras subset
9. implement structured vocal row decoding
10. implement structured lyric control-row tokenization
11. add mixed raw-prefix + tab-suffix mapping
12. only then add raw multi-verse lyric reconstruction heuristics

Rule of thumb:

- first make the confirmed subset work
- then layer heuristics explicitly
- never silently mix heuristic repairs into the confirmed binary model
## 18. What Still Needs Deciphering

If continuing FT3 reverse-engineering, the highest-value next steps are:

1. Decode remaining raw multi-verse vocal-text variants into stable verse rows.
2. Decode remaining non-tab note-staff raw bar semantics.
3. Decode remaining bar header bits beyond repeat/double/system-break.
4. Confirm whether ties/slurs/holds are stored in FT3 bar records and where.
5. Expand FT3 extras decoding from current subset to a fuller matrix.
6. Document a corpus-backed feature matrix:
   - seen
   - decoded
   - partially decoded
   - ignored

## 19. Practical Reading Rule

For now, treat FT3 as three overlapping practical subsets:

- `tab bars`: fairly well understood
- `structured vocal text`: moderately well understood
- `raw mixed score`: partially reconstructed, not fully deciphered

That model matches the actual current parser architecture and the local FT3
corpus behavior better than pretending FT3 is one uniform simple format.
