# FT3/PDF parity matrix

Manual comparison with Sarge Gerbode's published PDFs, 2026-07-11 through
2026-07-17. Reference PDFs are not copied into the repository.

```bash
uv run python scripts/fetch_ft3_corpus.py corpus/ft3-regression.json
uv run oud ascii FILE.ft3 --bars 1:10
uv run python scripts/ft3_audit.py lutemusic/05_can_she_excuse
```

| Shape | Local FT3 | Published PDF | Result |
| --- | --- | --- | --- |
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

## Findings

- The focused `corpus/ft3-regression.json` fixtures report zero residual note
  bits, vocal bits, unknown source records, or import warnings.
- Standard-note source records are semantic `note`/`note-lyrics` records. They
  are no longer duplicated as raw bars in each imported lane.
- In a 15-file standard-notation audit, 4 files adapt strictly with lyrics and
  11 adapt when the explicit note-only policy is selected. The other 4 are
  rejected with concrete invalid-pitch or meter-overflow diagnostics. The
  adapter does not guess through those records or force unmatched lyrics onto
  note onsets.
- The four canonical layout cases contain 1,382 events. Every event retains a
  staff/measure/system location at 60, 80, and 120 columns; two narrow Folle
  events are explicitly clipped, and the other cases place every event.
- Exact glyphs, braces, coordinates, proportional spacing, ordinary system
  wrapping, and automatic PDF pagination are Fronimo engraving output. They are
  approximated or reflowed for the terminal width. Explicit section/page data
  present in FT3 is preserved.

The focused matrix therefore has semantic import parity, not pixel-identical
engraving parity. It does not establish general FT3 or Fronimo parity.

## Fixed 75-file expansion

`corpus/ft3-random-75.json` records a one-time selection made on 2026-07-12.
Tests fetch those exact URLs and hashes; they never repeat the random choice.
All 75 files load without crashing or warnings and pass the semantic audit with
zero residual note bits, vocal bits, or unknown source records.
