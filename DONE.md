# DONE

- 2026-09-13: Fixed consumer integration regressions in proportional engraving:
  accidentals/editorial prefixes no longer move the onset notehead, and staff
  lines fill the viewport after short measures. Clipped measures no longer
  invent an edge barline or prematurely hide the last visible notehead.
  Replaced per-sample 257-point pitch tables with exact octave-local
  interpolation. Added nine public-API regressions across these changes.
  Validation: Ruff lint/format and Ty pass; 1,665 tests pass with 11 skips,
  95.08% coverage. Voce's exact-pitch/accidental overlay and original smooth
  scrolling regressions also pass.

- 2026-09-13: Verified the LilyPond boundary remains export-only. The importer
  tree contains no LilyPond parser, and `.ly` is used only at the export,
  validation, documentation, and test boundaries. Corrected the stale backlog
  item in `TODO.md`.

- 2026-09-13: Closed the Petrucci/Voce notation handoff with bounded lifecycle
  regressions, reproducible benchmark thresholds, proportional-overlay and
  hidden-meter examples, cache ownership documentation, and a consumer migration
  map. Assessed canonical accompaniment extraction and deferred implementation
  until explicit tempo and bounded-repeat contracts exist. The 96-event,
  66-replacement reference workload retained 3.742 KiB of traced Python heap
  after cache clearing; detailed frame measurements are in the handoff report.
  Validation: Ruff lint and format, Ty, and 1,656 tests pass with 11 skips and
  95.07% coverage.

- 2026-09-13: Integrated exact proportional timeline anchors into the notation
  engraver through the public `layout_score_proportional` API. Fixed-scale
  layouts preserve logical off-screen span endpoints, expose clipping and
  quantization collisions, and keep the ordinary respaced layout isolated.
  Added canonical breve and dotted-breve note/rest engraving with distinct
  semantics, correct augmentation dots, and no synthetic stems, flags, or ties.
  Validation: Ruff lint and format, Ty, and 1,654 tests pass with 11 skips and
  95.04% coverage.

- 2026-09-13: Added exact source-neutral timeline and pitch projection APIs.
  `project_timeline` preserves measure, event, split-segment, and span identity
  at a caller-selected `Fraction` origin/scale, reports viewport clipping and
  quantization collisions without respacing, and reserves an explicit preamble.
  Written and continuous pitch projection supports active treble/bass clef
  changes, accidentals, interpolation, viewport offsets, and explicit rounding.
  The remaining proportional engraver integration stays blocked in `TODO.md`.
  Validation: Ruff lint and format, Ty, and 1,648 tests pass with 11 skips and
  95.03% Petrucci coverage.

- 2026-09-13: Established the Petrucci timeline foundation: canonical measures
  retain exact pickup/irregular extents, aligned staffs validate shared
  boundaries, all staffs consume shared onset anchors, clipped events retain
  logical span geometry, written duration spelling supports breve values, and
  staff state plus semantic cells use object-owned indexes. Nested timeline and
  FT3 assembly modules under their domain packages and made the remaining
  projection/engraving/performance work an explicit blocking gate in `TODO.md`.
  Validation: Ruff lint and format, Ty, and 1,643 tests pass with 11 skips and
  95.05% Petrucci coverage.

- 2026-09-12: Retired the remaining test and corpus-script `C901`/`PLR0917`
  suppressions by extracting terminal, snapshot, command, PTY, report, and MIDI
  event helpers. Added export-boundary signature coverage and refreshed the
  architecture debt inventory; validation was not run in this change.

- 2026-09-12: Retired all production `C901` and `PLR0917` suppressions by splitting
  editor, importer, playback, and engraving coordinators and making render/export
  boundaries keyword-explicit. Updated direct callers and the architecture debt
  record; validation was not run in this change.

- 2026-09-12: Retired the next five legacy C901 suppressions by separating
  tablature assignment search, overlay key handling, assignment validation,
  `:set` token dispatch, and metadata preset conversion. Updated the
  architecture debt inventory; validation was not run in this change.

- 2026-09-12: Retired five legacy C901 suppressions by splitting tab and
  MusicXML measure emission, FT3 LilyPond markup collection, editor bootstrap,
  and dynamic system-start planning into focused operations. Updated the
  architecture debt inventory; validation was not run in this change.

- 2026-09-12: Removed the GitHub Actions workflow by project decision; local
  quality and release checks are authoritative. Vulture reported no
  high-confidence findings (`--min-confidence 80`) after parser repair. Added
  shared engraving-matrix microcases for collision, rhythm, and mixed
  voice/lute/lyrics contracts. Validation was not run in this change.

- 2026-09-12: Fixed MusicXML round-trip ordering and rest-only measures, and
  updated the first-write regression for prefilled Save As. Added the complete
  `oud(1)` manual source, generated roff page, reproducible build, and
  user-local installation scripts. Refactored CLI dispatch to remove its
  active C901/PLR0911 findings, then retired all 236 repository PLR2004
  findings with domain-local constants and repaired the affected FT3/MIDI
  parser control flow. Validation: full Ruff, Ruff format, and Ty pass; full
  pytest passed with 1,631 tests, 11 skips, and 95.18% Petrucci coverage.

- 2026-08-10: Reduced corpus-wide companion-MIDI discrepancies with source-provenance tuning profiles, diatonic extended basses, independent notation-only playback, corrected repeat-section advancement, and bar-duration registration for completely mapped note staffs. Mixed voices retain their internal rhythm instead of snapping to lute attacks; *Can she excuse my wrongs?* improves from 0.674 to 0.913 normalized comparison score. Optional companion tests now reject stale MIDI revisions and compare pitch evidence without treating PPQ or absolute timing as semantics. The cached, non-redistributed 514-score audit reports 224 exact, 420 at or above 0.90, 11 best-fit transpositions, 99 weak cases, 22 below 0.50, and no silent exports. Validation: Ruff, Ruff format, Ty, and 1,626 tests pass with 11 platform/tool/evidence skips under an 8 GB memory cap; Petrucci coverage is 95.15%.

- 2026-08-09: Added a non-redistributing companion-MIDI audit for every fixed FT3 manifest. It derives authoritative Gerbode MIDI URLs, caches payloads and 404 evidence under ignored `downloads/`, preserves unique source paths, parses multi-track running-status MIDI, and compares onset chords independently of PPQ, tracks, patches, and absolute timing. All 514 unique corpus scores now have downloaded companions and comparison records: 194 exact, 359 at or above 0.90 onset similarity, and 155 below it. Danyel's *Leaves Be Green* now uses its documented nine-course sounding scordatura with explicit provenance and source tuning takes precedence over the editor default; its comparison improves to zero transposition, 0.960 onset similarity, and 0.932 pitch overlap. Validation: Ruff, Ruff format, Ty, and 1,619 tests pass with 10 platform/tool skips and 95.14% Petrucci coverage.

