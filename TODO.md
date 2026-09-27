# TODO

Priority order (hard dependency order):

1. Complete the Petrucci foundation gate below.
2. Publication-grade FT3 viewer support.
3. Gerbode-based lute tablature and standard-note typing parity.
4. Intelligent, score-aware transposition.
5. Linked Petrucci proof quality and LilyPond publication export.
6. Architecture debt and secondary release work.

## P0: Publication blockers

No open P0 items. Publication readiness still depends on the P1 FT3 support and
acceptance claims below.

## P0: Editor UI consistency

Evidence and acceptance criteria live in `docs/ui-fix-plan.md`; tick items there.

- [ ] Phase 3: move editor chrome (status, prompt, overlays, help) out of Petrucci.
- [ ] Phase 4: edit on exact onsets through the canonical tablature transaction path.
- [ ] Phase 5: one command registry; split preferences, document properties and runtime state.

## P0: Petrucci reusable notation library

This backlog comes from the 2026-09-12 Petrucci/Voce handoff. Petrucci remains
source-neutral and owns notation, geometry, clipping, and semantic identity;
Voce owns assessment, interaction, audio transport, and lesson policy.

**Foundation gate (closed 2026-09-13):** do not start or polish any lower-priority Petrucci, FT3,
viewer, transposition, or LilyPond item while this section has an unchecked
item. Fixing presentation symptoms before these contracts are complete creates
backend-specific geometry and is not an acceptable substitute.

- [x] Preserve exact pickup and irregular-measure extents in the canonical score and flow adapter.
  - Measure boundaries use whole-note units; aligned staffs reject conflicting extents.
- [x] Build one union of exact onset anchors per measure and consume it across every staff.
  - Staff-local collision widths may enlarge a shared slot but may not move simultaneous events independently.
- [x] Retain logical onset geometry beyond the viewport and clip only paintable span segments.
  - Ties, slurs, and glissandi must expose continuation geometry when an endpoint is clipped.
- [x] Add typed written-duration spelling independent of reciprocal denominators.
  - `DurationSpelling` covers breve through 128th values and four augmentation dots.
- [x] Preindex effective staff state and semantic frame cells with object-owned lifetimes.
  - Do not add global unbounded caches or repeated full-frame identity scans.
- [x] Expose a public proportional timeline projection with explicit origin and scale.
  - Return exact event/segment positions, measure boundaries, viewport clipping, and collision diagnostics.
  - [x] Publish exact `TimelineProjectionRequest` and identity-preserving measure/event/span projection records.
  - [x] Keep requested scale fixed and report distinct onsets that round into one visible staff cell.
  - [x] Make the notation engraver consume these anchors for notes, beams, ties, slurs, ledger lines, and accidentals before painting.
- [x] Expose public written-pitch and continuous-pitch staff projection against the same geometry contract.
  - Cover treble/bass clefs, clef changes, accidentals, timeline positions, and viewport offsets.
- [x] Migrate engraving duration decisions to `DurationSpelling` and render breve/dotted-breve notes and rests.
  - Add irregular-measure, semantic-cell, terminal-clipping, and no-tied-whole-note regressions.
- [x] Add bounded performance regressions for repeated layout, scrolling, resizing, batched lookup, and score replacement.
  - Record workload size and ceilings; performance claims without measurements do not close this gate.

- [x] Add display-only meter visibility for 3/4, 6/8, 4/2, and mid-score meter changes.
  - Preserve meter, validation, beaming, event timing, and reserved preamble/change spacing.
### Deferred: reusable accompaniment data

- [x] Assess an optional pure canonical-score performance projection with stable part/voice/source IDs.
  - Keep MIDI serialization, TiMidity processes, transport, latency, and lesson policy outside Petrucci.
  - Assessment and prerequisite model gaps are recorded in `docs/petrucci-voce-handoff.md`; implementation is deferred.

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
- [ ] Continue the fixed compatibility corpus from 514 to at least 1,000 public
  FT3 files without repeating random selection at test time.
  - Include solo, duet, mixed vocal, vocal-only, polyphonic, multi-section,
    German, Italian, French, and Spanish/Neapolitan examples.
  - Record URL, checksum, format/version, expected metadata, and staff-kind
    counts; require zero crashes and actionable warnings or unknown records.
  - Offline progress is 514 checksum-unique, semantically clean payloads. The
    direct composer index supplies additional URL candidates; future manifests
    must remain checksum-disjoint and audit-clean.
