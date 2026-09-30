# MusicXML fixtures

- `guitar_study_am.musicxml` is an original classical-guitar study written for
  Oud's tests (GPL-3.0-only, like the repository). It uses the layout MuseScore
  and Guitar Pro export: one part with a notation staff and a TAB staff, two
  voices (a held bass under eighth-note arpeggios), a tie across a barline, a
  pull-off, a natural harmonic, a dotted chord, a grace note, a triplet, a
  fermata, a repeat with two endings and a closing barline. It validates against
  the W3C MusicXML 3.1 schema. It is not an excerpt of any published work.
- `minimal_score_2bars.musicxml.norm` and `galliard_2bars.musicxml.norm` are
  normalized exports of `tests/fixtures/tab/minimal_score.tab` and of the
  hand-built FT3 galliard in `tests/helpers_ft3.py`.
