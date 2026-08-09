# Local tablature corpus

This directory is a local cache for integration testing. Gerbode `.ft3`
payloads and decoded dumps are ignored by Git and must never be committed.
Only this attribution file and derived, non-musical manifests belong in the
repository.

The local `.ft3` files are typesettings by Sarge Gerbode, downloaded from
[lutemusic.org](https://www.lutemusic.org). They are used for importer and
viewer integration tests.

Fetch the fixed corpora from a checkout with:

```bash
uv run python scripts/fetch_ft3_corpus.py \
  corpus/ft3-regression.json corpus/ft3-random-75.json
```

This verifies every payload against its checked-in SHA-256. Selection is not
repeated during fetch or testing.

The underlying Renaissance music is in the public domain; the typesettings are
licensed under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
License](https://creativecommons.org/licenses/by-nc-sa/4.0/) (CC BY-NC-SA 4.0).
Performance for hire is permitted per the site.

These files are **not** covered by the project's GPL-3.0 license. Do not add
them to a commit. If you redistribute them separately, keep this attribution
and comply with the source license.