- [ ] Decode and render German and Spanish/Neapolitan FT3 tablature from real
  fixtures, or reject each unsupported style with a precise visible diagnostic.
- [x] Decode every FT3 semantic variant found across the direct composer-index audit.
  - The 14 formerly unresolved files are fixed as the v8 corpus: source layout,
    exercise labels, editorial text, later fingering/bracket/barre variants, and
    one-staff notation-only mapping are now typed without fake tablature notes.
- [x] Add LilyPond/MuseScore-inspired semantic regression cases for partial and
  grace beams, grouped tuplets, cross-system ties/slurs, fermatas, ornaments,
  endings, and repeat barlines without vendoring upstream fixtures.
- [ ] Confirm the remaining notation constructs against real FT3 encodings:
  TabVoice collision precedence, mensural proportions, harmonics, glissandi,
  and notation-staff fingerings.
  - Typed source-independent fields, imported-score regressions, terminal
    rendering, and LilyPond assertions are complete; raw FT3 bit meanings still
    require evidence before the importer may set them.
  - Unknown values must remain visible in `:info` and fail the semantic audit
    instead of being silently discarded.

### Playback and acceptance

- [x] Play all mapped voices and staffs with synchronized cursor movement.
  - Compare MIDI note-on events, voice/channel assignment, repeats/endings,
    tempo, and start-bar behavior for the representative viewer matrix.
  - Keep pause/stop/restart and missing-synth diagnostics deterministic; never
    report playback success when no player started.
- [ ] Close the corpus-wide companion-MIDI semantic gaps.
  - The normalized 514-score baseline has 224 exact scores, 420 at or above
    0.90 onset-chord similarity, 11 best-fit global transpositions, and 22 below
    0.50 similarity; never treat PPQ, patch, track, or count-in differences as
    pitch/rhythm agreement.
  - First resolve source-tuning metadata for the five transposition-only exact
    sequences, then classify the zero/sparse generated parts and mixed-score
    voice-count differences without inventing source events.
  - Decode the collapsed full-score registration cases where one imported staff
    bar still represents an entire piece; do not hide these behind timing or
    tuning profiles.
    Regressions: `sonata_CM_01_moderato.ft3`, `come_raggio_del_sol_G.ft3`, and
    `courant_duet.ft3` must retain source-record order while mapping notation to
    the corresponding tablature bars and repeat passes.
  - Correct independent note-staff onset grouping in completely mapped scores,
    especially `sonata_01.ft3`, `pavan_3.ft3`, and
    `o_death_rock_me_asleep_mens.ft3`; preserve simultaneous voices without
    collapsing sequential notes onto shared onset chords.
  - Classify incomplete-source versus decoder loss before changing note counts.
    `passacaille_B.ft3` contains 108 sounding imported events against 387 in its
    fuller companion arrangement; Couperin viol/duet/trio companions likewise
    require part and arrangement provenance rather than invented source notes.
  - Decode exercise and technique records that still export only fragments in
    `grounds16.ft3`, `lefthand1.ft3`, `righthand_85.ft3`, and
    `right_hand_obrian.ft3`; distinguish instructions, fingering demonstrations,
    and sounding events explicitly.
  - Resolve the remaining 11 best-fit transpositions only from source tuning or
    instrument provenance. The current cases are Abel's two full scores,
    `000_beck_katherine_ogie.ft3`, mensural *O Death*, `sonata_01.ft3`, Gesualdo's
    galliard, `disperate_speranze_4.ft3`, `arabesque_T.ft3`, Reusner's
    passacaglia, `battle_pavane.ft3`, and `courant_duet.ft3`.
  - Store companion MIDI checksum and retrieval provenance in audit reports so
    stale optional evidence is diagnosed before parity assertions run.
  - Danyel's *Leaves Be Green* is corrected to zero transposition and reaches
    0.960 onset similarity / 0.932 pitch overlap. Its remaining 75 companion-only
    attacks are realized diminutions without encoded FT3 note or ornament
    testimony; add them only if a source representation and provenance are found.
- [x] Make `lyricmode=current` follow the active stanza automatically while
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

## P1.4: Linked Petrucci and LilyPond engraving (next after transposition)