- 2026-08-09: Added Gerbode publication parity for Dowland's *Can she excuse my wrongs?*: FT3 vocal/lyric rows now retain two registered verse lanes without printable coordinate noise, LilyPond normalizes every staff to one canonical source-bar timeline, and the Petrucci profile emits eight five-bar systems on two letter pages with boxed end-bar numbers, six main lute courses, separate bass courses, and un-beamed rhythm flags. The LilyPond exporter now owns explicit timing, registration, style, document, and voice layers; a repository architecture test prohibits importer/exporter coupling. Validation pending at the user-request boundary.

- 2026-08-09: Replaced the flat Petrucci package with six directional domains and subdivided rendering, engraving, note input, tablature input, terminal presentation, and core music ownership. Applied the same seven-direct-entity invariant to every package under `oud` and `petrucci`, grouped Oud presentation/services plus LilyPond, MIDI, and FT3 internals, and removed obsolete root test limits and generated cache/build/MIDI debris. Public `petrucci` symbols and FT3/export entry points remain canonical; no forwarding modules were retained. Validation pending at the user-request boundary.

- 2026-08-09: Made Bossinensis's twelve-stanza *Felice fu quel dì* the first Gerbode/LilyPond publication benchmark. Recovered every single-row coda syllable, scoped the explicit final-only coda to the last stanza, registered intro/coda marks, added typed dense-score system/page planning, and placed voice/lyrics above tablature by default. Validation: Ruff, Ruff format, Ty, and 1,539 tests pass with one platform skip and 95.07% Petrucci coverage. Warning-free two-page A4 PDFs compile under LilyPond 2.26 in 2.47 seconds/93 MB and 2.24 in 3.03 seconds/129 MB for comparison with the public Gerbode edition.

- 2026-08-09: Made LilyPond 2.26 the explicit publication baseline while retaining a configured 2.24 compatibility target; added TOML binary selection, registered manual barlines, deterministic timing resets, beam normalization, lyric cleanup, role-appropriate clefs, legal line breaks, pinned paper spacing, and dual-engine compiler regressions. Validation: all four curated FT3 publications compile without warnings under both engines; Ruff, Ruff format, Ty, and 1,537 tests pass with one platform skip and 95.07% Petrucci coverage.

- 2026-08-09: Established an export-only linked engraving program: a shared Petrucci/LilyPond quality matrix records translated LilyPond 2.24.4 and MuseScore 4.6.0 invariants; `lyprofile=petrucci` applies the default publication hierarchy with `classic` as a diagnostic fallback; and generated output has an executable compiler/warning regression. Validation: Ruff, Ruff format, Ty, and 1,533 tests pass with one platform skip and 95.07% Petrucci coverage.

- 2026-08-09: Replaced the flat `oud.editor` namespace with six directional domain packages: core, navigation, editing, services, commands, and interaction. Canonical imports and architecture-debt paths now use the hierarchy, obsolete flat modules were removed rather than wrapped, and a structural regression enforces at most seven direct entities per package. Validation: Ruff, Ruff format, Ty, and 1,530 tests pass with one platform skip and 95.07% Petrucci coverage.

- 2026-08-09: Added public `NotationLayoutPolicy.justify_last_system` control for final and one-system notation layouts. Final justification fills the available measure width, remains opt-in, and does not stretch nonfinal forced-break systems. Replaced positional box-fitting options with a typed request and added generic fitting plus public layout regressions. Validation: Ruff, Ruff format, Ty, and 1,530 tests pass with one platform skip and 95.07% Petrucci coverage.

- 2026-08-09: Published six companion-MIDI playback comparisons, including an explicit invalid empty reference; introduced source-independent diplomatic mensuration/proportion records and separate editorial meanings with stable identities; split insert dispatch and command completion complexity; and replaced three high-arity layout/rhythm surfaces with typed requests. Validation: Ruff, Ruff format, Ty, and 1,530 tests pass with one platform skip and 95.07% Petrucci coverage.

- 2026-08-09: Resolved all 14 remaining FT3 variants from the complete direct composer-index audit. Added PDF-confirmed later right-hand fingerings, bracket/barre variants, source layout flags, compact page/exercise records, editorial annotations, and a conservative one-staff notation-only mapper that prevents Couperin viol bytes from becoming fake tablature. The locally cached v8 fixtures expand the fixed corpus to 514. Validation: Ruff, Ruff format, Ty, and 1,517 tests pass with one Darwin-only skip and 95.13% Petrucci coverage; a checksum-new `04v_allison_spanish_measures.ft3` audit reports zero unresolved values, records, warnings, or load errors.

- 2026-08-09: Expanded the fixed FT3 compatibility corpus from 415 to 500 checksum-disjoint public scores and decoded PDF-confirmed right-side `+` (`0a00`) and `*` (`4000`) tablature ornaments. The v7 audit also bounded, rather than hid, layered exercise records and four remaining note-extra families. Validation pending at user request boundary.

- 2026-08-09: Added typed proportions, harmonics, glissandi, and notation fingerings with compact terminal and LilyPond output; synchronized all mapped MIDI staffs and polyphonic voice clocks/highlights; made current lyrics follow playback stanzas; retired five Petrucci complexity findings. Validation: mandatory Ruff, format, Ty, and pytest gate.

- 2026-08-09: Expanded the deterministic FT3 compatibility corpus from 300 to 415 semantically clean public payloads and retired five Petrucci framebuffer, lyric, geometry, bass-course, and playback complexity findings. Validation: mandatory Ruff, format, Ty, and pytest gate.
- 2026-08-09: Retired five Petrucci text and lyric complexity findings by separating notes sections, measure number policy, proportional text placement, lyric-event placement, and inter-syllable cue drawing. Validation: mandatory Ruff, format, Ty, and pytest gate.
- 2026-08-09: Retired the next five highest Petrucci complexity findings, consolidated duplicated tie-cue placement, and split framebuffer, rhythm-flag, and span-priority operations below the enforced ceiling. Validation: mandatory Ruff, format, Ty, and pytest gate.
- 2026-08-09: Retired the five highest Petrucci complexity findings, introduced typed bar-view assembly, and published an executable supported-behavior matrix with explicit FT3/Fronimo limits. Validation: mandatory Ruff, format, Ty, and pytest gate.
Technical change log. Keep short, append newest on top.

