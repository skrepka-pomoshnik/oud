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

## Format goals (maintainer, 2026-09-29)

- Full read support for `.tab` (the original `tab` program) and FT3.
- MusicXML is the default save format (trial, `C16`). `.tab` keeps
  first-class read and write support but is not the main format, because it
  cannot hold several voices or staffs, lyrics, or tuplet timing.

## Order of work

1. Editor rebuild for typing: `C4` → `C5` → `C6`.
2. Formats: `C16` (MusicXML default), `C15` (full TAB with sidecar).
3. Note typing: `C7`.
4. Transposition: `C8`.
5. FT3 fidelity: `C9`, `C10`, `C11` (need the local Gerbode corpus).
6. Publication and source model: `C12`, `C13`, `C14`.

`S` items run in parallel with the `C` chain whenever their dependencies allow;
S2–S5, S7–S10, S18 and S19 need nothing outside the repository.
`docs/ui-fix-plan.md` holds the evidence and acceptance for `C3`–`C6` and
`S2`–`S8`; tick items there as well.

---

## Complex tasks (owner: Claude)

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
  4. Delete the test-only grid primitives `clear_cell`, `clear_cell_note` and
     `apply_duration` (`petrucci.input.tablature.grid`) and the `grid` setting,
     which no longer affects typing.
  5. Lay out bars that are not full against their meter, not their content:
     today an incomplete bar re-spaces while typing and `beatsnap=soft` centres
     a lone event.
  6. Pass `cursor_event` through the duet renderer (it is `None` there, so the
     duet cursor still uses the scaled column).
- Acceptance: the grep above returns nothing; TAB save/reopen, MIDI, MusicXML,
  and LilyPond outputs are unchanged for every repo TAB file and fixture.

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
  2. A single melody line is stored in the format's own `M` music line
     (`C15` step 1); anything more goes to the `C15` sidecar. No new syntax
     inside `.tab` (maintainer decision, 2026-09-29).
  3. Notation-staff typing: the `C3` onset cursor moves onto notation staffs, and
     edits go through `apply_note_input` with the same undo, read-only, and save
     rules as tablature.
- Acceptance: typed pitches produce the same TAB/MIDI/LilyPond output as the
  equivalent fret entry; notation parts survive save/reopen; keyscript fixtures
  for notes, chords, rests, ties, and lyrics.
- Depends on: `C6`, `C15`.

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

### C15. Full original TAB format with a warned sidecar for the rest

Why complex: defines the save contract for every document, changes a file format
boundary, and today loses user data on open and save.

Maintainer decision (2026-09-29): `.tab` is the original `tab` program format
(Wayne Cripps) and must be supported fully, with no Oud-only syntax. Content the
format cannot hold is never dropped silently: the save warns and writes that
content to a sidecar in a format Oud already reads and writes.

