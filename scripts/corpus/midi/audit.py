from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from fractions import Fraction
from pathlib import Path

from oud.exports.midi import export_midi
from oud.importers.ft3 import build_durations, load_ft3
from scripts.corpus.fetch import load_manifest, manifest_paths
from scripts.corpus.midi.format import MidiNotes, read_midi_notes
from scripts.corpus.midi.references import ReferenceFetch, fetch_reference, generated_cache_path


@dataclass(frozen=True, slots=True)
class MidiComparison:
    reference_notes: int
    generated_notes: int
    reference_onsets: int
    generated_onsets: int
    exact: bool
    best_transposition: int
    onset_similarity: float
    pitch_overlap: float


@dataclass(frozen=True, slots=True)
class AuditRecord:
    source_url: str
    local_ft3: str
    reference_url: str
    reference_midi: str
    generated_midi: str | None
    status: str
    detail: str | None = None
    comparison: MidiComparison | None = None


def _onset_chords(notes: MidiNotes, shift: int = 0) -> tuple[tuple[int, ...], ...]:
    grouped: dict[Fraction, list[int]] = defaultdict(list)
    for note in notes.notes:
        grouped[note.onset].append(note.pitch + shift)
    return tuple(tuple(sorted(grouped[onset])) for onset in sorted(grouped))


def compare_notes(reference: MidiNotes, generated: MidiNotes) -> MidiComparison:
    reference_chords = _onset_chords(reference)
    candidates: list[tuple[float, int, tuple[tuple[int, ...], ...]]] = []
    for shift in range(-12, 13):
        shifted = _onset_chords(generated, shift)
        ratio = SequenceMatcher(None, reference_chords, shifted, autojunk=False).ratio()
        candidates.append((ratio, shift, shifted))
    similarity, shift, shifted_chords = max(candidates, key=lambda item: (item[0], -abs(item[1]), item[1] == 0))
    reference_pitches = Counter(note.pitch for note in reference.notes)
    generated_pitches = Counter(note.pitch + shift for note in generated.notes)
    overlap = sum((reference_pitches & generated_pitches).values())
    denominator = max(len(reference.notes), len(generated.notes), 1)
    return MidiComparison(
        reference_notes=len(reference.notes),
        generated_notes=len(generated.notes),
        reference_onsets=len(reference_chords),
        generated_onsets=len(shifted_chords),
        exact=reference_chords == shifted_chords and shift == 0,
        best_transposition=shift,
        onset_similarity=round(similarity, 6),
        pitch_overlap=round(overlap / denominator, 6),
    )


def load_corpus(manifests: list[Path], repo_root: Path) -> list[tuple[str, Path]]:
    items: dict[str, Path] = {}
    for manifest_path in manifests:
        manifest = load_manifest(manifest_path)
        for entry, local_path in zip(manifest.files, manifest_paths(manifest, repo_root), strict=True):
            items.setdefault(entry.url, local_path)
    return sorted(items.items())


def audit_corpus(
    items: list[tuple[str, Path]],
    cache_root: Path,
    *,
    jobs: int = 8,
    refresh: bool = False,
) -> list[AuditRecord]:
    reference_root = cache_root / "reference"
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        fetched = executor.map(lambda item: fetch_reference(item[0], reference_root, refresh=refresh), items)
        references = dict(zip((url for url, _path in items), fetched, strict=True))
    records: list[AuditRecord] = []
    for source_url, ft3_path in items:
        reference = references[source_url]
        generated_path = generated_cache_path(cache_root / "generated", source_url)
        records.append(_audit_one(source_url, ft3_path, reference, generated_path))
    return records


def _audit_one(source_url: str, ft3_path: Path, reference: ReferenceFetch, generated_path: Path) -> AuditRecord:
    def record(
        status: str,
        *,
        generated_midi: str | None = None,
        detail: str | None = None,
        comparison: MidiComparison | None = None,
    ) -> AuditRecord:
        return AuditRecord(
            source_url=source_url,
            local_ft3=str(ft3_path),
            reference_url=reference.url,
            reference_midi=str(reference.path),
            generated_midi=generated_midi,
            status=status,
            detail=detail,
            comparison=comparison,
        )

    if reference.status in {"missing", "error"}:
        return record(f"reference_{reference.status}", detail=reference.detail)
    if not ft3_path.exists():
        return record("ft3_missing", detail="local corpus file is absent")
    try:
        reference_notes = read_midi_notes(reference.path)
        if not reference_notes.notes:
            return record("reference_empty")
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        piece = load_ft3(str(ft3_path))
        export_midi(str(generated_path), piece, {}, build_durations(piece), 32)
        comparison = compare_notes(reference_notes, read_midi_notes(generated_path))
    except (OSError, ValueError, IndexError) as exc:
        return record("comparison_error", generated_midi=str(generated_path), detail=str(exc))
    return record("compared", generated_midi=str(generated_path), comparison=comparison)