## 2026-08-09
- Expanded the fixed FT3 compatibility corpus from 263 to 300 disjoint,
  checksum-verified public scores with metadata and clean semantic audits.
  Split the five highest-complexity Petrucci render, spacing, tuning, and mark
  coordinators, lowering the C901 baseline from 134 to 129; the full uv quality
  gate passes.
- Added a checksum-verified Lully score with one canonical tie to curated
  Petrucci terminal, TAB round-trip, LilyPond, MIDI, semantic, and published-PDF
  acceptance. Split leading-row allocation from vocal layout placement,
  lowering the C901 baseline to 134; the full uv quality gate passes.
- Curated source-supported Petrucci excerpts for La Couperin trio, O felice,
  and Almain 11 with fixed terminal, TAB round-trip, LilyPond, MIDI, semantic,
  and published-score expectations. Recorded missing style provenance, ties,
  tuplets, and grace notes as explicit corpus work, bumped the version to
  0.4.0a1, and split system-fit validation to lower the C901 baseline to 135;
  the full uv quality gate passes.
- Added deterministic French and Italian transaction pipelines covering
  canonical editor state, terminal rows, TAB save/reopen, LilyPond, and MIDI.
  Split vocal fallback inference, semantic-canvas cluster painting, and terminal
  valued-symbol selection, lowering the C901 baseline to 136; the full uv
  quality gate passes.
- Added French and Italian transaction/keyscript acceptance fixtures for extra
  bass courses, repeated chords, course movement, attachment retention, and
  mixed note/chord/rest undo. Editor transactions are now intrinsically atomic.
  Split TAB metadata, chord, and segment parsing into focused state owners,
  retiring all three importer findings plus the settings-option dispatcher and
  lowering the C901 baseline to 139;
  the full uv quality gate passes.
- Added explicit full-score and focused-staff terminal modes. Full-score mode
  keeps all mapped notation and tablature staffs in one layout while staff
  focus vertically reaches tall scores without moving the logical cursor;
  focused mode renders one selected voice or tablature. Added upstream-inspired
  beamlet, grace, grouped-tuplet, broken-span, volta, and repeat-barline
  regressions, bounded partial beams away from barlines, and grouped one tuplet
  bracket per run. Split three complexity findings; the baseline is now 143.
- Made multi-stanza FT3 songs compact by selecting lyrics before horizontal and
  vertical layout. Terminal display now defaults to the first stanza, supports
  `first`, selected `current`, `all`, and full hiding, and reports the selection
  in `:info`. Corrected flat pitch parsing so Felice's third-tactus `bb` sounds
  as B-flat instead of B-natural; focused regressions cover the real score.
- Closed seven small Petrucci slices: atomic Italian two-digit replacement and
  deletion, invalid-boundary tests, note/rest replacement tests, one Oud Italian
  insert path using `TabEditTransaction`, focused time-signature row helpers, and
  `MelodyEvent.source_id` propagation through canonical notation and terminal
  semantic cells. The function-level debt baseline is now 146.
- Added public one-cell terminal notehead overrides without replacing the active
  pretty/safe glyph inventory; added a source-independent typed tablature
  transaction API for fret, course, rational onset, duration, note/chord/rest,
  deletion, typed changes, and stable errors. Oud cell/rhythm clearing and entry
  now reuse Petrucci mutation primitives. Split width planning and tuning labels
  from `petrucci/terminal/view/model.py`, retiring the final oversized module and reducing
  the function-level debt baseline to 147.
- Retired five Petrucci library boundary findings without changing its public
  contracts: measure and staff validation, score-layout reference and bounds
  validation, collision-cell scanning, and tuning-token parsing now have focused
  ownership. The architecture baseline is now 149 complex functions and one
  oversized module.
- Retired the two largest remaining coordinator findings. FT3 import now separates
  document metadata, body classification/decoding, bar assembly, and piece
  finalization; legacy TAB export now separates immutable export policy, source or
  edited chord projection, header generation, and serialization. Public signatures
  and focused importer/export behavior remain unchanged. The baseline is now 154
  complex functions and one oversized module.
- Retired the highest architecture finding by replacing the complexity-53 undo
  coordinator with a typed action context and immutable responsibility-specific
  handler registry. Corrected the debt gate so reduced scores are improvements,
  while higher and duplicate findings remain regressions; moved Felice integration
  cases out of the generic FT3 module. The baseline is now 156 complex functions
  and one oversized module.
- Added viewport-only navigation for long read-only scores: `K/J` or `W/S`
  move by rendered system, `[` and `]` jump across section/page boundaries, and
  counted jumps preserve the logical score cursor. Status now reports the visible
  system range plus available FT3 section and page context. Regression tests cover
  cursor preservation, counted boundaries, and status context.
- Matched Bossinensis's *Felice fu quel dì* mixed-score structure: decoded its
  printable FT3 lyric-position bytes into twelve verse lanes, removed singleton
  control fragments from comments, and rendered conventional soprano notation
  above six-course French tablature on one shared system grid. Mixed playback
  now marks both the canonical vocal event and corresponding tab chord; partial
  content is clipped only at the terminal's lower edge. Interactive open now
  reports missing paths without replacing the current score or raising.

## 2026-08-08
- Made vocal-only FT3 viewing use a compact full-score layout: all mapped voices
  remain visible up to the terminal's lower border, with deterministic clipping
  below it. Voice focus now selects canonical cursor/playback highlighting and
  MIDI projection without replacing the displayed score. Compact mode removes
  repeated measure rows, tab-driven stems, blank staff gaps, and polyphonic FT3
  control fragments misread as singleton lyrics. Correct line/space pitch
  geometry, within-system focus scrolling, explicit playback markers, and
  separate-channel MIDI for every imported vocal staff complete the viewer path.

## 2026-08-04
- Added Petrucci's immutable, source-independent standard-note transaction API:
  nearest-octave or explicit pitches, accidentals, persistent dotted/tuplet
  duration, voices, chords, rests, grace style, repitch/replacement/deletion,
  ties, slurs, lyrics, deterministic IDs, atomic rollback, and stable errors.
