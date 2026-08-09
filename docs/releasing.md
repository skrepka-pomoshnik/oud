# Releasing oud

Run the release checks from the repository root:

```
uv sync --locked
./scripts/quality.sh
uv run python scripts/checks/release_artifacts.py
uv build
```

For a wider importer pass, use a temporary live sample. Downloaded files are
removed when the command exits:

```
uv run python scripts/corpus/smoke.py --fetch-lutemusic 250 \
  --lutemusic-url https://browse.lutemusic.org/tabs/composers/
```

The 2026-07-10 release pass loaded 250/250 live files from that composer index
with zero importer errors and zero warnings. The bundled corpus loaded 36/36
with zero errors and zero warnings.

Before uploading, recheck the package name. The PyPI JSON endpoint for `oud`
returned HTTP 404 on 2026-07-10, so the name was unregistered at that point;
availability is not reserved until the first upload.

```
curl -sS -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/oud/json
```

The Ubuntu Python 3.11 quality job must be green before tagging. Run the focused
`macos-curses` workflow manually when terminal input, resize handling, or curses
presentation changes; it does not spend macOS runner minutes on unrelated
commits.

## Publication decisions

- The canonical repository, homepage, and issue tracker are
  `https://github.com/skrepka-pomoshnik/oud`.
- `uv.lock`, `.github/workflows/ci.yml`, and `tests/fixtures/ft3/README.md` are tracked
  and present on `origin/main` from commit `390ebe8`.
