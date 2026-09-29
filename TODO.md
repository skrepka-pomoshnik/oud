# TODO

Open work only. Completed items live in `DONE.md`.

The backlog is split by complexity so that work can be handed out safely:

- **Complex (`C`, owner: Claude).** A task is complex when it does at least one
  of these: changes a canonical model, file format, or public Petrucci contract;
  crosses the Oud/Petrucci boundary or more than one layer; needs a design
  decision or reverse engineering without a written spec; or can silently corrupt
  user data through edit, undo, save, or playback.
- **Not complex (`S`, open to any contributor).** Local to one module, script,
  fixture set, or document. Acceptance is already specified and no public
  contract changes. Some of these still need specific data, network access, or a
  host (marked **Needs**).

Each item lists its files, steps, acceptance, and dependencies. Do not start an
item whose dependencies are open. Every item is done only when the common gate
passes (`./scripts/quality.sh`) and `DONE.md` records the outcome and evidence.

## Order of work

1. Editor rebuild for typing: `C3` → `C4` → `C5` → `C6`.
2. Note typing: `C7`.
3. Transposition: `C8`.
4. FT3 fidelity: `C9`, `C10`, `C11` (need the local Gerbode corpus).
5. Publication and source model: `C12`, `C13`, `C14`.

`S` items run in parallel with the `C` chain whenever their dependencies allow.
`docs/ui-fix-plan.md` holds the evidence and acceptance for `C3`–`C6` and
`S2`–`S8`; tick items there as well.

---

## Complex tasks (owner: Claude)

### C3. Onset cursor and one edit path (UI plan phase 4, editor)

Why complex: rewrites cursor semantics and every insert path, and risks losing
user edits.

- Files: `oud/editor/interaction/insert/actions.py` (`_flatten_chords_to_grid`
  at line 104 and every `_handle_insert_*`), `oud/editor/navigation/motions.py`,
  `cursor_map.py`, `layout.py`, `oud/editor/editing/primitives/edits.py`,
  `rhythm.py`, `oud/editor/core/state.py`.
- Steps:
  1. The cursor becomes (bar, exact onset `Fraction`, course) with an explicit
     append slot. `h`/`l` step between onsets, not justified filler cells.
  2. Route French letters, Italian numbers, bass-course entry (`/`), rests (`z`),
     dots, durations, replace mode, and delete through `apply_tab_transaction`
     (`petrucci.input.tablature.mutation`, onsets in whole notes). The Italian
     path currently writes the grid through `enter_fret`.
  3. Delete `_flatten_chords_to_grid`. Editing an imported bar keeps its chords.
  4. The status beat comes from the onset and the bar's own meter.
- Acceptance: every keyscript and transaction fixture passes; editing an imported
  bar leaves unedited chords identical; no edit path writes a grid map.

### C4. Retire the grid maps and float rhythm (UI plan phase 4, readers)

Why complex: about 40 modules read `overrides`, `durations`, or `dotted`,
including rendering, TAB/MusicXML/MIDI export, playback, and verification.

- Files (largest first): `oud/editor/editing/primitives/bars.py`,
  `oud/presentation/cli_convert.py`, `oud/editor/editing/primitives/rhythm.py`,
  `oud/editor/services/media/operations.py`, `petrucci/rendering/bar/legacy.py`,
  `oud/editor/services/io/loading.py`, `oud/editor/navigation/layout.py`,
  `oud/editor/editing/score/operations.py`, `petrucci/terminal/view/model.py`,
  `petrucci/rendering/rhythm/grid.py`, `oud/exports/export_tab.py`,
  `oud/editor/editing/transforms.py`, `oud/exports/midi/projection.py`,
  `oud/exports/musicxml.py`, and the remaining readers found by
  `grep -rlE "\.overrides|\.durations|\.dotted\b" oud petrucci`.
- Steps:
  1. Migrate readers one layer at a time: exports, then playback, then
     rendering, then visual/transforms/find.
  2. Replace float quarter-beat rhythm with `Fraction` and per-bar meters.
  3. Delete `overrides`, `durations`, `dotted` from `EditorState` and
     `render_piece`.
- Acceptance: the grep above returns nothing; TAB save/reopen, MIDI, MusicXML,
  and LilyPond outputs are unchanged for every repo TAB file and fixture.
- Depends on: `C3`, `S6`.

### C5. Typed undo transactions (UI plan phase 4)

Why complex: undo is the last line of defence for user data; 24 untyped
`UndoAction(kind: str, data: dict)` kinds exist.

