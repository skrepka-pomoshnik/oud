#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, deque
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oud.core.ft3 import load_ft3  # noqa: E402
from oud.core.model import Piece  # noqa: E402
from oud.core.plugin_model import RemoteTab  # noqa: E402
from oud.core.tab_parser import load_tab, load_tab_data  # noqa: E402
from oud.plugins.lutemusic import (  # noqa: E402
    LUTEMUSIC_URLS,
    download_tab,
    fetch_supported_tabs,
)

SUPPORTED_SUFFIXES = (".ft3", ".ft3.gz", ".tab")


@dataclass(frozen=True)
class ScanResult:
    path: str
    bars: int = 0
    warnings: tuple[str, ...] = ()
    warning_classes: tuple[str, ...] = ()
    error: str | None = None


def classify_warning(message: str) -> str:
    text = message.lower()
    rules = (
        (("raw fallback",), "vocal-raw-fallback"),
        (("melody lane is inferred",), "vocal-melody-inferred"),
        (("vocal details",), "vocal-partial"),
        (("editorial text",), "editorial-text"),
        (("bar header markers",), "bar-header-markers"),
        (("unknown staves", "not decoded yet"), "unknown-staves"),
        (("tab appears incomplete",), "tab-incomplete"),
        (("empty piece", "no structured content", "no recoverable bars"), "empty-piece"),
    )
    for needles, warning_class in rules:
        if any(needle in text for needle in needles):
            return warning_class
    return "other"


def _supported(path: Path | str) -> bool:
    text = str(path).lower().split("?", maxsplit=1)[0]
    return text.endswith(SUPPORTED_SUFFIXES)


def discover_files(roots: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and _supported(root):
            found.add(root.resolve())
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and _supported(path):
                found.add(path.resolve())
    return sorted(found)


def _load_piece(path: Path) -> Piece:
    lower = path.name.lower()
    if lower.endswith((".ft3", ".ft3.gz")):
        return load_ft3(str(path))
    parsed = load_tab_data(str(path))
    return parsed.piece if parsed is not None else load_tab(str(path))


def scan_files(paths: Iterable[Path]) -> list[ScanResult]:
    results: list[ScanResult] = []
    for path in paths:
        try:
            piece = _load_piece(path)
        except Exception as exc:
            results.append(
                ScanResult(
                    path=str(path),
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )
            continue
        warnings = list(piece.import_warnings)
        if not piece.bars:
            warnings.append("Importer produced an empty piece with no structured content.")
        results.append(
            ScanResult(
                path=str(path),
                bars=len(piece.bars),
                warnings=tuple(warnings),
                warning_classes=tuple(classify_warning(item) for item in warnings),
            ),
        )
    return results


def _collect_remote_items(url: str, limit: int) -> tuple[list[RemoteTab], list[ScanResult]]:
    pending = deque([url])
    seen: set[str] = set()
    files: list[RemoteTab] = []
    errors: list[ScanResult] = []
    while pending and len(files) < limit:
        current = pending.popleft()
        if current in seen:
            continue
        seen.add(current)
        try:
            items = fetch_supported_tabs(current, limit=2000)
        except Exception as exc:
            errors.append(
                ScanResult(
                    path=current,
                    error=f"listing {type(exc).__name__}: {exc}",
                ),
            )
            continue
        for item in items:
            if item.is_dir:
                pending.append(item.url)
            elif _supported(item.url):
                files.append(item)
                if len(files) >= limit:
                    break
    return files, errors


def download_remote_corpus(
    url: str,
    limit: int,
    destination: Path,
    *,
    jobs: int,
) -> tuple[list[Path], list[ScanResult]]:
    items, errors = _collect_remote_items(url, limit)
    downloaded: list[Path] = []
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = {
            executor.submit(download_tab, item, destination / f"{index:04d}"): item
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                downloaded.append(future.result())
            except Exception as exc:
                errors.append(
                    ScanResult(
                        path=item.url,
                        error=f"download {type(exc).__name__}: {exc}",
                    ),
                )
    return sorted(downloaded), errors


def report_results(
    results: list[ScanResult],
    *,
    json_output: bool,
    verbose: bool,
    fail_on_warning: bool,
) -> int:
    loaded = [result for result in results if result.error is None]
    errors = [result for result in results if result.error is not None]
    warned = [result for result in loaded if result.warnings]
    warning_counts = Counter(
        warning_class
        for result in loaded
        for warning_class in result.warning_classes
    )
    if json_output:
        payload = {
            "attempted": len(results),
            "loaded": len(loaded),
            "errors": len(errors),
            "warned_files": len(warned),
            "warning_classes": dict(sorted(warning_counts.items())),
            "files": [asdict(result) for result in results],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"Scanned {len(results)} file(s): {len(loaded)} loaded, "
            f"{len(errors)} errors, {len(warned)} with warnings.",
        )
        if warning_counts:
            print("Warning classes:")
            for name, count in sorted(warning_counts.items()):
                print(f"  {count:4d}  {name}")
        if errors:
            print("Errors:")
            for result in errors:
                print(f"  {result.path}: {result.error}")
        if verbose:
            for result in loaded:
                status = ", ".join(result.warning_classes) or "ok"
                print(f"  {result.path}: {result.bars} bars [{status}]")
    if not results:
        return 2
    if errors or (fail_on_warning and warned):
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-load FT3/TAB files and classify importer warnings.",
    )
    parser.add_argument(
        "roots",
        nargs="*",
        help="Files or directories to scan (default: lutemusic).",
    )
    parser.add_argument(
        "--fetch-lutemusic",
        type=int,
        metavar="N",
        help="Temporarily download and scan up to N live lutemusic.org files.",
    )
    parser.add_argument(
        "--lutemusic-url",
        default=LUTEMUSIC_URLS["composers"],
        help="Remote listing root used with --fetch-lutemusic.",
    )
    parser.add_argument("--jobs", type=int, default=6, help="Parallel download workers.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="List every loaded file.")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return nonzero for known partial-import warnings too.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    roots = [Path(value) for value in args.roots]
    if not roots and args.fetch_lutemusic is None:
        roots = [Path("lutemusic")]
    results = scan_files(discover_files(roots))
    if args.fetch_lutemusic is not None:
        if args.fetch_lutemusic < 1:
            _parser().error("--fetch-lutemusic must be at least 1")
        with tempfile.TemporaryDirectory(prefix="oud-corpus-") as temp_dir:
            paths, fetch_errors = download_remote_corpus(
                args.lutemusic_url,
                args.fetch_lutemusic,
                Path(temp_dir),
                jobs=args.jobs,
            )
            results.extend(fetch_errors)
            results.extend(scan_files(paths))
    return report_results(
        results,
        json_output=args.json,
        verbose=args.verbose,
        fail_on_warning=args.fail_on_warning,
    )


if __name__ == "__main__":
    raise SystemExit(main())
