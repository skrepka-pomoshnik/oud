# TODO

## P0: Petrucci proper score renderer

Target: Petrucci remains Oud's library and gains a proper standard-notation
typesetter for Oud's imported note/vocal staffs. Its public contracts must also
support a second application such as Voce without Oud editor, FT3, tablature, or
curses dependencies. Detailed boundaries and sequencing are in
`docs/petrucci-score-plan.md`.

The canonical model, measured layout, semantic terminal frame, overlays, public
API, Oud adapter, and neutral-consumer wheel smoke are implemented. The work
below is the remaining release gate, not a restatement of completed foundation.

### Engraving correctness

- [ ] Resolve independent-voice and dense-chord collisions without moving the
  shared musical onset. Cover seconds/unisons, opposing stems, overlapping
  accidentals, rests, dots, beams, and lyrics with deterministic precedence.
- [ ] Carry real imported tuplets, ties/slurs, mid-score clef/key changes, and
  remaining ornament forms through the Oud adapter. Each construct needs
  canonical, layout, semantic-frame, and text-snapshot evidence.
- [ ] Extend the reserved-lane collision policy to multiple lyric verses,
  simultaneous dynamics, nested spans, and tuplets; add overlap and bounds
  invariants over every positioned semantic element.
- [ ] Reject or visibly clip every unsupported pitch, duration, and viewport
  case. A clipped viewport must preserve canonical event identity and emit an
  explicit clipping marker rather than silently lose source semantics.

### Oud migration and second-consumer proof

- [ ] Close the remaining representative FT3 adapter failures without guessing:
  seven strict lyric-onset mismatches and five note-only timing/capacity errors
  in the fixed corpus's 15-file notation subset. False ASCII pitches and
  flagged meter records are closed. Preserve `include_lyrics=False` as an
  explicit note-only migration mode; never truncate or spread source lyrics to
  force a match.
- [ ] Migrate vocal-only, then mixed/polyphonic/duet imported staffs to the new
  score path without changing solo tablature output; remove each legacy vocal
  fallback only after canonical adapter coverage exists.
- [ ] Add structural and text snapshots at 60, 80, and 120 columns for dense and
  sparse measures, repeated pitches, rests, accidentals, ledger lines, ties,
  lyrics, safe glyphs, clipping, forced breaks, and resize preserving active ID.
- [ ] Add one real score-following acceptance fixture across multiple playback
  positions. Validate the actual Voce adapter with explicit renderer ownership,
  repeated-note feedback by event ID, and Petrucci public imports only. The
  consumer must select `system_offset` for the active event across playback and
  resize, and map Petrucci's semantic roles to its own color policy without
  moving playback clocks or global renderer state into Petrucci.
- [ ] Move internal callers off underscore helpers exported by
  `view_model.__all__`, then shrink that legacy surface without changing
  `typeset_piece()` output.
- [ ] Keep Petrucci in Oud until the canonical API and snapshots pass in both Oud
  and Voce; a separate distribution remains out of scope for this milestone.

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
  - Fixed expansions: 150/150 files in the two `corpus/ft3-random-75*.json` manifests load without warnings or semantic-audit failures. The second sample adds 75 previously unseen composer directories; selection happened once and is never repeated by tests.
  - Include solo, duet, mixed vocal, vocal-only, polyphonic, multi-section, German, Italian, French, and Spanish/Neapolitan examples.
  - Report format/version and staff-kind counts; require zero crashes and make every warning or unknown record actionable.
  - Manually compare at least 25 stratified files against their published PDF and MIDI, and record evidence in `docs/ft3-parity.md` (17 PDF comparisons recorded; MIDI remains incomplete).
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