- Files: `oud/editor/editing/primitives/undo.py`, `oud/editor/core/state.py`,
  every `record_action` caller.
- Steps: replace `UndoAction` with typed records per mutation family (chords,
  bar properties, courses/tuning, metadata, spans). One user action is one undo
  step.
- Acceptance: undo/redo fixtures for every family, including the mixed note,
  chord, and rest transaction; no `kind=` strings remain.
- Depends on: `C4`.

### C6. Command registry and typed editor state (UI plan phase 5)

Why complex: touches every command and every settings reader.

- Files: `oud/presentation/tui/commands.py` (539 lines),
  `oud/editor/commands/dispatch.py`, `oud/editor/commands/handlers/*.py`,
  `oud/editor/core/state.py`, `oud/settings.py`.
- Steps:
  1. Replace the three command layers with one `CommandSpec` registry: handler,
     argument spec, read-only policy, completion, and help line.
  2. Split `EditorState.settings` into typed user preferences, document
     properties, and runtime state. `:set` routes to exactly one of them.
  3. Break `EditorState` into view, input-session, document, and media records.
- Acceptance: help and completion are generated from the registry; every `:set`
  key has one owner; preference persistence keeps its current rules.
- Depends on: `C5`.

### C7. Pitch entry and notation-staff typing (new, P1.2)

Why complex: needs a storage-format decision and wires a second input model into
the editor. `apply_note_input` / `NoteInputTransaction` exist in
`petrucci/input/note/` but nothing in `oud/` calls them, so the editor cannot
type standard notes at all.

- Steps:
  1. Pitch entry into tablature: type a note name (with accidental and octave)
     and have `oud/editor/editing/tab/assignment.py` (`assign_chord_pitches`)
     choose course and fret under the current tuning, with forced-course
     override and visible diagnostics when no assignment exists.
  2. Decide and document how native TAB stores a notation part. Today
     `oud/importers/tab.py` and `oud/exports/export_tab.py` have no melody or
     notation line. **Decision needed from the maintainer before step 3.**
  3. Notation-staff typing: the `C3` onset cursor moves onto notation staffs, and
     edits go through `apply_note_input` with the same undo, read-only, and save
     rules as tablature.
- Acceptance: typed pitches produce the same TAB/MIDI/LilyPond output as the
  equivalent fret entry; notation parts survive save/reopen; keyscript fixtures
  for notes, chords, rests, ties, and lyrics.
- Depends on: `C6`.

### C8. Score-aware transposition (P1.3)

Why complex: a new optimisation algorithm with a playability cost model.
Replace the current per-chord reassignment with a deterministic score-aware
algorithm that preserves sounding pitch and produces playable tablature.

- Steps:
  1. Define hard constraints: tuning, course count, fret range, forced strings,
     no same-course chord collisions, bass-course rules, maximum hand stretch,
     and representable output glyphs.
  2. Define a documented cost model: fret position, hand movement, course
     changes, open-string preference, chord-shape continuity, repeated fingering,
     voice continuity, and preservation of user-forced assignments.
  3. Optimise over a phrase or selected range with dynamic programming or a
     bounded beam search; never choose each note/chord greedily in isolation.
     Equal-cost results have a stable tie-break.
  4. Make transposition transactional: preview changed, impossible, and ambiguous
     events with concrete reasons; apply all changes atomically or require an
     explicit partial mode; preserve attachments, durations, voices, selection,
     cursor, and one-step undo/redo.
  5. Support whole-score and visual-range transposition, target tuning/course
     changes, and standard-note respelling with an explicit key-aware policy.
- Acceptance: adversarial and real-score tests for dense chords, repeated
  passages, bass courses, alternate tunings, impossible ranges, deterministic
  output, save/reopen pitch invariants, and LilyPond/MIDI agreement.
- Depends on: `C5`.

### C9. FT3 decoding gaps (P1.1)

Why complex: reverse engineering without a spec. **Needs** the local Gerbode
corpus (not redistributable; fetching is blocked in the cloud environment).

- Decode and render German and Spanish/Neapolitan FT3 tablature from real
  fixtures, or reject each unsupported style with a precise visible diagnostic.
- Confirm the remaining notation constructs against real FT3 encodings: TabVoice
  collision precedence, mensural proportions, harmonics, glissandi, and
  notation-staff fingerings. Typed fields, regressions, terminal rendering, and
  LilyPond assertions exist; raw FT3 bit meanings still need evidence before the
  importer may set them. Unknown values must stay visible in `:info` and fail the
  semantic audit instead of being silently discarded.

### C10. Companion-MIDI semantic gaps (P1.1)