- [ ] Refine advanced terminal engraving against compact notation references:
  assess dark/light semantic colour palettes, mixed-role cell readability,
  ANSI output and colour-independent duration recognition.
  validate solid-block projection, narrow viewports, note/rest identity and
  Alacritty output; compare it directly with the braille and ASCII modes.
  review the unified braille clef/rest masks and curve continuity; cover
  chord/broken-tie anchoring, compact polyphonic beams and slopes with small,
  redistributable fixtures. Improve the crude clef and beam silhouettes without
  reintroducing mixed-grid geometry.
  Compare ASCII and advanced previews at several terminal fonts and sizes;
  preserve event identities, clipping, and readable duration distinctions.

- [ ] Expand `tests/fixtures/ft3/manifests/engraving-quality-matrix.json` until every supported
  notation feature has one source-independent microcase and at least one real
  FT3 case. The initial executable inventory covers six shared feature families
  and registers the Felice real-score benchmark; add a real FT3 entry whenever
  another family is promoted from partial support.
- [x] Drive Petrucci proof assertions and LilyPond export assertions from the
  same matrix instead of maintaining backend-specific fixture inventories.
- [x] Translate the remaining applicable LilyPond 2.24.4 and MuseScore 4.6.0
  regressions into small legal fixtures that record provenance and the borrowed
  invariant rather than upstream output bytes. Existing translated invariants
  are registered in `upstream_microcases` and exercised by the layout tests.
- [x] Keep LilyPond export-only: do not add a LilyPond parser or use `.ly` as an
  internal representation.
  - Verified 2026-09-13: no LilyPond importer exists under `oud/importers/`; `.ly`
    is produced at the export boundary and is not a Petrucci model input.
- [ ] Expand dual-engine PDF comparisons from the curated FT3 corpus to every
  shared engraving-matrix microcase; 2.26 is authoritative and 2.24 differences
  must be documented as compatibility limitations.

- [ ] Add stable engraving profiles for solo lute, lute with voice, vocal-only,
  polyphonic mixed score, duet, and multi-section works.
  - Control paper size, margins, staff size, system spacing, bars/system,
    page/system breaks, title/credits, instrument names, and page numbering.
  - Preserve staff order, lyrics, repeats/endings, meter/key/clef changes,
    bass courses, rhythms, beams, fingerings, ornaments, and section/page data.
- [x] Require generated `.ly` files to compile with the supported LilyPond
  version without errors or undocumented warnings. The fixed external
  `ft3-regression.json` manifest is exported and compiled with 2.26 when
  available; 2.24 remains a separate compatibility smoke target.
- [ ] Build a rendered-PDF acceptance matrix for solo, mixed, four-part, duet,
  long multi-page, and dense scores.
  - Check page count, system count, staff order, clipping, collisions, orphaned
    headings, lyric alignment, and readable scale.
  - Extend the implemented Bossinensis twelve-stanza and Dowland two-verse
    benchmarks with bounded raster-difference thresholds and further public
    Gerbode mixed scores.
  - Record intentional differences from Gerbode/Fronimo output instead of
    claiming pixel identity.

## P2: Architecture limits

The architecture quality check enforces complexity 7, a 1,000-line module ceiling,
at most seven direct Python entities per package, and the UI-independent dependency
boundary directly against the current tree. No debt baseline is carried; new
violations fail immediately.

## P3: Secondary release work

- [x] Ship a real `oud(1)` manual page that works with `man oud`.
  - Maintain `man/oud.1.scd` as the readable source and commit generated
    `man/oud.1` roff output.
  - Cover synopsis, options/subcommands, files, environment, exit status,
    examples, diagnostics, and see-also references.
  - Add reproducible build and user-local installation under
    `~/.local/share/man/man1` without requiring sudo.
  - Validate with `mandoc -T lint man/oud.1` and `man -l man/oud.1` when
    available. The repository build uses `scdoc`; `mandoc` is optional.
  - Keep README as the quick-start page and the man page as the exhaustive
    command reference.
## Source-faithful notation architecture

These items refine the existing FT3, terminal-viewer, and publication work. They do not constitute a claim of general mensural, neumatic, or chant support.

### P1: separate source testimony from interpretation

- [ ] Extend the implemented stable diplomatic identity, source order/coordinates,
  mensuration, and proportion records to written pitch/shape, coloration,
  ligature membership, dots, accidentals/ficta, and text association.
- [ ] Extend the separate mensuration/proportion editorial decisions to effective
  onset and duration, perfection/imperfection or alteration, dot meaning, ficta
  decisions, and voice synchronization. Derivation must remain deterministic
  and must not mutate source testimony.
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

## P0 - Static audit follow-up

The parser sources are syntactically valid and the current Ruff and Vulture
audits are clean. Keep future static checks local and update this section only
with reproducible findings.