- Added a fixed one-time 100-score Gerbode manifest disjoint from all earlier
  corpora. Public note transactions exactly reconstruct every canonical notation
  score and more than 20,000 independently projected sounding TAB events; the
  downloaded FT3 payloads remain ignored and excluded from release artifacts.
- Closed release artifact hygiene with wheel/sdist allowlists, payload and
  development-file rejection, typed-package checks, and isolated Petrucci import
  verification without Oud or curses.
- Closed the Unix conversion contract: text pipelines use `-`, diagnostics and
  stable exit statuses are separate from primary output, existing files require
  `-f`, all file publication is atomic, and failed PDF builds preserve `.ly`.
  Corrupt FT3 input now fails explicitly instead of becoming a blank score.
- Kept CI acceptance macOS-only and added every fixed corpus manifest to its
  deterministic fetch step.
- Validation: no tracked FT3 payloads; architecture debt 157/157 with one
  oversized module; Ruff, Ruff format, Ty, and release artifacts pass; 1,340
  tests pass with one Darwin-only skip at 86.64% coverage; 401/401 local FT3
  files load without errors or warnings.

## 2026-07-19
- Added a fourth fixed, one-time 63-file FT3 manifest with no URL or digest
  overlap, bringing the random compatibility corpus to 263 files. All 63 new
  files load and pass the semantic audit without warnings or unresolved values;
  two additional published PDFs confirm under-`v` and combined fingering bits.
- Split normal-mode dispatch, Petrucci staff/rhythm/system rendering, FT3 import,
  LilyPond and MIDI export, and four oversized test modules by responsibility.
  The enforced debt baseline is now 158 complex functions and one oversized
  module; the remaining work is tracked as P2 rather than a release blocker.
- Validation: no tracked FT3 payloads, architecture and isolated Petrucci wheel
  gates, Ruff, Ruff format, Ty, and 1,300 tests pass with one Linux-skipped
  Darwin test at 86.74% coverage; 300/300 local corpus files load without
  warnings.
- Split both 2K-line Petrucci modules by ownership. `render_system.py` is now
  671 lines and `notation_layout.py` 801; every extracted rendering/layout
  module is below 1,000 lines. The former complexity-162 renderer is now 70,
  and the exact debt baseline fell to 166 findings and nine oversized modules.
- Removed game-result policy from Petrucci: no overlay/result enums, feedback
  lane, confidence, or hit/miss styling remains. Semantic roles, IDs, clipping,
  and `cells_for()` let consumers decorate their own states after typesetting.
- Added horizontal viewport translation with separate paint and layout widths.
  Moving `x_offset` repaints one cached layout while preserving translated
  event-cell identity; pretty and safe modes preserve identical semantic maps.
- Moved viewport and prompt-history state into `oud.editor` and made the debt
  gate reject `curses` or `oud.presentation.tui` imports from editor, importer, exporter,
  playback, plugin, and Petrucci modules.
- Made `petrucci` a real top-level typed package in the Oud wheel and removed
  the ambiguous `oud.core` grouping. FT3/TAB/MusicXML import, playback timing,
  plugin records, and editor tablature assignment now have explicit package
  owners; no old-path forwarding modules remain.
- Added exact source-neutral `FlowEvent` adaptation for external consumers,
  including chords/rests, voices, lyrics, unusual meters, overlapping active
  events, measure-crossing splits and ties, source-to-segment identity, and
  precomputed-layout painting for playback updates.
- Added an isolated wheel consumer gate proving the public `petrucci` surface
  imports without `oud` or curses. A 256-event benchmark measured about 177 ms
  cold layout and 9.8 ms cached-layout plus repaint at 80x24 on this host.
- Enforced complexity 7 for new code and checked all existing suppressions into
  an exact non-growth debt baseline: 167 complex functions and seven oversized
  production modules plus four oversized test modules. CI now rejects new or
  growing complexity and 1,000-line module debt.
- Validation: architecture debt, isolated Petrucci wheel, Ruff, Ruff format,
  Ty, and 1,294 tests pass with one Darwin-only test skipped at 86.29% coverage;
  237/237 local FT3 corpus files load without warnings.
- Added a compact note/tablature typing workflow matrix derived from MuseScore's
  operation-and-score tests and LilyPond's one-feature regressions. Both key
  profiles now share French chord/rest/bass coverage; replacement retention,
  atomic undo/redo, and Italian two-digit save behavior are explicit.
- Added source-independent Petrucci decoding for Oud's editable tablature cells.
  Italian fret 10 round-trips as one note, while legacy TAB export rejects
  unrepresentable higher frets without creating a partial file.
- Added a third one-time, composer-stratified 50-score FT3 manifest. All 200
  fixed random scores pass the semantic audit; PDF evidence decoded left
  parentheses, under-fret hooks, a placement-layout record, and three score
  headings. External FT3 payloads remain ignored.
- Enabled bounded four-worker pytest execution with load-scope scheduling.
  Per-load text-record caching and single-pass line-feature checks reduced the
  200-score load benchmark from 38.9 to 25.1 seconds; the expanded no-coverage
  suite completes in 31.3 seconds locally.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,289 tests
  pass with one Darwin-only test skipped on Linux at 86.28% coverage; 237/237
  local corpus files load without warnings.
- Closed the Petrucci proper-score P0 gate. Dense independent voices use
  disjoint beam and cue lanes, whole-layout collision checks pass, narrow
  clipping retains event-owned markers, and structural plus ASCII text goldens
  cover 60, 80, and 120 columns.
- Preserved imported tuplets, grace notes, typed slurs, key/clef changes,
  irregular source timing, additional ornaments, and unaligned source lyric
  lines without guessing note onsets. All 15 notation-bearing files in the
  fixed 150-file corpus now adapt strictly.
- Routed vocal-only and focused mixed/polyphonic note or lyric staffs through
  canonical Petrucci rendering while preserving the default tablature path.
  Oud applies cursor and playback attributes after resolving stable source IDs,
  without moving score geometry or adding consumer state to Petrucci.
- Reduced `view_model.__all__` to its intentional public entry point; layout and
  rendering callers now import owned layout primitives directly.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,279 tests
  pass with one Darwin-only test skipped on Linux at 86.02% coverage; 187/187
  local corpus files load without warnings.
- Fixed the normal-mode count hang: numeric prefixes now saturate at 999,
  counted movement stops at boundaries or after one editable append, and
  read-only navigation cannot append bars. Page, staff-focus, and viewport
  counts execute as one bounded operation.