Why complex: decoder-versus-source classification across the corpus. **Needs**
the local corpus and companion MIDIs.

The normalized 514-score baseline has 224 exact scores, 420 at or above 0.90
onset-chord similarity, 11 best-fit global transpositions, and 22 below 0.50
similarity. Never treat PPQ, patch, track, or count-in differences as
pitch/rhythm agreement.

- First resolve source-tuning metadata for the five transposition-only exact
  sequences, then classify the zero/sparse generated parts and mixed-score
  voice-count differences without inventing source events.
- Decode the collapsed full-score registration cases where one imported staff
  bar still represents an entire piece. `sonata_CM_01_moderato.ft3`,
  `come_raggio_del_sol_G.ft3`, and `courant_duet.ft3` must retain source-record
  order while mapping notation to the corresponding tablature bars and repeat
  passes.
- Correct independent note-staff onset grouping in completely mapped scores,
  especially `sonata_01.ft3`, `pavan_3.ft3`, and
  `o_death_rock_me_asleep_mens.ft3`; preserve simultaneous voices without
  collapsing sequential notes onto shared onset chords.
- Classify incomplete-source versus decoder loss before changing note counts.
  `passacaille_B.ft3` has 108 sounding imported events against 387 in its fuller
  companion arrangement; Couperin viol/duet/trio companions likewise need part
  and arrangement provenance rather than invented source notes.
- Decode exercise and technique records that still export only fragments in
  `grounds16.ft3`, `lefthand1.ft3`, `righthand_85.ft3`, and
  `right_hand_obrian.ft3`; distinguish instructions, fingering demonstrations,
  and sounding events explicitly.
- Resolve the remaining 11 best-fit transpositions only from source tuning or
  instrument provenance: Abel's two full scores, `000_beck_katherine_ogie.ft3`,
  mensural *O Death*, `sonata_01.ft3`, Gesualdo's galliard,
  `disperate_speranze_4.ft3`, `arabesque_T.ft3`, Reusner's passacaglia,
  `battle_pavane.ft3`, and `courant_duet.ft3`.
- Danyel's *Leaves Be Green* is at zero transposition, 0.960 onset similarity,
  and 0.932 pitch overlap. Its 75 companion-only attacks are realized
  diminutions without FT3 testimony; add them only if a source representation
  and provenance are found.

### C11. Staff registration in mixed scores (viewer)

Why complex: shared horizontal registration across tablature and notation
layouts. **Needs** the local corpus.

- At 120x40 in *Felice fu quel dì*, lute and soprano bars do not share
  horizontal bar positions within a system.
- Acceptance: every staff in a system places each barline at the same column;
  regression at 80x24 and 120x40.

### C12. Publication engraving profiles and PDF acceptance (P1.4)

Why complex: a new profile model across many LilyPond features, and a raster
acceptance harness with tolerance decisions.

- Stable engraving profiles for solo lute, lute with voice, vocal-only,
  polyphonic mixed score, duet, and multi-section works. Control paper size,
  margins, staff size, system spacing, bars/system, page/system breaks,
  title/credits, instrument names, and page numbering. Preserve staff order,
  lyrics, repeats/endings, meter/key/clef changes, bass courses, rhythms, beams,
  fingerings, ornaments, and section/page data.
- A rendered-PDF acceptance matrix for solo, mixed, four-part, duet, long
  multi-page, and dense scores: page count, system count, staff order, clipping,
  collisions, orphaned headings, lyric alignment, and readable scale. Extend the
  Bossinensis twelve-stanza and Dowland two-verse benchmarks with bounded
  raster-difference thresholds and further public Gerbode mixed scores. Record
  intentional differences from Gerbode/Fronimo output instead of claiming pixel
  identity.
- Done when the LilyPond output passes the Gerbode comparison corpus and the
  visual regression cases.
- Depends on: `S12`.

### C13. Source testimony versus interpretation

Why complex: extends the canonical model and identity through every layer. This
is not a claim of general mensural, neumatic, or chant support.

- Extend the stable diplomatic identity, source order/coordinates, mensuration,
  and proportion records to written pitch/shape, coloration, ligature
  membership, dots, accidentals/ficta, and text association.
- Extend the mensuration/proportion editorial decisions to effective onset and
  duration, perfection/imperfection or alteration, dot meaning, ficta decisions,
  and voice synchronization. Derivation stays deterministic and never mutates
  source testimony.
- Preserve one stable object identity and source location through import,
  interpretation, `NotationScore`, `ScoreLayout`, terminal semantic cells,
  playback diagnostics, and LilyPond export.
