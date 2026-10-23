# Lyrics

Lyric events retain a zero-based stanza and source-note onset. Empty source
cells do not move later syllables to earlier notes. Repeated syllables are
musical content, not duplicates to remove.

FT3 notation records with a counted, length-prefixed lyric tail are decoded
before printable-text heuristics. Recognition uses the declared source count
or a decoded note-group count, valid Windows-1252 cells and a six-zero-byte
trailer, optionally followed by bounded closing-record metadata. CRLF separates
stanzas within a cell; missing stanza cells retain their indices. Ambiguous or
unrecognized layouts remain on the existing import path, not an invented
interpretation. The counted decoder currently supports one-byte cell lengths.
Explicitly framed annotations before the note run remain commentary. Coda
directives in that commentary still select the final stanza. Literal source
punctuation, including question marks, is retained in counted lyric cells.
An empty counted tail is still a lyric record: its binary geometry must not
be retried as printable text. Legacy fallback boundary deduplication is not
used when a vocal prefix identifies a multi-stanza reconstruction.
Numeric music-font cells remain source controls, not sung syllables. Empty
stanza slots survive assembly, selection and export; a missing first stanza
must not silently promote the second one.

Both LilyPond export paths use the same stanza-padding operation. Rest-only
bars consume no sung-note slots. An explicit extender emits a line command and
a note skip; the line command alone does not advance lyric time. Hyphens may
span empty note anchors. Underscores inside syllables denote elision and are
displayed as spaces within one syllable, not printed literally.
The Gerbode profile uses an 18-point staff for vocal scores while retaining
21.5 points for solo tablature. Long footer text wraps; identical source and
footnote text is printed once rather than twice.

Terminal settings remain `showlyrics=off|on` and
`lyricmode=first|current|all`, with `lyricverse` selecting a stanza when there
is no active playback stanza.

These contracts do not establish full Gerbode fidelity. Longer/other binary
text encodings, source-to-voice association in unusual polyphonic layouts,
cross-system continuations and reference-PDF collision/underlay comparisons
still need corpus acceptance.

Validated on 2026-10-23: the focused suite passed 189 tests with 8 skips; the
full suite passed 2,284 tests with 23 skips and no failures. Petrucci coverage
was 95.53%; Ruff lint/format, Ty and architecture checks passed. All seven
Caldara, Dowland and Bossinensis benchmark PDF pages were visually inspected,
with warning-free compilation under LilyPond 2.26 and 2.24.4. This is not a
claim of corpus-wide lyric or engraving parity.
