# TODO

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
  - Initial fixed expansion: 75/75 files in `corpus/ft3-random-75.json` load without crashing; selection happened once and is never repeated by tests.
  - Include solo, duet, mixed vocal, vocal-only, polyphonic, multi-section, German, Italian, French, and Spanish/Neapolitan examples.
  - Report format/version and staff-kind counts; require zero crashes and make every warning or unknown record actionable.
  - Manually compare at least 25 stratified files against their published PDF and MIDI, and record evidence in `docs/ft3-parity.md`.
- [ ] Decode and render German and Spanish/Neapolitan FT3 tablature from real fixtures, or reject each unsupported style with a precise visible diagnostic.
- [ ] Close the remaining notation gaps with real-file evidence: polyphonic TabVoice collision precedence, partial beams, tuplets, harmonics, glissandi, ties/slurs across systems, fingerings, ornaments, fermatas, endings, and barline/repeat variants.
  - Each decoded construct needs a typed model field, importer regression, terminal rendering regression, and LilyPond/PDF assertion.
  - Unknown values must remain visible in `:info` and fail the semantic audit rather than being silently discarded.

### Edition and export fidelity

- [ ] Build a representative PDF acceptance matrix for solo, mixed, four-part, duet, and multi-section scores.
  - Verify staff order, lyrics, annotations, repeats/endings, section/page boundaries, system count, and absence of clipping or overlap.
  - Document intentional LilyPond differences from Fronimo instead of claiming pixel-identical output.
- [ ] Make every imported title, subtitle, staff name, footnote, editorial comment, section annotation, and source page discoverable in `:info`/`:notes` and preserved in LilyPond output.
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
