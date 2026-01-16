def test_import_app_module() -> None:
    __import__("app")


def test_import_render_module() -> None:
    __import__("render")


def test_import_export_tab_module() -> None:
    __import__("export_tab")


def test_import_lilypond_module() -> None:
    __import__("lilypond")


def test_import_midi_module() -> None:
    __import__("midi")


def test_compile_all() -> None:
    import compileall
    assert compileall.compile_dir(".", quiet=1)
