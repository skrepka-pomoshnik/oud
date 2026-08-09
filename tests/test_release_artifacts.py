from scripts.checks.release_artifacts import invalid_artifact_names


def test_wheel_content_policy_rejects_development_and_external_payloads() -> None:
    names = {
        "oud/presentation/app.py",
        "petrucci/py.typed",
        "oud-1.0.dist-info/METADATA",
        "tests/test_app.py",
        "tests/fixtures/ft3/manifests/manifest.json",
        "oud/private.ft3",
    }

    assert invalid_artifact_names(names, wheel=True) == {
        "tests/fixtures/ft3/manifests/manifest.json",
        "oud/private.ft3",
        "tests/test_app.py",
    }


def test_sdist_content_policy_allows_build_sources_but_rejects_planning_records() -> None:
    names = {
        "LICENSE",
        "MANIFEST.in",
        "README.md",
        "oud/presentation/app.py",
        "petrucci/core/score.py",
        "pyproject.toml",
        "TODO.md",
        "examples/score.mid",
    }

    assert invalid_artifact_names(names, wheel=False) == {"TODO.md", "examples/score.mid"}
