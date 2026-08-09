# TODO

Priority order:

1. Publication-grade FT3 viewer support.
2. Gerbode-based lute tablature and standard-note typing parity.
3. Intelligent, score-aware transposition.
4. Publication-quality PDF generation through LilyPond.
5. Architecture debt and secondary release work.

## P0: Publication blockers

No open P0 items. Publication readiness still depends on the P1 FT3 support and
acceptance claims below.

## P1.1: Publication-grade FT3 viewer

Target: a mature read-only workflow for supported public Gerbode FT3 scores.
Native FT3 writing and Fronimo editor parity remain out of scope.

### Full-score presentation

- [x] Add explicit `score` and `staff` viewer modes for imported scores.
  - At 120x40, `score` mode renders every mapped tablature, notation, and lyric
    staff together when they fit.
  - At 80x24, vertical scrolling reaches every staff without dropping content;
    `staff` mode remains the compact focused view.
  - Preserve source staff label/index, bar, cursor, playback position, filename,
    document mode, and write target across mode changes and resize.
  - Cover solo, mixed song, four-part vocal, vocal-only, and duet FT3 files at
    80x24 and 120x40.
- [x] Add navigation suitable for long read-only scores.
  - Support previous/next system and section/page jumps without changing the
    logical score cursor.
  - Show current section/page and system range in status or `:info` when the FT3
    contains that data.

### Format confidence

- [x] Expand the deterministic, stratified compatibility manifest from 263 to
  300 public FT3 files with a fixed one-time selection, checksums, metadata,
  zero semantic-audit residuals, and no committed downloaded payloads.
- [ ] Continue the fixed compatibility corpus from 300 to at least 1,000 public
  FT3 files without repeating random selection at test time.
  - Include solo, duet, mixed vocal, vocal-only, polyphonic, multi-section,
    German, Italian, French, and Spanish/Neapolitan examples.
  - Record URL, checksum, format/version, expected metadata, and staff-kind
    counts; require zero crashes and actionable warnings or unknown records.
- [ ] Complete at least 25 stratified manual comparisons against published PDF
  and MIDI evidence in `docs/ft3-parity.md` (19 PDF comparisons are recorded;
  MIDI evidence remains incomplete).
- [ ] Decode and render German and Spanish/Neapolitan FT3 tablature from real
  fixtures, or reject each unsupported style with a precise visible diagnostic.
- [x] Add LilyPond/MuseScore-inspired semantic regression cases for partial and
  grace beams, grouped tuplets, cross-system ties/slurs, fermatas, ornaments,
  endings, and repeat barlines without vendoring upstream fixtures.
- [ ] Close the remaining notation gaps with real-file evidence: polyphonic
  TabVoice collision precedence, mensural proportions, harmonics, glissandi,
  and notation-staff fingerings.
  - Each construct needs a typed model field, importer regression, terminal
    rendering regression, and LilyPond assertion.
  - Unknown values must remain visible in `:info` and fail the semantic audit
    instead of being silently discarded.

### Playback and acceptance

- [ ] Play all mapped voices and staffs with synchronized cursor movement.
  - Compare MIDI note-on events, voice/channel assignment, repeats/endings,
    tempo, and start-bar behavior for the representative viewer matrix.
  - Keep pause/stop/restart and missing-synth diagnostics deterministic; never
    report playback success when no player started.
- [ ] Make `lyricmode=current` follow the active stanza automatically while
  `playverses=all`; preserve an explicitly selected `lyricverse` while stopped.
- [ ] Add the macOS-only terminal acceptance pass.
  - Cover first run, open failure, solo/mixed/polyphonic/duet navigation,
    score/staff switching, edit/undo, modified quit, first Save As, overwrite
    refusal, playback failure/success, PDF failure/success, resize, and reopen.
  - Run real curses cases at 80x24 and 120x40 and retain terminal output on
    failure.
## P1.2: Gerbode lute and note typing parity

Target: re-enter representative Gerbode score material without losing musical
intent. This is score-entry parity against documented examples, not parity with
every Fronimo editing feature.