- Replaced rectangular duration/string probing with sparse duration change
  points and reused visual geometry within one counted motion. A 999-step,
  226-bar adversarial probe with million-index duration records completes in
  about 1-2 seconds locally instead of exceeding 30 seconds.
- Added regressions over both key profiles for every byte key and configured
  curses key after an oversized prefix, plus read-only append prevention,
  command-local geometry reuse, and billion-scale sparse duration coordinates.

## 2026-07-17
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,262 tests
  pass with one Darwin-only test skipped on Linux at 85.76% coverage; 187/187
  local corpus files load without warnings.
- Added a compact public Petrucci notation policy that can hide stems/beams and
  barlines and emit collision-safe written pitch labels.
- Preserved one logical onset for simultaneous voices while assigning
  deterministic visual lanes to common unison/second, rest, stem/flag, dynamic,
  same-verse lyric, and dense annotation conflicts. Monophonic score snapshots stay
  unchanged.
- Distinguished eighth, 16th, 32nd, and 64th rests in Unicode-pretty and
  ASCII-safe output. Expanded public-only neutral-host acceptance through
  repeated pitches, rests, cross-system ties, lyrics, compact output, resize,
  and active-system selection.
- Removed redundant new-score and read-only focus key hints from the persistent status area. Playback now follows the active score system by default, retains its viewport through rests, catches positions advanced during a slow full render, and remains disableable with `:set playbackscroll=off`.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, and 1,257 tests pass with one Darwin-only test skipped on Linux at 85.73% coverage; 187/187 local corpus files load without warnings.
- Separated FT3 meter codes from shared header flags. Nineteen records across 14 fixed-corpus files now retain their explicit meter; the published Gesualdo score confirms `0e 10` as a repeated `3/2` opening, and all four viol staffs adapt to canonical Petrucci notation.
- Stopped barline and empty notation records from promoting heuristic ASCII coordinate fragments into fake pitches. Relevant barline fragments remain typed control rows, while tablature payload bytes such as `_6(` no longer create synthetic notation staffs.
- Validation: no tracked FT3 payloads, both fixed 75-file semantic audits pass, Ruff, Ruff format, Ty, and 1,254 tests pass with one Darwin-only test skipped on Linux at 85.72% coverage; 187/187 local corpus files load without warnings.
- Added a second fixed 75-file Gerbode corpus with unique, previously unseen composer directories and no overlap with the first sample. All 150 fixed external files load without warnings and pass the semantic audit with no residual flags or unknown records; FT3 payloads remain ignored.
- Corrected lane-major mixed-score detection and the empty `0130` notation marker, so Berchem's 59-bar score maps to one tablature lane plus labeled alto and bass staffs instead of fragmented fake staffs. Typed empty layout records no longer produce unknown-staff warnings.
- Decoded and rendered PDF-confirmed courtesy accidentals (`8000` plus an accidental), editorial square brackets (`4000`), standalone tie continuation (`8000`), left apostrophe (`1600`), and the legacy open ninth-course form (`3c00`). Petrucci now carries courtesy, brackets, and imported ties through its public canonical model and semantic terminal frame.
- Added six FT3/PDF comparisons for the new corpus, bringing the documented matrix to 16 files, and bumped the alpha version to `0.2.0a2`.
- Validation: no tracked FT3 payloads, both fixed 75-file audits pass with zero unresolved semantics, 187/187 local corpus files load without warnings, Ruff, Ruff format, Ty, and 1,251 tests pass with one Darwin-only test skipped on Linux at 85.72% coverage. An isolated `0.2.0a2` wheel renders the new Petrucci courtesy-accidental and editorial-bracket semantics through its public API.
- Deepened the FT3-to-Petrucci adapter with per-voice timing, same-onset chord normalization, opposing polyphonic stems, cut time, repeats/endings, beams, fermatas, dynamics, and `+` ornaments. Meaningful lyrics remain strict; callers can explicitly select trustworthy note-only adaptation with `include_lyrics=False`.
- Added key-aware measure accidental state with natural cancellation and explicit/courtesy policies, distinct repeat forms, reserved ending/ornament/fermata lanes, and a complete public `EventLocation` map so external consumers can follow every canonical event across clipping, system scrolling, and resize.
- Removed Petrucci's eager curses import by keeping text attributes portable and translating them only in `CursesScreen`. An isolated wheel resolved all 64 public symbols and rendered a canonical score with `py.typed` present and no curses module loaded.
- Audited 15 representative real FT3 files without committing source payloads: 4 adapt strictly, 11 adapt in note-only mode, and the remaining 4 fail with explicit pitch or meter diagnostics. The four supported canonical scores retain 1,382 event locations across 60, 80, and 120 columns; only two events in the narrow Folle layout are explicitly clipped.
- Fixed Petrucci's narrow-layout identity contract: every canonical event ID remains in `ScoreLayout` even when its glyph cannot be placed, off-viewport events have no visible cells, and genuinely unknown IDs still fail explicitly.
- Reserved disjoint semantic rows for measure numbers, cross-system slurs/ties, dynamics, annotations, and lyrics. Caller decoration resolves exact cells by event ID without changing geometry; span endpoints and continuations use shaped ASCII-safe/Unicode glyphs instead of repeated fill characters.
- Moved MusicXML golden scratch output to pytest's isolated `tmp_path`, so tests no longer mutate the source fixture tree. Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,241 passed with one Darwin-only test skipped on Linux, 85.64% coverage, and 112/112 corpus files loaded without warnings.

## 2026-07-16
- Added Petrucci's source-independent standard-notation vertical slice: strict immutable score records with stable IDs and exact timing, measured system fitting, content-derived row budgets, semantic onset/layout elements, display-safe terminal painting, and cached layout independent of transient caller decoration.
- Added treble/bass notes and chords, rests, ledger lines, dots, stems, flags and beams, accidentals, conventional key-signature positions, barlines, tuplets, ties/slurs with cross-system segments, fermatas, dynamics, lyrics, ASCII/Unicode glyph policies, and exact event-owned cell geometry.
- Added a strict Oud note/lyric adapter and an independent consumer fixture that imports no Oud model. Built and installed the wheel in an isolated environment; public score rendering worked, `py.typed` was present, and importing `petrucci` did not initialize curses.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,223 passed with one Darwin-only test skipped on Linux, 85.54% coverage, 112/112 corpus files loaded without warnings, and an isolated built-wheel consumer smoke.

