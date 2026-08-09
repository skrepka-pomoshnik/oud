# External score and fixture provenance

Mandatory tests may use only tracked project-authored fixtures or external
fixtures with an explicit source, license, checksum, and redistribution policy.
The loader returning a warning score for a missing file is not evidence that a
fixture-backed test ran.

## Tracked example

`examples/triste.tab` is derived from a MuseScore transcription contributed by
the repository author under GPL-3.0-only. See `examples/README.md` for hashes and
the derivation record.

## Local-only historical scores

The following local files are intentionally ignored, excluded from packages,
and forbidden as mandatory test dependencies:

- `examples/si_par_souffrir.tab`
  - Local SHA-256: `a1745e9a2854abc0a32fae7493d4003d81f1112e4b2d0999aafbe7828c76fe5f`
  - Apparent archive entry: `Berlin_manuscript/si_par_souffrir.tab` in the
    Dartmouth Tab archive.
  - Transcriber and payload license are not established. Do not redistribute.
- `examples/2_intrada_anon.tab`
  - Local SHA-256: `36cb517d09d08987ca75bf1b59244396ba3ae31fe4decf49b1c6a0947ec2b1df`
  - Source, transcriber, and license are not established. Do not redistribute.
- `examples/Sarabande_de_gautier.tab`
  - Local SHA-256: `c451f0870a943eb1ab97e140ac40caa828e1876ea3d1efcddac8697599134cd1`
  - Source, transcriber, and license are not established. Do not redistribute.

These files may be inspected manually on a machine where the user obtained them
lawfully. Automated tests, documentation builds, screenshots, and release gates
must not require them or silently substitute an empty score when they are absent.