- Add one small end-to-end fixture for every historical construct we claim to
  support, starting with mensuration and proportion from real FT3 files:
  diplomatic display, interpreted timing, terminal rendering, LilyPond output,
  and MIDI timing assertions.
- Add an alternative-interpretation regression proving two editorial decisions
  can share one diplomatic source without duplicating or rewriting it.
- Reject unsupported historical constructs visibly instead of approximating or
  silently discarding them (the documentation half is `S10`).
- Define the semantic typesetting requests shared by the terminal proof and
  LilyPond export: object identity, anchors, ordering, collision roles, spacing
  constraints, registration points, and explicit local overrides. Do not build a
  second geometry engine or an SVG backend. Borrow proven printing concepts, not
  output formats: duration-sensitive spacing, optical corrections, anchors,
  collision boxes, registration, local engraver responsibilities, and explicit
  per-object overrides.

### C14. MEI mensural interoperability experiment

Why complex: a new import/export format; experimental, lowest priority.

- Prototype lossless MEI mensural import/export for the supported diplomatic
  subset only. Preserve IDs, source order, graphic mensuration signs, semantic
  mensuration values, explicit interpretive durations, and unsupported-data
  diagnostics.
- Compare the prototype with Verovio on a small checked-in legal fixture set,
  including mensural score-up. Use Verovio only as an interoperability oracle; do
  not add an SVG backend, make Verovio a required dependency, or advertise MEI
  support until round trips and comparisons pass.
- Depends on: `C13`.

---

## Not complex tasks (open to any contributor)

### S2. Scroll the command prompt horizontally (UI plan phase 3)

- Files: `oud/presentation/tui/prompt.py`, `prompt_text` in
  `oud/editor/services/screen/status.py`.
- Keep the cursor visible when the text is wider than the screen, so a long
  prefilled Save As path stays editable at 80 columns.
- Acceptance: tests at 80 columns with a path longer than the line, for typing,
  deleting, and history recall.

### S3. One help surface (UI plan phase 3)

- Files: `oud/editor/core/input/help.py`,
  `oud/editor/interaction/normal/commands.py` (`help_pager`).
- The in-app overlay and the `less` pager show identical generated content from
  the key table.
- Acceptance: a test that compares the overlay lines with the pager text for
  each key style.

### S4. Named meter diagnostic in the status line (UI plan phase 3)

- Replace the cryptic `M` from `bar_meter_integrity_marker` with a segment such
  as `meter 5/6`, shown only in normal mode.
- Files: `oud/editor/services/screen/rhythm.py` (`bar_meter_marker`) and the
  `meter` segment in `oud/editor/services/screen/status.py`.
- Acceptance: status tests for a full bar, an underfull bar, and an overfull bar.

### S5. One position vocabulary (UI plan phase 3)

- `oud/editor/services/screen/status.py` falls back to `col:N` when the meter
  does not parse. Show `beat:` in every TAB and FT3 projection; `C3` later makes
  it exact.
- Acceptance: no `col:` in any status line; tests for TAB, FT3 projection, and an
  unparseable meter.

### S6. Idempotent TAB save (UI plan phase 4)

- File: `oud/exports/export_tab.py:159` writes
  `bar.time_sig or settings["time"]` for every bar, so re-saving adds a repeated
  `S6/4` line.
- Write a meter line only where the bar has its own `time_sig`, on the first bar,
  or where an empty bar needs its explicit line to stay a measure (see the
  empty-bar decision in `docs/ui-fix-plan.md`).
- Acceptance: open-save-reopen-save of every repo TAB file is byte-identical
  after the first save; empty bars still round-trip.
- Land before `C4` starts, because `C4` rewrites the same file.

### S7. Staff label overwrites the tablature staff (viewer)

- The `lute` staff label overwrites the start of the tablature staff.
- Acceptance: the label occupies its own prefix columns; regression at 80x24 and
  120x40 for solo and mixed scores.

### S8. Focus label matches the staff label (viewer)

- File: `oud/editor/navigation/view/focus.py:44` names the tablature lane `Tab`,
  while the staff label reads `lute`. Use one label source.
- Acceptance: status `focus:` equals the rendered staff label for solo, mixed,
  and duet scores.

### S9. Companion-MIDI provenance in audit reports

- Files: `scripts/corpus/midi/`.
- Store the companion MIDI checksum and retrieval provenance in audit reports so
  stale optional evidence is diagnosed before parity assertions run.
- Acceptance: a stale or altered companion MIDI produces an explicit diagnostic.

### S10. Document the supported historical-notation matrix

