# TODO

## P0: Architecture debt retirement

CI now enforces complexity 7 and a 1,000-line module ceiling against the exact
non-growth baseline in `architecture-debt.json`; rationale, counts, and ownership
targets are in `docs/architecture-debt.md`.

- [ ] Decompose the remaining high-risk dispatchers to complexity 7, starting
  with `oud.editor.normal_actions.handle_normal` (87),
  `petrucci.render_system.render_systems` (70),
  `petrucci.render_rhythm_rows._render_rhythm_rows` (52), and
  `petrucci.render_staff_rows._render_staff_and_playback` (37). Preserve the
  existing key matrices, structural frames, and text goldens at each step.
- [ ] Split `oud/importers/ft3.py` and `_ft3_text.py` into container scanning,
  typed record decoding, staff assembly, text/lyric decoding, and normalization
  while retaining one public `load_ft3` operation and all corpus evidence.
- [ ] Split LilyPond and MIDI projection from serialization and external process
  execution; bring both exporter modules below 1,000 lines and complexity 7.
- [ ] Split `petrucci/view_model.py` by width planning, source projection, and
  tuning/display records, then split the four oversized tests by behavior.
- [ ] Retire the remaining 166 function-level C901 findings without raising limits,
  broad per-file ignores, compatibility wrappers, or count-only helper modules.

## P1: Note and tablature typing confidence

Reference model: MuseScore's `note_tests.cpp` drives real note-input operations
and compares complete score state, while its TablEdit fixtures separate normal
and dotted notes/rests, positions, voices, ties, tuplets, grace notes, and bass
courses. LilyPond's `input/regression` keeps one-feature tablature files for
string assignment, letter frets, open/additional bass strings, chord repetition,
dots beside two-digit frets, beams/slurs, ties, and grace notes.

- [ ] Define a public, source-independent Petrucci typing transaction API before
  moving editor mutation code. It must accept explicit pitch/fret, string,
  duration, voice, onset, rest/chord intent, and return typed changes/errors
  without importing curses, Oud editor state, FT3, or file I/O.
- [ ] Add standard-note typing once that API exists: nearest-octave letter entry,
  explicit accidental/natural spelling, rests, chord stacking, voices, duration
  persistence, dots, ties, tuplets, grace notes, and out-of-range pitch errors.
- [ ] Complete tablature typing matrices for French and Italian styles: open and
  two-digit frets, extra bass courses, same-onset chords, rests, repeated chords,
  string movement, full-bar overflow, invalid frets, and alternate tunings.
- [ ] Cover edit transitions and preservation: note-to-note repitch, note/rest
  replacement, delete, undo/redo, attachment retention, and no cross-voice or
  cross-string mutation.
- [ ] Add deterministic operation-sequence tests that compare canonical state,
  rendered semantics, TAB save/reopen, and LilyPond/MIDI export. Keep compact
  one-feature fixtures for failures; do not vendor MuseScore/LilyPond fixtures.

Minimal executable coverage now protects French chord/rest/bass entry across
both key profiles, replacement with attachment preservation, atomic
note/rest undo-redo, Italian fret 10 save/reopen, and an explicit TAB rejection
for unrepresentable higher Italian frets. Standard-note entry remains planned
because Oud currently provides a read-only canonical note model, not an editable
note-input state machine.

## P1: Credible FT3 viewer

Target: a mature read-only FT3 viewing workflow, not Fronimo editor parity. Native
FT3 writing and direct printer control remain out of scope; PDF is the printable
artifact.

### Full-score presentation

- [ ] Add `score` and `staff` viewer modes for imported scores.
  - At 120x40, `score` mode renders every mapped tablature, notation, and lyric staff together when they fit.
  - At 80x24, vertical scrolling reaches every staff without dropping content; `staff` mode remains the compact focused view.
  - Keep source staff label/index, bar, cursor, playback position, filename, document mode, and write target visible across mode changes and resize.
  - Cover solo, mixed song, four-part vocal, vocal-only, and duet FT3 files at 80x24 and 120x40.