`docs/tab-format.md` holds the format summary, the reference-parser recipe
(`tab -v` from <https://github.com/mandovinnie/Lute-Tab>), and the support
table. Every **Lost** and **Partial** row there is a step here. Reading
without data loss, writing the program's syntax, and verbatim preservation of
unedited lines are done (see `DONE.md`).

`.tab` has first-class support but is not Oud's main format (see Format goals).

- Files: `oud/importers/tab.py`, `oud/exports/export_tab.py`,
  `oud/editor/services/io/files.py`, `oud/editor/services/io/loading.py`,
  `oud/presentation/cli_convert.py`, `docs/tab-format.md`.
- Steps:
  1. Keep marks on edited chords: today an edited chord line is written fresh
     and loses its ornaments, fingerings and `M`/`T` text (see
     `docs/tab-format.md`). Needs the marks in the model (`Note` has ornament
     and fingering fields). Triplets need tuplet timing in the chord model.
  2. Sidecar: when a save holds content TAB cannot express (several notation
     staffs, lyrics beyond `T` text, anything the table marks unsupported),
     write `name.tab` plus `name.musicxml` with that content and warn, naming
     both files and what went to the sidecar. Replace the `TabExportError`
     refusal with this. Write no sidecar when TAB holds everything; delete a
     stale sidecar only if Oud wrote it.
  3. Load: opening `name.tab` also reads `name.musicxml` when present; a
     sidecar that does not match (bar count, parts) is reported and opened
     read-only rather than guessed.
  4. Same rules for `oud convert` to `.tab`.
- Acceptance: every support-table row is Supported or preserved verbatim; a
  hand-written fixture per row round-trips byte-identically; an integration test
  (marked, skipped without the program) runs `tab -v` on Oud output and on the
  source and compares the parsed chords; a piece with a notation staff saves to
  `.tab` + `.musicxml`, warns, and reopens identical; a TAB-only piece writes no
  sidecar.
- Depends on: nothing open.

### C16. MusicXML as the default save format (trial)

Why complex: changes the save contract of every new document and which files
Oud may overwrite; a lossy round trip would lose user work on every save.

- Files: `oud/exports/musicxml.py`, `oud/importers/musicxml.py`,
  `oud/editor/core/document.py`, `oud/editor/services/io/files.py`,
  `oud/editor/services/bootstrap.py`, `docs/user-guide.md`.
- Steps:
  1. Ornaments, fingerings and text in the MusicXML round trip, once `C4`
     moves them into the model (the rest of the round trip is lossless, see
     `DONE.md`).
  2. Trial feedback: decide whether MusicXML stays the default after use
     (`:w`, new documents, projections). `oud convert` still needs an explicit
     output path.
  3. Duet FT3 scores stay view-only: they keep two lute parts in one bar list.
     Editing them needs a second tablature part in the model.
  4. Notation-staff details MusicXML could carry but Oud does not write yet:
     ornaments, fingerings, slurs, fermatas, beams, clefs and key signatures of
     imported staffs (`oud/exports/musicxml_staffs.py`).
- Acceptance: ornaments, fingerings and text survive the round trip like the
  rest (default save, native reopen and the lossless core are done, see
  `DONE.md`).

---

## Not complex tasks (open to any contributor)

These are sized for one focused session each. Work them in any order.

How to work an `S` task:

1. Read `AGENTS.md`. Run `./scripts/quality.sh` once before changing anything.
2. Write the acceptance test first and watch it fail.
3. Change only the files the task names. Keep functions at complexity 7 or
   less and modules under 1,000 lines (the gate checks both).
4. Run `./scripts/quality.sh` until every line says `[ok]`.
5. Delete the task here, add an entry at the top of `DONE.md` (what changed,
   the test names, the gate numbers), and commit with a short imperative
   subject.

If a step turns out to need a model or format change, stop and move the task to
the complex list with a note instead of widening it.

### S3. Lock the shared help text with a test

- Where: the help overlay (`compose.py:49`) and the `less` pager
  (`show_help` in `oud/editor/commands/handlers/misc.py:44`) both print
  `help_lines(state)` from `oud/editor/core/input/help.py:61`. Only plugin
  mode differs (it shows `plugins/<name>.txt` in the pager).
- Do: add a test that, for each key style (`vim`, `vim+arrows`, `casual`,
  `casual+arrows`; the `keys` setting, see
  `tests/test_keymap_table.py`), captures the text passed to the fake `less`
  (`run_fn`, as in `tests/test_tui_commands_exec.py:78`) and compares it with
  `help_lines(state)`.
- Acceptance: the new test passes; no production change is expected. If it
  fails, make the overlay and pager use the same lines.

### S4. Say what is wrong with a bar's length

- Where: `bar_meter_marker` in `oud/editor/services/screen/rhythm.py` returns
  `M` when the cursor bar's events do not fill its meter; the status row shows
  it as the `meter` segment.
- Do: return `meter:<content> of <meter>` instead, where content is
  `bar_content_length(bar)` (`petrucci/input/tablature/mutation.py:195`,
  whole notes) written over the meter's denominator, for example
  `meter:5/8 of 3/4` or `meter:7/8 of 3/4`. Keep `None` for a full bar, an
  empty bar and an unknown meter. Rename `METER_MISMATCH_MARKER`.
- Acceptance: tests in `tests/test_editor_status_row.py` for a full bar (no
  segment), an underfull bar and an overfull bar in 3/4, and a 6/8 bar.

### S5. No `col:` in the status row

- Where: `_position` in `oud/editor/services/screen/status.py:184` falls back
  to `col:N` when `parse_time_signature_value`
  (`petrucci/core/music/time.py:4`) cannot parse the meter. It returns `None`
  for `C|` and single numbers such as `3`.
- Do: (1) parse `C|` and `C/` as 2/2 in `parse_time_signature_value`, with a
  test in `tests/test_petrucci_time.py` (create it if missing); (2) when the
  meter still does not parse, show `ev:<k>/<n>`, the cursor's stop number
  among `bar_stops(state, bar)` (`oud/editor/core/coordinates.py:123`).
- Acceptance: tests for a 3/4 bar (`beat:`), a `C|` bar (`beat:k/2`), and a
  bar with meter `3` (`ev:`); `grep -rn '"col:' oud` finds nothing.

### S7. The staff label overwrites the tablature

- Where: `petrucci/adapters/piece_view.py:253` paints `lute` five columns left
  of the first measure (`measure_boxes[0].x - 5`), over the staff lines when
  the measure starts closer to the edge.
- Do: reserve the label's width (plus one space) before the first measure of
  every system, or leave the label out when the terminal is narrower than the
  label plus one measure.
- Acceptance: a regression test that renders a solo TAB piece and a piece with
  a notation staff (build one like `_layered_piece` in
  `tests/test_layered_scores.py`) at 80x24 and 120x40 and checks that the
  staff's first column still shows its line character.

### S8. One label for the tablature staff

- Where: the focus list calls the lane `Tab`
  (`oud/editor/navigation/view/focus.py:44`) while the staff is drawn as
  `lute` (`petrucci/adapters/piece_view.py:198`).
- Do: define the label once (a constant in `petrucci/adapters/piece_view.py`)
  and use it in both places.
- Acceptance: a test that the status `focus:` text equals the drawn staff label
  for a solo piece and for a piece with a notation staff.

### S9. Checksums for companion MIDI files

- Where: `scripts/corpus/midi/references.py` fetches and caches companion MIDI
  files; `scripts/corpus/midi/audit.py` reports on them. Neither records a
  checksum, so a changed or stale cached file goes unnoticed.
- Do: add the SHA-256 of the cached file to `ReferenceFetch` and to the audit
  report; when a report names a checksum and the cached file's differs, report
  `stale companion MIDI: <path>` before any parity check.
- Acceptance: tests with small files in `tmp_path` (no network): a matching
  file passes, an altered file produces the diagnostic.

### S18. `oud convert` without an output path

- Where: `oud/presentation/app.py:210` makes `output` required;
  `convert_command` is in `oud/presentation/cli_convert.py:167`.
- Do: make `output` optional (`nargs="?"`); when it is missing, write
  `<input stem>.musicxml` next to the input (MusicXML is the default format,
  see `C16`). Existing files still need `--force`. Reading from `-` still
  needs an explicit output.
- Acceptance: tests in `tests/test_cli_contract.py`: `oud convert x.tab`
  writes `x.musicxml`; a second run without `--force` fails with the existing
  "exists" error; `oud convert - ` without output is a usage error.

### S19. Fermatas and slurs on notation staffs in MusicXML

- Where: `oud/exports/musicxml_staffs.py` writes notation staffs and
  `oud/importers/musicxml_staffs.py` reads them back. `MelodyEvent` has
  `fermata`, `slur_start` and `slur_end` (`petrucci/core/model.py`), which are
  not written yet.
- Do: write `<notations><fermata/></notations>` and
  `<slur type="start|stop" number="1"/>` inside the note's `notations`
  element (after any `tied`), and read them back into the same fields.
- Acceptance: extend `_layered_piece` and `_staffs` in
  `tests/test_layered_scores.py` with a fermata and a slur pair; the MusicXML
  round-trip test still passes.

### S10. Document the supported historical-notation matrix

- Add a table to `docs/supported-behavior.md` that lists each historical
  construct as supported, partial, experimental or unsupported, with the test
  that proves it. Follow the table format of `docs/tab-format.md`. Enforcement
  is part of `C13`; this task is documentation only.

## Blocked tasks (need data, tools, a host, or design judgement)

Not suitable for unattended work: each needs something the cloud environment
does not have, or open-ended judgement.

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
  license and expected interpretation before any is used. **Needs** a licensing
  judgement per source.

### S14. Advanced terminal engraving review (experimental modes)

Opt-in renderers only; the default ASCII and pretty modes are unaffected.
**Needs** visual review on real terminals and fonts.

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