- [x] Add one extra-bass-course transaction and keyscript fixture per style.
- [x] Add one repeated-chord transaction fixture per style.
- [x] Add one string-movement fixture proving other courses remain unchanged.
- [x] Add one attachment-retention fixture for replacement and deletion.
- [x] Add one undo/redo fixture for a mixed note, chord, and rest transaction.
- [x] Add deterministic operation-sequence tests that compare canonical state,
  rendered semantics, TAB save/reopen, and LilyPond/MIDI export. Keep compact
  one-feature fixtures for failures; do not vendor MuseScore or LilyPond
  fixtures.
- [x] Curate source-supported excerpts from the fixed 100-score Gerbode corpus
  covering tablature, bass courses, chords/rests, polyphonic notation, lyrics,
  and ornaments. Checked-in expectations cover terminal rendering, TAB
  save/reopen semantics, LilyPond, MIDI, and published-score observations
  without committing external FT3 or PDF payloads.
- [x] Extend curated Petrucci acceptance with a checksum-verified Gerbode score
  containing a canonical tie and compare its render/exports with the published
  two-page score.
- [ ] Add style-proven French and Italian Gerbode sources plus source examples
  containing tuplets and grace notes; the current fixed corpora have null style
  provenance and no instances of those notation features.

## P1.3: Intelligent transposition (next after FT3 and typing parity)

Replace the current per-chord reassignment with a deterministic score-aware
algorithm that preserves sounding pitch and produces playable tablature.

- [ ] Define explicit hard constraints: tuning, course count, fret range, forced
  strings, no same-course chord collisions, bass-course rules, maximum hand
  stretch, and representable output glyphs.
- [ ] Define a documented cost model for playability and notation stability:
  fret position, hand movement, course changes, open-string preference, chord
  shape continuity, repeated fingering, voice continuity, and preservation of
  user-forced assignments.
- [ ] Optimize over a phrase or selected range with dynamic programming or a
  bounded beam search; do not choose each note/chord greedily in isolation.
  Equal-cost results must have a stable tie-break.
- [ ] Make transposition transactional.
  - Preview changed, impossible, and ambiguous events with concrete reasons.
  - Apply all changes atomically, or require an explicit partial mode.
  - Preserve attachments, durations, voices, selection, cursor, and one-step
    undo/redo.
- [ ] Support whole score and visual-range transposition, target tuning/course
  changes, and standard-note respelling with an explicit key-aware policy.
- [ ] Add adversarial and real-score tests for dense chords, repeated passages,
  bass courses, alternate tunings, impossible ranges, deterministic output,
  save/reopen pitch invariants, and LilyPond/MIDI agreement.

## P1.4: Publication-quality PDF via LilyPond (next after transposition)

- [ ] Add explicit LilyPond executable/version selection and retain structured,
  actionable compiler diagnostics.
- [ ] Add stable engraving profiles for solo lute, lute with voice, vocal-only,
  polyphonic mixed score, duet, and multi-section works.
  - Control paper size, margins, staff size, system spacing, bars/system,
    page/system breaks, title/credits, instrument names, and page numbering.
  - Preserve staff order, lyrics, repeats/endings, meter/key/clef changes,
    bass courses, rhythms, beams, fingerings, ornaments, and section/page data.
- [ ] Require generated `.ly` files to compile with the supported LilyPond
  version without errors or undocumented warnings.
- [ ] Build a rendered-PDF acceptance matrix for solo, mixed, four-part, duet,
  long multi-page, and dense scores.
  - Check page count, system count, staff order, clipping, collisions, orphaned
    headings, lyric alignment, and readable scale.
  - Record intentional differences from Gerbode/Fronimo output instead of
    claiming pixel identity.

## P2: Architecture debt retirement

CI enforces complexity 7 and a 1,000-line module ceiling against the exact
non-growth baseline in `architecture-debt.json`; rationale, counts, and ownership
targets are in `docs/architecture-debt.md`.

- [ ] Retire the remaining 124 function-level C901 findings without raising
  limits, broad per-file ignores, compatibility wrappers, or count-only helper
  modules. Continue with `oud.editor.insert_actions.handle_insert` (31),
  `oud.tui.input.complete_command_text` (31), and
  then continue through the next highest domain coordinators.
- [ ] Replace the 31 narrowly suppressed production `PLR0917` surfaces with
  typed render, layout, playback, and export request records as their owning
  modules are split; do not add per-file ignores or forwarding wrappers.

