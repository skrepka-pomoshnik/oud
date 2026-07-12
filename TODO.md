# TODO

## Low priority: Release operations

- [ ] Add a macOS terminal interaction pass covering first run, open failure, edit/undo, modified quit, first Save As, overwrite refusal, read-only navigation, resize, and reopen.
- [ ] Confirm GitHub Actions green on macOS.

## Later: Manual page

- [ ] Ship a real `oud(1)` manual page that works with `man oud`.
  - Maintain `man/oud.1.scd` as the readable source and commit generated `man/oud.1` roff output.
  - Cover synopsis, options and subcommands, files, environment, exit status, examples, diagnostics, and see-also references.
  - Add reproducible build and user-local installation under `~/.local/share/man/man1` without requiring sudo.
  - Validate with `mandoc -T lint man/oud.1` and `man -l man/oud.1` when available.
  - Keep README as the quick-start landing page and the man page as the exhaustive command reference.
