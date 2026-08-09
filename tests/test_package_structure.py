import ast
from pathlib import Path

_PACKAGE_ROOTS = (Path("oud"), Path("petrucci"))


def _package_entities(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.name != "__pycache__" and (path.suffix == ".py" or (path.is_dir() and (path / "__init__.py").is_file()))
    )


def _packages(root: Path) -> list[Path]:
    return [root, *(path for path in root.rglob("*") if path.is_dir() and (path / "__init__.py").is_file())]


def test_project_packages_have_at_most_seven_direct_entities() -> None:
    for root in _PACKAGE_ROOTS:
        for package in _packages(root):
            entities = _package_entities(package)
            assert len(entities) <= 7, (package, [path.name for path in entities])


def test_oud_root_exposes_only_domain_packages_and_settings() -> None:
    assert {path.name for path in _package_entities(Path("oud"))} == {
        "__init__.py",
        "editor",
        "exports",
        "importers",
        "presentation",
        "services",
        "settings.py",
    }


def test_petrucci_root_exposes_only_domain_packages() -> None:
    assert {path.name for path in _package_entities(Path("petrucci"))} == {
        "__init__.py",
        "adapters",
        "core",
        "engraving",
        "input",
        "rendering",
        "terminal",
    }


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_lilypond_export_and_import_layers_are_independent() -> None:
    importer_modules = {module for path in Path("oud/importers").rglob("*.py") for module in _imported_modules(path)}
    exporter_modules = {
        module for path in Path("oud/exports/lilypond").rglob("*.py") for module in _imported_modules(path)
    }
    assert not any(module.startswith("oud.exports") for module in importer_modules)
    assert not any(module.startswith("oud.importers") for module in exporter_modules)
