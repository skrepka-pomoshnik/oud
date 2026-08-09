from pathlib import Path


def _package_entities(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.iterdir() if path.name != "__pycache__" and (path.is_dir() or path.suffix == ".py")
    )


def test_editor_packages_have_at_most_seven_direct_entities() -> None:
    root = Path("oud/editor")
    packages = [root, *(path for path in root.rglob("*") if path.is_dir() and path.name != "__pycache__")]

    for package in packages:
        entities = _package_entities(package)
        assert len(entities) <= 7, (package, [path.name for path in entities])


def test_editor_root_exposes_only_domain_packages() -> None:
    root = Path("oud/editor")
    assert {path.name for path in _package_entities(root)} == {
        "__init__.py",
        "commands",
        "core",
        "editing",
        "interaction",
        "navigation",
        "services",
    }
