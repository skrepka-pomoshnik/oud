from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssignmentPolicy:
    minimum_fret: int = 0
    max_stretch: int | None = None
    restrain_open_strings: bool = False


@dataclass(frozen=True)
class AssignedTabNote:
    pitch: int
    string: int
    fret: int


@dataclass
class AssignmentDiagnostic:
    code: str
    message: str
    item_index: int | None = None


@dataclass
class AssignmentResult:
    notes: list[AssignedTabNote]
    diagnostics: list[AssignmentDiagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def _stretch_ok(assigned: list[AssignedTabNote], max_stretch: int | None) -> bool:
    if max_stretch is None:
        return True
    frets = [n.fret for n in assigned if n.fret > 0]
    if len(frets) <= 1:
        return True
    return (max(frets) - min(frets)) <= max_stretch


def _fretted_stretch(assigned: list[AssignedTabNote]) -> int:
    frets = [n.fret for n in assigned if n.fret > 0]
    if len(frets) <= 1:
        return 0
    return max(frets) - min(frets)


def _penalty_for_candidate(
    fret: int,
    *,
    policy: AssignmentPolicy,
    current: list[AssignedTabNote],
) -> tuple[int, int, int]:
    # Lower tuple is better.
    open_penalty = 1 if (policy.restrain_open_strings and fret == 0) else 0
    future_stretch = 0
    if current:
        frets = [n.fret for n in current if n.fret > 0]
        if fret > 0:
            frets = [*frets, fret]
        if frets:
            future_stretch = max(frets) - min(frets)
    return (open_penalty, future_stretch, fret)


def _candidate_frets_for_pitch(
    pitch: int,
    tuning_pitches: list[int],
    *,
    policy: AssignmentPolicy,
    used_strings: set[int],
    forced_string: int | None,
) -> list[AssignedTabNote]:
    candidates: list[AssignedTabNote] = []
    if forced_string is not None:
        if forced_string < 1 or forced_string > len(tuning_pitches):
            return []
        strings = [forced_string]
    else:
        strings = list(range(1, len(tuning_pitches) + 1))
    for string in strings:
        if string in used_strings:
            continue
        base_pitch = tuning_pitches[string - 1]
        fret = pitch - base_pitch
        if fret < 0:
            continue
        open_string_is_exempt = fret == 0 and not policy.restrain_open_strings
        if not open_string_is_exempt and fret < policy.minimum_fret:
            continue
        candidates.append(AssignedTabNote(pitch=pitch, string=string, fret=fret))
    return candidates


class _AssignmentSearch:
    def __init__(
        self,
        ordered_items: list[tuple[int, int]],
        tuning_pitches: list[int],
        policy: AssignmentPolicy,
        forced_strings: dict[int, int],
    ) -> None:
        self.ordered_items = ordered_items
        self.tuning_pitches = tuning_pitches
        self.policy = policy
        self.forced_strings = forced_strings
        self.best_notes: list[AssignedTabNote] | None = None
        self.best_score: tuple[int, int, int, int] | None = None

    def run(self) -> list[AssignedTabNote] | None:
        self._backtrack(0, [], set())
        return self.best_notes

    def _record_complete_assignment(self, assigned: list[AssignedTabNote]) -> None:
        open_count = sum(1 for note in assigned if note.fret == 0)
        max_fret = max((note.fret for note in assigned), default=0)
        stretch = _fretted_stretch(assigned)
        penalized_open_count = open_count if self.policy.restrain_open_strings else 0
        total_fret = sum(note.fret for note in assigned)
        score = (penalized_open_count, stretch, total_fret, max_fret)
        if self.best_score is None or score < self.best_score:
            self.best_score = score
            self.best_notes = list(assigned)

    def _backtrack(
        self,
        position: int,
        assigned: list[AssignedTabNote],
        used_strings: set[int],
    ) -> None:
        if position >= len(self.ordered_items):
            self._record_complete_assignment(assigned)
            return

        item_index, pitch = self.ordered_items[position]
        candidates = _candidate_frets_for_pitch(
            pitch,
            self.tuning_pitches,
            policy=self.policy,
            used_strings=used_strings,
            forced_string=self.forced_strings.get(item_index),
        )
        if not candidates:
            return
        candidates.sort(
            key=lambda candidate: _penalty_for_candidate(
                candidate.fret,
                policy=self.policy,
                current=assigned,
            ),
        )
        for candidate in candidates:
            assigned.append(candidate)
            if not _stretch_ok(assigned, self.policy.max_stretch):
                assigned.pop()
                continue
            used_strings.add(candidate.string)
            self._backtrack(position + 1, assigned, used_strings)
            used_strings.remove(candidate.string)
            assigned.pop()


def _ordered_assignment_items(pitches: list[int], forced_strings: dict[int, int]) -> list[tuple[int, int]]:
    ordered_items = list(enumerate(pitches))
    ordered_items.sort(
        key=lambda item: (
            0 if item[0] in forced_strings else 1,
            -item[1],
        ),
    )
    return ordered_items


def _assignment_failure_diagnostics(
    ordered_items: list[tuple[int, int]],
    tuning_pitches: list[int],
    policy: AssignmentPolicy,
    forced_strings: dict[int, int],
) -> list[AssignmentDiagnostic]:
    diagnostics: list[AssignmentDiagnostic] = []
    used_dummy: set[int] = set()
    for item_index, pitch in ordered_items:
        forced = forced_strings.get(item_index)
        if forced is not None and (forced < 1 or forced > len(tuning_pitches)):
            diagnostics.append(
                AssignmentDiagnostic(
                    "forced_string_out_of_range",
                    f"Forced string {forced} is outside available strings.",
                    item_index=item_index,
                ),
            )
            continue
        candidates = _candidate_frets_for_pitch(
            pitch,
            tuning_pitches,
            policy=policy,
            used_strings=used_dummy,
            forced_string=forced,
        )
        if not candidates:
            code = "forced_string_impossible" if forced is not None else "no_candidate"
            diagnostics.append(
                AssignmentDiagnostic(
                    code,
                    "No valid string/fret assignment under current constraints.",
                    item_index=item_index,
                ),
            )
            continue
        if policy.max_stretch is not None:
            diagnostics.append(
                AssignmentDiagnostic(
                    "max_stretch_exceeded",
                    "Candidates exist but no chord assignment satisfies max_stretch.",
                    item_index=item_index,
                ),
            )
            break
        diagnostics.append(
            AssignmentDiagnostic(
                "assignment_failed",
                "No valid chord assignment found.",
                item_index=item_index,
            ),
        )
        break
    return diagnostics or [AssignmentDiagnostic("assignment_failed", "No valid chord assignment found.")]


def _restore_assignment_order(
    pitches: list[int],
    best_notes: list[AssignedTabNote],
) -> list[AssignedTabNote]:
    by_pitch_occurrence: dict[tuple[int, int], AssignedTabNote] = {}
    counts: dict[int, int] = {}
    for note in best_notes:
        occurrence = counts.get(note.pitch, 0)
        by_pitch_occurrence[(note.pitch, occurrence)] = note
        counts[note.pitch] = occurrence + 1
    out: list[AssignedTabNote] = []
    seen: dict[int, int] = {}
    for pitch in pitches:
        occurrence = seen.get(pitch, 0)
        out.append(by_pitch_occurrence[(pitch, occurrence)])
        seen[pitch] = occurrence + 1
    return out


def assign_chord_pitches(
    pitches: list[int],
    tuning_pitches: list[int],
    *,
    policy: AssignmentPolicy | None = None,
    forced_strings: dict[int, int] | None = None,
) -> AssignmentResult:
    policy = policy or AssignmentPolicy()
    forced_strings = forced_strings or {}
    if not pitches:
        return AssignmentResult(notes=[])
    if not tuning_pitches:
        return AssignmentResult(
            notes=[],
            diagnostics=[AssignmentDiagnostic("no_tuning", "No tuning pitches provided.")],
        )

    ordered_items = _ordered_assignment_items(pitches, forced_strings)
    best_notes = _AssignmentSearch(
        ordered_items,
        tuning_pitches,
        policy,
        forced_strings,
    ).run()
    if best_notes is None:
        return AssignmentResult(
            notes=[],
            diagnostics=_assignment_failure_diagnostics(
                ordered_items,
                tuning_pitches,
                policy,
                forced_strings,
            ),
        )

    return AssignmentResult(notes=_restore_assignment_order(pitches, best_notes), diagnostics=[])