## P3: Secondary release work

- [ ] Confirm GitHub Actions green on macOS.
- [ ] Ship a real `oud(1)` manual page that works with `man oud`.
  - Maintain `man/oud.1.scd` as the readable source and commit generated
    `man/oud.1` roff output.
  - Cover synopsis, options/subcommands, files, environment, exit status,
    examples, diagnostics, and see-also references.
  - Add reproducible build and user-local installation under
    `~/.local/share/man/man1` without requiring sudo.
  - Validate with `mandoc -T lint man/oud.1` and `man -l man/oud.1` when
    available.
  - Keep README as the quick-start page and the man page as the exhaustive
    command reference.
## Source-faithful notation architecture

These items refine the existing FT3, terminal-viewer, and publication work. They do not constitute a claim of general mensural, neumatic, or chant support.

### P1: separate source testimony from interpretation

- [ ] Define typed diplomatic records for the historical signs currently supported by FT3: stable source identity and order, source coordinates, written pitch/shape, mensuration and proportion signs, coloration, ligature membership, dots, accidentals/ficta, and text association.
- [ ] Represent editorial decisions separately from diplomatic records: effective onset and duration, perfection/imperfection or alteration where applicable, dot meaning, ficta decisions, and voice synchronization. Derivation must be deterministic and must not mutate source testimony.
- [ ] Preserve one stable object identity and source location through import, interpretation, `NotationScore`, `ScoreLayout`, terminal semantic cells, playback diagnostics, and LilyPond export.
- [ ] Add one small end-to-end fixture for every historical construct we claim to support. Start with mensuration and proportion from real FT3 files; require diplomatic display, interpreted timing, terminal rendering, LilyPond output, and MIDI timing assertions.
- [ ] Add an alternative-interpretation regression case proving that two explicit editorial decisions can share the same diplomatic source without duplicating or rewriting it.
- [ ] Document the supported historical-notation matrix explicitly; reject unsupported constructs visibly instead of approximating or silently discarding them.

### P2: improve proof rendering and publication typesetting

- [ ] Define the semantic typesetting requests needed by both the compact terminal proof and LilyPond export: object identity, anchors, ordering, collision roles, spacing constraints, registration points, and explicit local overrides. Do not build a second geometry engine or an SVG backend.
- [ ] Keep the terminal renderer as the deterministic proof and editing surface. Its acceptance criteria remain compact fitting, clipping only at the lower viewport border, stable cursor/playback highlighting, ASCII-safe geometry, and graceful narrow-terminal behavior.
- [ ] Add typesetting microcases for spacing, collisions, lyrics, ligatures, mensuration signs, tablature rhythm flags, and mixed vocal-plus-lute systems. Assert generated LilyPond structure and use bounded PDF raster comparisons for final typography.
- [ ] Borrow proven printing concepts rather than output formats: duration-sensitive spacing, optical corrections, anchors, collision boxes, registration, local engraver responsibilities, and explicit per-object overrides.
- [ ] Keep font and glyph metrics inside the publication backend; core notation and terminal layout must not depend on SMuFL private-use glyph widths or a particular terminal font.
- [ ] Retain LilyPond as the publication backend and improve its output until the Gerbode comparison corpus and visual regression cases pass.

### P3: bounded interoperability experiments

- [ ] Prototype lossless MEI mensural import/export for the supported diplomatic subset only. Preserve IDs, source order, graphic mensuration signs, semantic mensuration values, explicit interpretive durations, and unsupported data diagnostics.
- [ ] Compare the MEI prototype with Verovio on a small checked-in legal fixture set, including mensural score-up. Use it only as an interoperability oracle; do not add an SVG backend, make Verovio a required dependency, or advertise MEI support until round trips and comparisons pass.
- [ ] Evaluate public CMME and Measuring Polyphony examples only after fixture licensing and expected interpretations are documented.

### Deferred pending a product decision

- [ ] Decide whether a dedicated mensural input DSL is needed only after the diplomatic model and round trips expose concrete limitations in FT3/TAB entry. Do not design syntax before that evidence exists.
- [ ] Treat neumes, `gabc`, chant editing, facsimile overlays, and terminal image protocols as separate future scopes, not extensions implied by mensural or tablature support.