- Add a table to `docs/supported-behavior.md` listing each historical construct
  as supported, partial, experimental, or unsupported, with the test that proves
  it. Enforcement is part of `C13`.

### S11. Engraving-quality matrix coverage

- File: `tests/fixtures/ft3/manifests/engraving-quality-matrix.json`.
- Give every supported notation feature one source-independent microcase. The
  inventory covers six feature families and registers the Felice benchmark. Add
  a real FT3 entry whenever a family is promoted from partial support (**Needs**
  the local corpus for that half).

### S12. Dual-engine PDF comparisons for every microcase

- Extend the curated-FT3 comparisons to every shared engraving-matrix microcase.
  LilyPond 2.26 is authoritative; document 2.24 differences as compatibility
  limitations.
- **Needs** LilyPond 2.24 and 2.26 installed.

### S13. Typesetting microcases and fixture licensing

- Add microcases for spacing, collisions, lyrics, ligatures, mensuration signs,
  tablature rhythm flags, and mixed vocal-plus-lute systems. Assert the generated
  LilyPond structure (raster comparisons belong to `C12`).
- Evaluate public CMME and Measuring Polyphony examples: record each fixture's
  license and expected interpretation before any is used.

### S14. Advanced terminal engraving review (experimental modes)

Opt-in renderers only; the default ASCII and pretty modes are unaffected.

- Assess dark/light semantic colour palettes, mixed-role cell readability, ANSI
  output, and colour-independent duration recognition.
- Validate solid-block projection, narrow viewports, note/rest identity, and
  Alacritty output; compare with the braille and ASCII modes.
- Review the braille clef/rest masks and curve continuity; cover chord and
  broken-tie anchoring and compact polyphonic beams and slopes with small
  redistributable fixtures. Improve the crude clef and beam silhouettes without
  reintroducing mixed-grid geometry.
- Compare ASCII and advanced previews at several fonts and sizes; preserve event
  identities, clipping, and readable duration distinctions.

### S15. Grow the FT3 compatibility corpus to 1,000 files

**Needs** access to lutemusic.org (blocked in the cloud environment).

- Continue the fixed corpus from 514 to at least 1,000 public FT3 files without
  repeating random selection at test time. Include solo, duet, mixed vocal,
  vocal-only, polyphonic, multi-section, German, Italian, French, and
  Spanish/Neapolitan examples.
- Record URL, checksum, format/version, expected metadata, and staff-kind counts;
  require zero crashes and actionable warnings or unknown records. New manifests
  stay checksum-disjoint and audit-clean. The direct composer index supplies the
  additional URL candidates.

### S16. Style-proven French and Italian sources

**Needs** access to lutemusic.org.

- Add style-proven French and Italian Gerbode sources plus examples with tuplets
  and grace notes; the fixed corpora have null style provenance and no instances
  of those features.

### S17. macOS terminal acceptance pass

**Needs** a macOS host.

- Cover first run, open failure, solo/mixed/polyphonic/duet navigation,
  score/staff switching, edit/undo, modified quit, first Save As, overwrite
  refusal, playback failure/success, PDF failure/success, resize, and reopen.
- Run real curses cases at 80x24 and 120x40 and retain terminal output on
  failure.

---

## Standing constraints

- Petrucci stays source-neutral: it owns notation, geometry, clipping, and
  semantic identity. Voce owns assessment, interaction, audio transport, and
  lesson policy. MIDI serialization, TiMidity, transport, latency, and lesson
  policy stay outside Petrucci.
- LilyPond stays export-only and the publication backend: no LilyPond parser and
  no `.ly` internal representation. Font and glyph metrics stay inside the
  publication backend; core notation and terminal layout never depend on SMuFL
  private-use glyph widths or a particular terminal font.
- The terminal renderer is the deterministic proof and editing surface: compact
  fitting, clipping only at the lower viewport border, stable cursor/playback
  highlighting, ASCII-safe geometry, and graceful narrow terminals.
- The architecture check enforces complexity 7, a 1,000-line module ceiling, at
  most seven direct Python entities per package, and the UI-independent
  dependency boundary. No debt baseline is carried; new violations fail.
- Ruff and Vulture audits are clean. Record only reproducible static findings
  here.

## Deferred pending a product decision

- A dedicated mensural input DSL, only after the diplomatic model and round trips
  expose concrete limitations in FT3/TAB entry. Do not design syntax before that
  evidence exists.
- Neumes, `gabc`, chant editing, facsimile overlays, and terminal image protocols
  are separate future scopes, not implied by mensural or tablature support.
