# FT3/PDF parity matrix

Manual comparison with Sarge Gerbode's published PDFs, 2026-07-11 through
2026-07-19. Reference PDFs are not copied into the repository.

```bash
uv run python scripts/fetch_ft3_corpus.py corpus/ft3-regression.json
uv run oud ascii FILE.ft3 --bars 1:10
uv run python scripts/ft3_audit.py lutemusic/05_can_she_excuse
```

| Shape | Local FT3 | Published PDF | Result |
| --- | --- | --- | --- |
| Twelve-verse mixed song | `lutemusic/01_felice_fu_quel_anon.ft3` | [Felice fu quel dì](https://browse.lutemusic.org/sources/BossinensisF/v.2_1511/pdf/01_felice_fu_quel_anon.pdf) | Sixteen vocal/tab bars agree. Printable FT3 position bytes are removed and the column-major text matrix becomes twelve onset-aligned verses. The terminal uses shared vocal/tab measure boxes and clips only at its lower border. |
| Solo | `lutemusic/01_unquiet_thoughts/unquiet_thoughts_T.ft3` | [Unquiet Thoughts](https://www.lutemusic.org/sources/DowlandJ/1st_book_of_ayres/01_unquiet_thoughts/pdf/unquiet_thoughts_T.pdf) | 25 bars, meter, rhythms, notes, bass courses, repeats, and the `0x20`/`0x40` first/second endings agree. |
| Mixed | `lutemusic/05_can_she_excuse/can_she_excuse.ft3` | [Can she excuse my wrongs?](https://www.lutemusic.org/sources/DowlandJ/1st_book_of_ayres/05_can_she_excuse/pdf/can_she_excuse.pdf) | 40 aligned melody/lyric/tab bars agree; both lyric verses and imported staff focus remain available. |
| Polyphonic | `lutemusic/05_can_she_excuse/can_she_excuse_4_part.ft3` | [Can she excuse my wrongs?](https://www.lutemusic.org/sources/DowlandJ/1st_book_of_ayres/05_can_she_excuse/pdf/can_she_excuse.pdf) | Soprano, alto, tenor, and bass map to 24 complete logical bars and export as four LilyPond staffs. |
| Duet | `lutemusic/willoughby_duet.ft3` | [My Lord Willoughby's welcome home](https://lutemusic.org/composers/Lute_ensemble/Dowland/willoughby/pdf/willoughby_duet.pdf) | Two labeled 48-bar parts agree; `0x0200` is the visible chord arpeggio mark. |
| Vocal/mixed | `lutemusic/now_o_now.ft3` | [Now, O now I needs must part](https://www.lutemusic.org/sources/DowlandJ/1st_book_of_ayres/06_now_o_now/pdf/now_o_now.pdf) | 48 bars, explicit rests/accidentals, three lyric verses, vocal beams, and fermatas agree. |
| Edition marks | `lutemusic/ich_bin_eine_blume_zu_saron_T.ft3` | [Ich bin eine Blume zu Saron](https://www.lutemusic.org/composers/Buxtehude/ich_bin_eine_blume_zu_saron/pdf/ich_bin_eine_blume_zu_saron_T.pdf) | Three large records are annotation groups, not bars: `p`, `cresc.`, `BI`, `BII`, and `BIV` attach to following bars. Segmented arpeggios use `4a00/4e00/5200`. |
| Section/page | `lutemusic/32_passacaglia.ft3` | [32. Passacaglia](https://browse.lutemusic.org/sources/Piccinini/v.2_1639/pdf/32_passacaglia.pdf) | Embedded prose and RTF recover the editorial note, appendix page break, title, subtitle, and two original appendix bars. |
| Ornament | `lutemusic/ricercar_galileiG.ft3` | [Ricercar](https://www.lutemusic.org/composers/GalileiG/pdf/ricercar_galileiG.pdf) | Five right-side `x` ornaments correspond to `0x0e00`. |
| Standard notation | `lutemusic/random-75/039/grounds17.ft3` | [17th Century Grounds](https://browse.lutemusic.org/composers/Exercises/pdf/grounds17.pdf) | Four named ground sections agree. The first-event bytes split into 16-bit musical flags plus 16-bit layout data; section labels no longer create phantom high vocal flags. |
| Polyphonic mixed | `lutemusic/random-75/054/la_couperin_duet.ft3` | [La Couperin](https://browse.lutemusic.org/composers/Forqueray/pdf/la_couperin_duet.pdf) | The PDF confirms one polyphonic bass-viol staff above archlute tablature for 77 measures. Two notation voice lanes map to that one labeled staff; their two padding records are not bars. Petrucci's note-only adapter preserves all 459 canonical events and lays them out without clipping at 60, 80, and 120 columns. |
| Mixed score | `lutemusic/random-75-v2/013/13_o_sio_potesi_donna.ft3` | [O s'io potessi donna](https://browse.lutemusic.org/composers/Berchem/pdf/13_o_sio_potesi_donna.pdf) | The 59-bar lane-major body is two standard-note lanes plus tablature. Empty `0130` records remain notation bars; lyric bytes no longer become fake high-fret notes. |
| Courtesy accidentals | `lutemusic/random-75-v2/020/douce_memoire_song_sandrin.ft3` | [Douce memoire](https://browse.lutemusic.org/composers/Sandrin/pdf/douce_memoire_song_sandrin.pdf) | All 15 `a000` events are printed parenthesized naturals. `8000` therefore changes an explicit accidental to courtesy display. |
| Editorial notes | `lutemusic/random-75-v2/060/recit_de_la_beaute_double.ft3` | [Recit de la Beaute](https://browse.lutemusic.org/composers/Lully/pdf/recit_de_la_beaute_double.pdf) | Two `4000` notes use square editorial brackets. The standalone `8000` event continues the preceding same-pitch note as a tie. |
| Legacy bass | `lutemusic/random-75-v2/072/mozart_variations.ft3` | [Mozart theme variations](https://browse.lutemusic.org/composers/Mozart/pdf/mozart_variations.pdf) | The `3c00` note prints as the same double-slashed open ninth course used by the normal numeric-diapason encoding. |
| Ornament | `lutemusic/random-75-v2/074/praeludium_02.ft3` | [Praeludium 2](https://browse.lutemusic.org/composers/Mace/pdf/praeludium_02.pdf) | The sole `1600` mark is an apostrophe printed to the left of the tablature letter. |
| Layout | `lutemusic/random-75-v2/004/courant_duet_T.ft3` | [De France courant](https://browse.lutemusic.org/composers/Van_eyck/pdf/courant_duet_T.pdf) | Two 64-byte empty records change source layout coordinates and print no music; they are typed layout records rather than unknown staffs or bars. |
| Four-part meter | `lutemusic/random-75-v2/065/gesualdo_gagliarda_4.ft3` | [Gagliarda](https://browse.lutemusic.org/composers/Gesualdo/pdf/gesualdo_gagliarda_4.pdf) | All four opening records use header `0e 10` with fraction bytes `02 03`. The PDF confirms a left repeat in `3/2`: `08` is a shared header flag, while low meter code `06` selects the fraction. All four staffs now adapt canonically. |
| Additional ornaments | `lutemusic/random-50-v3/001/tombeau_sur_logy.ft3` | [Tombeau sur la mort de M. Compte de Logy](https://browse.lutemusic.org/composers/Weiss/pdf/tombeau_sur_logy.pdf) | Three `1c00` values print a left parenthesis before the fret; nine `2800` values print the repeated under-fret hook visible in bars 3, 26, and 27. Both now decode without residual bits. |
| Long solo layout | `lutemusic/random-50-v3/017/hierusalem.ft3` | [Hierusalem luge](https://browse.lutemusic.org/composers/Borrono/pdf/hierusalem.pdf) | The 222 numbered bars remain continuous across three pages. The interleaved 74-byte object has no musical bar and is preserved as a typed placement-layout record rather than an unknown staff. |
| Under-note ornament | `lutemusic/random-63-v4/019/2_suite_18_courante.ft3` | [Suite 18 in G minor, Courante](https://browse.lutemusic.org/composers/Froberger/pdf/2_suite_18_courante.pdf) | The sole `2400` value is the printed `v` below the first-course fret in bar 5; it now renders and exports as an under-`v` ornament. |
| Combined fingering bits | `lutemusic/random-63-v4/031/Folle_cor_T.ft3` | [Folle cor](https://browse.lutemusic.org/composers/Mazzocchi/pdf/Folle_cor_T.pdf) | All 36 bars and tablature agree. The isolated `00c0` source value composes known left-finger bits 2 and 3; the PDF hides fingerings, so Oud preserves `2+3` without claiming a visible PDF mark. |

## Findings

- The focused `corpus/ft3-regression.json` fixtures report zero residual note
  bits, vocal bits, unknown source records, or import warnings.
- Standard-note source records are semantic `note`/`note-lyrics` records. They
  are no longer duplicated as raw bars in each imported lane.
- Barline ASCII control fragments remain inspectable control rows instead of
  becoming fake pitches. Tablature payload fragments such as `_6(` no longer
  create synthetic notation staffs.
- In the fixed 415-file corpus, at least 38 files contain typed notation records. Thirty
  adapt strictly with lyrics. Seven are rejected with concrete inconsistent-
  duration or invalid-tie diagnostics; the adapter does not silently scale
  conflicting same-onset events or invent tie targets.
- The four canonical layout cases contain 1,382 events. Every event retains a
  staff/measure/system location at 60, 80, and 120 columns; two narrow Folle
  events are explicitly clipped, and the other cases place every event.
- Exact glyphs, braces, coordinates, proportional spacing, ordinary system
  wrapping, and automatic PDF pagination are Fronimo engraving output. They are
  approximated or reflowed for the terminal width. Explicit section/page data
  present in FT3 is preserved.

The focused matrix therefore has semantic import parity, not pixel-identical
engraving parity. It does not establish general FT3 or Fronimo parity.

## Fixed 300-file expansion

`corpus/ft3-random-75.json` records a one-time selection made on 2026-07-12.
Tests fetch those exact URLs and hashes; they never repeat the random choice.
All 75 files load without crashing or warnings and pass the semantic audit with
zero residual note bits, vocal bits, or unknown source records.

`corpus/ft3-random-75-v2.json` adds a second one-time selection made on
2026-07-17: one file from each of 75 previously unseen composer directories,
with no URL or digest overlap with the first sample. All 75 additional files
also load without warnings and pass the semantic audit.

`corpus/ft3-random-50-v3.json` adds a third one-time selection made on
2026-07-19: one file from each of 50 further composer directories, with no URL
or digest overlap with either earlier sample. It exposed and now covers two
additional ornament values, a placement-layout record, and three score headings.
All 50 files load without warnings and pass the semantic audit.

`corpus/ft3-random-63-v4.json` adds a fourth one-time selection made on
2026-07-19: 63 distinct composer buckets and no URL or digest overlap with the
earlier manifests. It exposed empty polyphonic notation records, embedded score
text that resembled tablature, combined fingering bits, and the under-`v`
ornament. All 63 files load without warnings and pass the semantic audit.
