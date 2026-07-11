# AGENTS.md

<!-- BEGIN COMMON ENGINEERING CONTRACT -->

This common engineering contract is mandatory for agents and contributors.
Project-specific rules may refine runtime versions, tool targets, architecture, protocols, and domain invariants, but may not weaken this contract silently.

## Common mission

Build small, deterministic Python software with explicit boundaries, stable behavior, and no hidden mechanisms.
Keep documentation aligned with actual behavior.

## Common principles

1. Prefer simple, direct implementations over frameworks and speculative abstractions.
2. Build strong domain modules instead of helper sprawl or convenience-wrapper layers.
3. Keep dependencies directional and domain logic independent of presentation, transport, storage, and external services.
4. Prefer composition, explicit data flow, explicit return types, and explicit errors.
5. Keep behavior and output deterministic. Do not add hidden network calls, silent fallbacks, or fake support claims.
6. Use one canonical path for each operation; different interfaces must reuse it.
7. Prefer deleting obsolete paths over adding compatibility shims.
8. Add a dependency only when it removes real complexity.
9. Keep changes minimal, focused, reviewable, and reversible.
10. Preserve user data and backward compatibility unless an intentional breaking change is documented.

## Common architecture rules

1. Each module owns one responsibility and one reason to change.
2. Public APIs are small, stable, typed, and documented where behavior is not obvious.
3. Avoid global mutable state, utility dumping grounds, import-time side effects, and cross-layer shortcuts.
4. Split modules when responsibilities diverge, not merely to satisfy a size metric.
5. Add an abstraction only after real uses establish a shared contract.
6. Keep project-specific boundaries and invariants in the project contract below.

## Common Unix-style rules

1. Prefer plain files and stable, inspectable formats.
2. Send primary command output to stdout and diagnostics to stderr.
3. Make tools scriptable and non-interactive by default.
4. Do not overwrite user data without explicit authorization.
5. Do not write outside an explicitly selected output or state directory.
6. Make partial failure visible; never silently discard or invent data.

## Common Python rules

1. Default to Python 3.11 or newer. An explicit project contract may retain an older supported runtime.
2. Type public functions and data contracts, plus internal boundaries where inference is not obvious.
3. Prefer dataclasses or small typed records for data and explicit exceptions for failures.
4. Keep control flow readable and functions focused.
5. Use boring Python; avoid clever metaprogramming.
6. Use pathlib for paths and context managers for owned resources.

## Common security and data rules

1. Never commit credentials, tokens, private data, proprietary fixtures, or machine-specific paths.
2. Read secrets from environment or settings, never source code.
3. Validate external input at boundaries.
4. Tests must not require private infrastructure or network access unless explicitly marked as integration tests.

## Common quality gate

Use uv as the environment, dependency, and command runner.
A project contract may narrow the Ty target or add stricter checks, but may not omit these checks.

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

Ruff must enable at least E, F, I, UP, B, SIM, C90, PLR, and RUF.
The shared line length is 120 and the shared complexity ceiling is 7.
Existing project-specific rules may be stricter.
Every exception must be narrow, documented beside its configuration, and removed when the debt is fixed.

## Common testing rules

1. Test public behavior and contracts rather than implementation trivia.
2. Add a regression test for each bug fix when practical.
3. Keep fixtures small, deterministic, and legal to redistribute.
4. Mark slow, network, hardware, benchmark, and integration tests.
5. Do not weaken assertions merely to make tests pass.

## Common documentation rules

1. Document supported behavior, limitations, inputs, outputs, and failure modes plainly.
2. Keep examples copy-pasteable and free of real secrets and private hosts.
3. Update architecture documentation when a boundary or public contract changes.
4. Distinguish supported, partial, experimental, and unsupported behavior.

## Common work-tracking rules

1. Keep the active backlog in root `TODO.md` and completed work in root `DONE.md`.
2. `TODO.md` contains unfinished, concrete, and verifiable work; move meaningful completions to `DONE.md`.
3. `DONE.md` records outcomes and validation evidence, newest first.
4. A project contract may declare an operational path exception when tooling depends on it. `regression_vibe` retains `WIP/TODO.md` and `WIP/done.md` as that explicit exception.## Common definition of done

A change is done when behavior is implemented, relevant tests and documentation are updated, mandatory quality checks pass, and no known contract mismatch is hidden.

<!-- END COMMON ENGINEERING CONTRACT -->

## Project contract

The rules below are specific to this repository. Where they specify tool targets or runtime support, they refine the common contract.

Keep it unix-way, layered and suckless.
You can always use python from environment in .venv.