## 2026-07-13
- Prevented orphaned rhythm/staff rows by requiring a meaningful half-system before drawing a clipped preview; duet score view only adds complete paired systems. Dense bars forced onto their own system still fill the staff width. The TUI now drains up to 64 queued keys before one render, preventing delayed repeated movement after key release.
- Cached clean dynamic system plans across cursor-only frames while bypassing the cache for modified documents. Cursor-display regressions fell from about 95 seconds to 25 seconds locally, and representative frame time dropped from 0.20 seconds to 0.03-0.09 seconds.
- Made imported FT3 provenance complete and inspectable: `:info` lists bibliographic fields, source page/metadata, format, and every staff; `:notes` includes editorial text from all imported staffs; LilyPond headers/comments preserve the same metadata and source comments.
- Tightened FT3 score presentation against the published Dowland *A Fantasy*: systems use only their visible course height, the playback caret no longer reserves a row, opening systems retain more naturally sized bars, and every displayed system can carry an unbracketed source bar number.
- Removed stale playback highlights from cached base frames, reduced active playback polling to 10 ms, and resampled the MIDI clock after full score renders before drawing the current-note overlay.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,174 passed with one Darwin-only test skipped on Linux, 85.55% coverage, and 112/112 local corpus files loaded without warnings.
- Made casual controls functionally equivalent without key collisions: `d` moves right, `,` moves to the previous bar, `W/S` jump rendered rows, `Ctrl-Z/Ctrl-Y` undo/redo, and visual-mode movement no longer triggers Vim deletion.
- Rendered the next score system into any remaining terminal rows instead of hiding every system that does not fit completely; the status line and cursor-safe full-system viewport remain intact.
- Stopped stretching sparse final, manual-break, and explicitly capped systems across empty width. Width-limited systems still justify, configured editing grids remain stable, and multi-digit frets plus inline source marks retain collision-safe spacing.

## 2026-07-12
- Closed all five semantic failures in the fixed 75-file expansion. Decoded comma, apostrophe, smile, and caret ornaments; separated standard-note musical/layout fields; preserved chord onsets and source voices; and mapped La Couperin's two notation voices to one 77-bar bass-viol staff. The 75-file audit now has zero residuals, unknown records, or warnings.
- Manually compared 17th Century Grounds and La Couperin with their published PDFs, bringing the documented FT3/PDF matrix to ten files.
- Removed all Gerbode FT3 payloads and decoded dumps from the Git index, ignored FT3 suffixes repository-wide, added a CI publication guard, and retained only attribution plus URL/SHA-256 manifests. Added a deterministic fetcher that refuses unsafe URLs, path traversal, checksum drift, and implicit replacement.
- Expanded FT3 compatibility coverage with a one-time 75-file selection fixed in `tests/fixtures/ft3/manifests/ft3-random-75.json`. All 75 load without crashing; the five semantic failures and Couperin structural warning are bounded by regression tests and recorded in `TODO.md`/`docs/ft3-parity.md`.
- Removed discarded exponential string-assignment searches from LilyPond pitch emission. The 226-bar Buxtehude fixture exports in about 0.02 seconds instead of 15.1 seconds with byte-identical output; the full coverage gate fell from 7:06 to 3:43.
- Validation: no tracked FT3 payloads, Ruff, Ruff format, Ty, 1,157 passed with one Darwin-only test skipped on Linux, 85.33% coverage, and 112/112 local corpus files loaded without warnings.
- Closed the remaining release-usability P0 items: the first 80x24 help page now gives a complete open/create, note entry, undo, safe save, and quit path, backed by an executable first-score regression.
- Added a macOS-only PTY regression around the real curses loop. It verifies 80x24 -> 120x40 resize preserves the score cursor, source filename, modified marker, imported-projection mode, and TAB write target while keeping cursor and status on separate rows.
- Raised the enforced line/branch coverage floor to 85%, removed the unreachable partial preset converter superseded by the canonical pitch-preserving transform, and covered screenshot/snapshot release tools, corpus failures, the FT3 audit CLI, and plugin error workflows.
- Validation: Ruff, Ruff format, Ty, 1,144 passed with one Darwin-only test skipped on Linux, the 85% coverage gate (85.40%), and the 37-file corpus smoke check all pass locally; the FT3 semantic audit separately passes 36/36 files with zero unresolved records or values.
- Closed the bundled Gerbode FT3 semantic audit: 36/36 files now have zero residual note bits, vocal bits, unknown source records, or import warnings. Typed source provenance is stored once on `ImportedScore`, separate from decoded staff bars.
- Corrected FT3 boundary semantics from PDF evidence (`0x20` first ending, `0x40` second ending), decoded vocal beams/fermatas, Ich annotation groups, arpeggio segments and right-side `x` ornaments, and Passacaglia's editorial appendix page/section records.
- Completed polyphonic viewer/export behavior: every source voice has a complete logical bar map, staff focus changes the rendered voice, LilyPond emits all standard staffs with beams/fermatas, and vocal-only scores now drive MIDI and playback timelines.

## 2026-07-11
- Added a reproducible FT3 residual/raw-record audit and manually compared representative solo, mixed, duet, and three-verse vocal fixtures with Gerbode's published PDFs. Structural content agrees; exact source systems, pages, and edition engraving remain explicit P0 gaps. Decoded the real compositional `0x3500` barre plus left-finger value without residual loss.
- Added explicit read-only staff focus: `j/k` cycles projected Tab/Melody/Lyrics lanes, duet focus maps to the corresponding source staff bar, and the active focus remains visible in status. Added typed info/success/warning/error/confirmation messages with distinct portable terminal attributes.
- Fixed the macOS CI quality environment by declaring `pytest-cov` in the uv dev group and locking coverage dependencies. Applied the repository's Ruff format baseline and documented the formatter-required `COM812` exception; Ruff, format, Ty, 1109 tests, the 82.50% coverage gate, and the 37-file corpus smoke pass locally.
- Removed the root `app.py`/`cli.py` launchers and obsolete `oud.cli`; `oud` -> `oud.presentation.app:main` is now the single command path. Removed the former `oud.core` and `oud.presentation.ui` Petrucci aliases, migrated tests/scripts to canonical imports, and retained only real parser/domain modules plus the curses adapter.
- Closed the compatibility-layer static-analysis debt: Ruff and Ty pass, 1101 tests pass, and the local corpus smoke test loads 37/37 files with no errors or warnings.
- Added explicit document modes and separate source/write-target state. Tab-only FT3 opens as an editable projection with explicit Save As; mixed, vocal-only, and duet FT3 opens read-only so visible non-TAB layers cannot be lost.
- Replaced implicit `name.ft3.tab` writes with a shared `:w`/`:wq`/`:x` Save As flow, confirmed overwrite handling, truthful modified state, and source-preserving target reuse. ASCII export no longer marks a score saved.
- Added persistent filename, modified, document-mode, write-target, bar, and string/staff context; added acknowledgeable notices and an 80-column first-run/safety presentation.
- Added key-driven workflow regressions for save/cancel/overwrite/reopen and solo, mixed, vocal-only, duet, and TAB classification.
- Reframed the active roadmap around two user-facing alpha blockers: trustworthy FT3 edit/save semantics and persistent workflow context, with explicit macOS interaction tests and release acceptance criteria. Removed completed checklist entries from `TODO.md`; their outcomes remain recorded below.

