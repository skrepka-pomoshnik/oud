# FT3 source evidence

Support decisions must distinguish documented conventions, observed binary
structure and unconfirmed interpretations. A clean residual-bit audit does not
establish correct music or layout.

## Gerbode annotations

[Gerbode's format conventions](https://www.lutemusic.org/fronimo_formats.html)
document `instrumentation:` as an alternative spelling of `ensemble:`. The
parallel notation mapper accepts either spelling; an explicit `ensemble:` takes
precedence when both exist. Tests cover independent voices and distinct staffs
in both tablature-first and notation-first serialization orders. The focused
regressions and full quality gate pass; validation details are below.

The same documentation distinguishes the complete ensemble from the `part:`
selection in a particular file. Its labels describe instruments or voices, not
a guaranteed physical staff order. Missing labels therefore must not be
replaced by invented voice assignments merely because record counts divide.

## Notation attributes: direct keyboard-handler evidence

Static inspection of the official application, combined with its bundled help,
disproves the former interpretation of low-word `0x8000` as an incoming tie.
The note-attribute getter at virtual address `0x408780` returns a 32-bit word
for notation. Its setter at `0x408860` stores all four bytes. Individual bits
must therefore be distinguished from the multi-bit attribute tag.

| Documented control | Handler evidence | Meaning in the attribute word |
| --- | --- | --- |
| `g`, grace note | `0x407B56`, toggles at `0x407B9F` | Tag `0x8000`, tested under mask `0xF8000` |
| `h`, hidden note/rest | `0x407C2D`, toggles at `0x407C6A` | Independent bit `0x100000` |
| `a`, courtesy accidental | `0x407C7B`, toggles at `0x407CBA` | Independent bit `0x80000000` |
| `e`, editorial accidental | `0x407CCD`, assigns at `0x407D3C` | Tag `0xC8000`, under the same mask |
| `r`, reversed stem | `0x407D4A`, toggles at `0x407D6A` | Independent bit `0x800000` |

The `g` handler permits toggling when that tag is either zero or `0x8000`;
it does not simply test whether bit `0x8000` is set. The editorial-accidental
tag also contains that bit and must not be interpreted as a grace note.
The getter/setter evidence describes the application's in-memory attributes;
the decoder's serialization framing must still be checked against it before
equating individual wire bytes with these fields.

This distinction fits the conflicting reference observations. The first
`passacaille_B.ft3` event was decoded as low word `0x8010` and upper word
`0x0003`: combining them gives `0x00038010`, whose masked tag is `0x38000`, not
the grace tag. Its PDF shows a full-sized note with a bowing mark. Conversely,
Abel's minuet has a small note decoded with low word `0x8000` and upper word
`0x0080`: the combined tag remains `0x8000`, with the reversed-stem bit set.
These are consistency checks, not yet validated decoder corrections. The exact
meaning of the other sign tags, including `0x38000`, remains to be decoded.

The decoder now combines the two serialized 16-bit words to recognize exactly
the grace tag, reads courtesy accidentals from the high-word flag and no longer
infers incoming ties from the low-word sign bit. Original attribute words
remain available on the imported event. Focused regressions distinguish grace,
ordinary and other sign tags, courtesy flags, same-pitch neighbors and the
timeline of an initial grace note. These regressions now pass. Corpus
expectations distinguish Sandrin's one courtesy flag from fifteen editorial
tags, and Lully's former inferred tie from its grace note. No source checksum
or render/export golden hash was changed for these semantic corrections.

Additional static evidence needs integration rather than another flag guess:
the `f` and `s` handlers assign `0x1000` and `0x2000` at `0x4078FA` and
`0x407923`, while the beaming handler manipulates low bits `0x0002/4/8`.
The dot handler cycles between `0x0010`, `0x0020` and no dots. These findings
must be reconciled with key-aware pitch normalization and written-duration
decoding; the current `0x0002`-as-sharp interpretation is not established by
the application evidence.

Real source spans still need decoding; a same-pitch neighbor alone does not
establish a tie. Editorial-accidental tags, hidden notes/rests and reversed stems
still need model/rendering/playback integration. Hidden notes must preserve
their time while remaining silent in MIDI, as the bundled help specifies.

The help's `ID_EDIT_ADD_LAYER.htm` also specifies at most four independent
notation layers per staff; each layer is monophonic except for equal-duration
chords. A serialized lane is not automatically a separate staff, nor does a
missing ensemble label establish that several lanes are voices of one staff.

## Fronimo documentation access

The [official Fronimo site](https://sites.google.com/view/fronimo/home) links its
distribution through a public Google Drive folder. The locally retrieved
`Fronimo-3_0 b19 r121.exe` identifies Clickteam in its installer stub; neither
7-Zip nor the standalone Inno Setup extractor could unpack the installer.
The block and file-table description in
[cicdec](https://github.com/Bioruebe/cicdec) allowed bounded extraction of
`Fronimo.chm` and the complete application variant for static inspection. The
second file table describes an update variant and was not used for application
inspection. No Fronimo executable was run or installed. All downloaded and
extracted material remains outside the repository; do not redistribute it as
test fixtures or copy the proprietary help text into the project.

SHA-256 provenance for the observed addresses and help contents:

| Artifact | SHA-256 |
| --- | --- |
| Installer | `63dd15b6027a2af7ae5f27da44b8b30517591a27a67367b4d12b1453231cee7c` |
| Complete application variant | `65f433a5a271161165037506bd8cf1c5baebbdcb464da7e809da2ac80261aac1` |
| Bundled help | `f837d3799d25881b87bf5c27cb5663c53ff4f84b74165c6f79c9f809f8261eec` |

## Note-entry contract and validation

`apply_note_input` now allows a grace group to share an onset and voice with
one principal note or rest. Grace events keep insertion order before the
principal even when entered after it. Timed-event collisions still fail
atomically. Chord entry prefers the principal by default; explicit grace style
selects an unambiguous grace target, and multiple grace targets are rejected
rather than guessed.

The small collision regressions failed before the API fix. Seven grace-input
edge cases now pass, and the 100-score corpus test still reconstructs canonical
scores by exact equality. Its accepted notation count rises from six to eight;
Rossi and Caldara no longer fall back to the tablature-only reconstruction path.

The full gate passes with 2,263 tests, 23 skips and 95.52% Petrucci coverage:

```bash
PYTEST_ADDOPTS='-n 2 --dist loadfile --durations=10' ./scripts/quality.sh
```

The preserved-set audit loads and exports all 787 distinct cached payloads;
785 render their first viewport at both terminal sizes. Caldara G and Milano
parts still fail strict grouped-duration validation. Compiled-PDF inspection
also leaves source clefs, grace export, pitch/beam interpretation and colliding
annotations open; see `gerbode-coverage.md` and `TODO.md`. The current semantic
residual audit examines the low notation word only, not all upper-word tags.
