import compileall


def test_import_app_module() -> None:
    __import__("app")


def test_import_render_module() -> None:
    __import__("ui.render")


def test_import_export_tab_module() -> None:
    __import__("exports.export_tab")


def test_import_lilypond_module() -> None:
    __import__("exports.lilypond")


def test_import_midi_module() -> None:
    __import__("exports.midi")


def test_compile_all() -> None:
    assert compileall.compile_dir(".", quiet=1)