## 2026-07-10
- Extracted the canonical score model and complete tab/vocal/note character-cell renderer into `petrucci`, with a reusable `typeset_piece`/`typeset_text` API and compatibility aliases for former `oud.core`/`oud.presentation.ui` paths.
- Improved import UX: malformed TAB files no longer silently replace an open score, partial TAB bars survive missing end markers, warning summaries point to `:info`, and all import warnings remain visible there.
- Closed the bundled FT3 viewer blockers: multipart note markers crossing the raw header boundary become note staves, unknown text remains visible as comments, observed bar headers are classified, vocal/multipart playback mapping is covered, and narrow multi-verse scores retain a visible bar.
- Closed the remaining FT3 backlog: typed the final score-settings record, eliminated unknown staffs across the bundled corpus, published duet cursor/playback maps, aligned sparse imported lyrics by source bar, and exported all supported non-tab staff variants to LilyPond.
- Finished automatable release polish: project URLs and alpha metadata, a renderer-generated README screenshot, a documented release procedure, and an audited decision to retain the existing non-personal commit metadata.
- Added `scripts/corpus/smoke.py` for local or bounded live lutemusic.org batches; it continues after per-file failures, classifies importer warnings, supports JSON output, and is wired into macOS CI. Release pass: 250/250 live files and 36/36 bundled files loaded with zero errors or warnings.
- Grouped transpose, retune, and reflow into explicit compound undo entries with regressions.
- Added a real-piece alpha workflow regression covering enter, correction, TAB save, MIDI/LilyPond export, and reopen.

## 2026-06-13
- Fixed `:play`/`M` playback regression: without an explicit end bar it again plays from the start bar to the end of the piece (the loop-range refactor had collapsed it to a single bar) — this was the "no sound on Linux" report.
- Made visual h/l movement track the rendered cursor exactly: the renderer publishes per-bar logical→display column maps (`cursor_display_maps`), movement steps one display cell per press and lands on each cell's note column (regressions in `tests/test_cursor_display_sync.py`).
- Fixed motions treating FT3 chord-index duration records as grid columns (`_note_cols`), which mistargeted note snapping in unflattened chord bars.
- Synced viewport block height with the renderer (always-reserved second stem row, melody staff for lyric-only pieces) and editor system planning with renderer minimum bar widths (time-cue padding, event gaps) — the cursor can no longer land on never-rendered systems.
- Added `:dark` / `:light` commands and `:set theme=auto|dark|light`: explicit fg/bg color pair plus painted window background for light-background terminals.

## 2026-06-12
- Publication prep: scrubbed personal absolute paths from DOCS.md/FT3.md/config.toml/tests, resolved .gitignore vs tracked-file conflicts, added lutemusic.org CC BY-NC-SA 4.0 attribution (`tests/fixtures/ft3/corpus/README.md`), added GitHub Actions CI (ruff + pytest on ubuntu/macos), and added a pytest/ruff dev dependency group with `uv.lock`.
- Moved to Python 3.11+ with stdlib `tomllib`; project now has zero runtime dependencies.
- Fixed light-theme low contrast: high-contrast mode uses bold on the terminal's default colors instead of forcing a white foreground.
- Added `:help` command that pages help text through less with TUI suspend/resume, plus a dispatch regression test.
- Removed scratch `examples/test.tab`; corpus check: all 43 local lutemusic.org files import without crashes (13 with partial-decode warnings).
- Reordered TODO.md for publication: P0 fix-now, P1 publication blockers (viewer coverage + alpha editing + mechanics), features pushed to P2+.
- Completed easy TODO cleanup: slimmed the `command_ops.py` compatibility facade, added loop playback for visual/current ranges, covered comment/gridflag/reflow tools, and added a dense synthetic snippet regression.
- Completed P1 edit foundation work: added cursor/deletable bar range helpers, routed normal-mode bar yank/delete through explicit range operations, and switched normal-mode movement to pure motion targets.
- Finished remaining P0 edit-mode cleanup: unified edit chord slots on raw chord positions, removed dead insert chord branches, made insert cursor snapping predictable, centralized post-insert advance, added visual delete/change, and recorded the short-term dual-representation decision.
- Fixed additional P0 edit-mode bugs: exact destructive chord targeting, file-open state reset, stave-break delete shifting, gliss/mark bar reindexing, count handling, and undo/redo cursor + clean modified-state restoration.
- Fixed first P0 edit-mode bugs: removed French lowercase duration-letter aliases, preserved insert-mode quit fallthrough, recorded chord flattening in undo, and grouped insert keystroke mutations into single undo steps.

## 2026-03-13
- Decoded `note-staff-raw` FT3 bars into imported `note` staffs instead of leaving them in generic unknown import buckets.
- Decoded `note-lyric-raw` FT3 bars into imported `note` + `lyrics` staffs.
- Split `barline-raw` FT3 material into a dedicated imported `barline` staff.
- Kept FT3 imported bar context (`time_sig`, `barline`, `repeat`) on imported score content.
- Reduced redundant TUI redraw during playback by only re-rendering on actual playback/message/resize changes.
- Tightened bottom vocal layout by removing the extra spacer row between tablature and note staff while keeping playback marker visibility.

## 2026-02-07
- Added reprise marker support end-to-end: `:repeat` now accepts structural + cue variants (`both`, `dc/ds`, `fine/coda`, `*alfine/*alcoda`) with normalization and limit handling in `oud/editor/editing/score/notation.py`.
- Added reprise export/render coverage: repeat cue marks are emitted in LilyPond export and tested in `tests/test_lilypond.py`.
- Finalized ASCII save parity check: `:wascii` output is validated against framebuffer snapshot in `tests/test_tui_commands_media.py`.
- Implemented and tested bars-per-line behavior (`:set barsperline=<n>`, `0=auto`) with new layout/render tests (`tests/test_editor_layout.py`, `tests/test_ui_render_split.py`).
- Added new testing suites:
  - `tests/test_tui_prompt.py` (prompt/update behavior paths),
  - `tests/test_render_matrix.py` (spacing/style/bass/marker matrix scenarios).
