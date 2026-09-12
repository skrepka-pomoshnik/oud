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

This project intentionally does not use GitHub Actions CI. Run the local quality
and release checks above before tagging. Platform-specific curses behavior is
covered by the macOS-marked tests when they are run on a macOS host.

## Publication decisions

- The canonical repository, homepage, and issue tracker are
  `https://github.com/skrepka-pomoshnik/oud`.
- `uv.lock` and `tests/fixtures/ft3/README.md` are tracked; proprietary FT3
  files remain local fixtures and are not redistributed.