- [ ] Add system/page navigation suitable for long read-only scores.
  - Support previous/next system and section/page jumps without changing the logical score cursor.
  - Show current section/page and system range in status or `:info` when the FT3 contains that data.

### Format and notation confidence

- [ ] Run a deterministic, stratified remote compatibility audit over at least 1,000 public FT3 files.
  - Record a checked-in manifest of URLs and expected metadata, not downloaded third-party files.
  - Fixed expansions: 200/200 files in the three `corpus/ft3-random-*.json` manifests load without warnings or semantic-audit failures. The later samples add 125 previously unseen composer directories; each selection happened once and is never repeated by tests.
  - Include solo, duet, mixed vocal, vocal-only, polyphonic, multi-section, German, Italian, French, and Spanish/Neapolitan examples.
  - Report format/version and staff-kind counts; require zero crashes and make every warning or unknown record actionable.
  - Manually compare at least 25 stratified files against their published PDF and MIDI, and record evidence in `docs/ft3-parity.md` (19 PDF comparisons recorded; MIDI remains incomplete).
- [ ] Decode and render German and Spanish/Neapolitan FT3 tablature from real fixtures, or reject each unsupported style with a precise visible diagnostic.
- [ ] Close the remaining notation gaps with real-file evidence: polyphonic TabVoice collision precedence, partial beams, tuplets, grace/cue notes, mensural proportions, harmonics, glissandi, ties/slurs across systems, fingerings, ornaments, fermatas, endings, and barline/repeat variants.
  - Each decoded construct needs a typed model field, importer regression, terminal rendering regression, and LilyPond/PDF assertion.
  - Unknown values must remain visible in `:info` and fail the semantic audit rather than being silently discarded.

### Edition and export fidelity

- [ ] Build a representative PDF acceptance matrix for solo, mixed, four-part, duet, and multi-section scores.
  - Verify staff order, lyrics, annotations, repeats/endings, section/page boundaries, system count, and absence of clipping or overlap.
  - Document intentional LilyPond differences from Fronimo instead of claiming pixel-identical output.
- [ ] Make `:pdf` a complete printable workflow: deterministic output path, explicit compiler command, actionable failure diagnostics, overwrite behavior, and success message containing the resulting file.

### Playback and interaction

- [ ] Play all mapped voices/staffs with synchronized cursor movement.
  - Compare MIDI note-on events, voice/channel assignment, repeats/endings, tempo, and start-bar behavior for the representative viewer matrix.
  - Keep pause/stop/restart and missing-synth diagnostics deterministic; never report playback success when no player started.
- [ ] Add the macOS-only terminal acceptance pass.
  - Cover first run, open failure, solo/mixed/polyphonic/duet navigation, score/staff switching, edit/undo, modified quit, first Save As, overwrite refusal, playback failure/success, PDF failure/success, resize, and reopen.
  - Run the real curses cases at 80x24 and 120x40 and retain terminal output on failure.

### Viewer-parity release gate

- [ ] Publish a concise comparison matrix against Fronimo's viewer behavior and test every claimed supported cell.
  - Do not use “Fronimo parity” while any required cell above is missing, partial, or validated only by synthetic fixtures.
  - Label unsupported editor-only behavior explicitly: native FT3 save, page engraving controls, templates, and direct printing.

## Low priority: Release operations

- [ ] Confirm GitHub Actions green on macOS.

## Later: Manual page

- [ ] Ship a real `oud(1)` manual page that works with `man oud`.
  - Maintain `man/oud.1.scd` as the readable source and commit generated `man/oud.1` roff output.
  - Cover synopsis, options and subcommands, files, environment, exit status, examples, diagnostics, and see-also references.
  - Add reproducible build and user-local installation under `~/.local/share/man/man1` without requiring sudo.
  - Validate with `mandoc -T lint man/oud.1` and `man -l man/oud.1` when available.
  - Keep README as the quick-start landing page and the man page as the exhaustive command reference.
