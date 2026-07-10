# Releasing oud

Run the release checks from the repository root:

```
uv sync --locked
uv run ruff check .
uv run pytest tests -q
uv run python scripts/corpus_smoke.py lutemusic
uv build
```

For a wider importer pass, use a temporary live sample. Downloaded files are
removed when the command exits:

```
uv run python scripts/corpus_smoke.py --fetch-lutemusic 250 \
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

The GitHub Actions matrix must be green on macOS before tagging. It runs
Python 3.11 and 3.13, ruff, pytest, and the bundled-corpus smoke pass.

## Publication decisions

- The canonical repository, homepage, and issue tracker are
  `https://github.com/skrepka-pomoshnik/oud`.
- `uv.lock`, `.github/workflows/ci.yml`, and `lutemusic/README.md` are tracked
  and present on `origin/main` from commit `390ebe8`.