- Ran full quality under `.venv`: `ruff`, `ty`, and `pytest` all pass (`322 passed`, coverage `80.60%`).
- Continued command-layer split: moved media/playback/export command helpers into `oud/editor/services/media/operations.py` (`cmd_midi`, `cmd_lilypond`, `cmd_pdf`, `cmd_play`, `cmd_midicmd`, `print_pdf`) with wrappers kept in `command_ops.py`.
- Continued command-layer split: moved score-edit operations (`yank/paste`, `cmd_bar`, `cmd_stave`, `cmd_chord`) into `oud/editor/editing/score/operations.py` and kept wrappers in `command_ops.py`.
- Added direct tests for split modules in `tests/test_tool_and_load_ops.py` (`cmd_info`, `cmd_plugins`, `cmd_tool`, and basic `cmd_open` path cases).
- Continued command-layer split: moved `cmd_open` into `oud/editor/services/io/loading.py` with injected loader functions so test monkeypatch behavior stays unchanged.
- Continued command-layer split: extracted tool/view commands into `oud/editor/commands/plugins/tools.py` (`cmd_tool`, `cmd_info`, `cmd_plugins`) with wrappers retained in `oud/editor/commands/dispatch.py`.
- Continued command-layer split: extracted notation/time/repeat/ornament helpers into `oud/editor/editing/score/notation.py` with compatibility wrappers in `oud/editor/commands/dispatch.py`.
- Continued command-layer split: extracted file/source/ascii write handlers into `oud/editor/services/io/files.py` and kept thin wrappers in `oud/editor/commands/dispatch.py`.
- Kept compatibility for existing tests/monkeypatch paths by preserving public `command_ops` entrypoints.
- Re-ran full quality under `.venv`: `ruff`, `ty`, and `pytest` all pass (`233 passed`).
- Added `/Users/s/Documents/Python/frnm/DOCS.md` with full current feature/usage reference and workflows.
- Started command-layer split by extracting `:set` and style-conversion logic into `oud/editor/commands/handlers/settings.py` (slimming `command_ops.py`).
- Added Vim word-search parity in normal mode: `*`, `#`, `n`, `N`.
- Added `%` jump for tab matching (slur/tie/hold endpoints and repeat start/end markers).
- Added mark support in normal mode: `m{char}` to set, `' {char}` / `` ` {char}`` to jump.
- Added config-driven key remap hooks in keymap (e.g. `remap_move_left = "a"`).
- Added shared prompt history helpers and wired search prompt history navigation (`/` with up/down).
- Added Vim-like char find motions in normal mode: `f/F/t/T` with repeat `;` and reverse repeat `,`.
- Added MIDI playback animation timeline plumbing and live render highlight for current playback bar/column.
- Tightened spacing/layout rendering: compact bar width pass + per-system auto fit + dense flag spread to avoid overlap.

## 2026-01-30
- Moved all code into `oud/` package with root wrappers for `app.py` and `cli.py`.
- Updated imports/tests for `oud.*` package layout and plugin pathing.
- Folded `about_project.md` into `README.md` and removed the standalone file.
- Added TODO/DONE to `.gitignore`.

## 2025-02-14
- Moved help/info key handling into `tui/controller.py`.
- Added help/info bindings in `editor/keymap.py`.
- Moved help text into `core/help_text.py`.
- Completed layered architecture cleanup (core no longer depends on UI/TUI).
- UI rendering now depends on `core/view_model` only.
- Added help/info mode tests in `tests/test_tui_controller.py`.
- Added view model adapter for UI rendering (`core/view_model.py`).
- Added count bindings to `editor/keymap.py`.
- Moved render view-model helpers into `core/view_model.py`.
- Centralized normal action bindings in `editor/keymap.py`.
- Added `editor/init.py` to initialize editor state outside TUI.
- Centralized command/search mode key bindings in `editor/keymap.py`.
- Added insert-mode bindings table in `editor/keymap.py`.
- Moved curses main loop to `tui/loop.py` and slimmed `app.py`.
- Added UI adapter (`ui/adapter.py`) and removed curses dependency from `ui/render.py`.
- Centralized normal-mode key bindings in `editor/keymap.py`.
- Fixed settings loader import to avoid ty unresolved-import errors.
- Added Ctrl-C as a confirmed-quit path (matches q behavior).
- Added French duration digit mapping test coverage.
- Refactored command handlers into `editor/command_ops.py`.
- Moved verify logic into `editor/verify_ops.py`.
- Added `editor/load_ops.py` for file loading.
- Added `tui/viewport.py` and `tui/controller.py` for TUI wiring.
# Petrucci timed-flow and pitch-cue coverage

- Added opt-in simple/compound-meter beam grouping, explicit measures with pickups and meter/state changes, initial key/clef state, and lossless `WrittenPitch` flow input.
- Added semantic event/onset pitch cues that repaint cached layouts without changing score geometry.
- Added regression coverage for compatibility defaults, explicit-boundary failures, spelling preservation, meter beaming, and cue identity/reflow behavior.
# Upstream-derived notation quality matrix

- Translated applicable LilyPond 2.24.4 and MuseScore 4.6.0 software-test invariants into deterministic public-API tests without copying upstream fixtures.
- Extended typed duration support through 128th notes and four dots, added reversible half/double duration operations, and accepted enharmonic ties while preserving spelling.
- Corrected tablature minimum-fret handling for open strings and added generated tuning/string/fret round-trip coverage, extended-bass, duplicate-pitch, and explicit-failure cases.
## 2026-08-09

- Made the coverage-enabled default pytest gate serial and capped Linux test-process address space at 8 GiB to prevent xdist coverage OOMs.
- Enforced 95% package-wide Petrucci line coverage in the default pytest command, without source exclusions.
- Removed assertion-only type tests and redundant runtime type guards from typed Petrucci composition and rendering APIs.
- Retired all remaining Petrucci C901 debt by extracting focused duration, mark, width, playback, and paint operations.
- Passed the full quality gate: Ruff check, Ruff format check, Ty, and 1,507 tests with one skip; Petrucci line coverage is 95.13%.
