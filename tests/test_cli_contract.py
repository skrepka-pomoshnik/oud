from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from oud import cli_convert
from oud.cli_convert import CommandStreams, ConvertOptions, convert_command

TAB_TEXT = "% test\n-C\n{Pipeline score}\nb\n0a-----\n\ne\n"


def _write_tab(path: Path) -> None:
    path.write_text(TAB_TEXT, encoding="utf-8")


def test_convert_streams_tab_stdin_to_musicxml_stdout() -> None:
    stdout = StringIO()
    stderr = StringIO()

    status = convert_command(
        "-",
        "-",
        "missing-config.toml",
        options=ConvertOptions(input_format="tab", output_format="musicxml"),
        streams=CommandStreams(stdin=StringIO(TAB_TEXT), stdout=stdout, stderr=stderr),
    )

    assert status == 0
    assert stdout.getvalue().startswith('<?xml version="1.0"')
    assert "<work-title>Pipeline score</work-title>" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_stdout_requires_explicit_streamable_format() -> None:
    for options, message in (
        (ConvertOptions(input_format="tab"), "stdout output requires --format"),
        (ConvertOptions(input_format="tab", output_format="midi"), "cannot be streamed"),
    ):
        stdout = StringIO()
        stderr = StringIO()
        status = convert_command(
            "-",
            "-",
            "config.toml",
            options=options,
            streams=CommandStreams(stdin=StringIO(TAB_TEXT), stdout=stdout, stderr=stderr),
        )
        assert status == cli_convert.EXIT_USAGE
        assert stdout.getvalue() == ""
        assert message in stderr.getvalue()


def test_missing_and_broken_inputs_have_stable_input_status(tmp_path: Path) -> None:
    output = tmp_path / "out.tab"
    missing_error = StringIO()
    broken_error = StringIO()
    broken = tmp_path / "broken.ft3"
    broken.write_bytes(b"not an FT3 score")

    missing_status = convert_command(
        str(tmp_path / "missing.ft3"),
        str(output),
        "config.toml",
        streams=CommandStreams(stderr=missing_error),
    )
    broken_status = convert_command(
        str(broken),
        str(output),
        "config.toml",
        streams=CommandStreams(stderr=broken_error),
    )

    assert (missing_status, broken_status) == (cli_convert.EXIT_INPUT, cli_convert.EXIT_INPUT)
    assert "Missing file" in missing_error.getvalue()
    assert "CPiece" in broken_error.getvalue()
    assert not output.exists()


def test_convert_refuses_overwrite_until_force_is_explicit(tmp_path: Path) -> None:
    source = tmp_path / "source.tab"
    target = tmp_path / "target.ly"
    _write_tab(source)
    target.write_text("original", encoding="utf-8")
    refused_error = StringIO()

    refused = convert_command(
        str(source),
        str(target),
        "config.toml",
        streams=CommandStreams(stderr=refused_error),
    )
    replaced = convert_command(
        str(source),
        str(target),
        "config.toml",
        options=ConvertOptions(overwrite=True),
        streams=CommandStreams(stdout=StringIO(), stderr=StringIO()),
    )

    assert refused == cli_convert.EXIT_OUTPUT
    assert "refusing to overwrite" in refused_error.getvalue()
    assert replaced == 0
    assert target.read_text(encoding="utf-8").startswith('\\version "2.24.0"')


def test_convert_does_not_create_unselected_output_directories(tmp_path: Path) -> None:
    source = tmp_path / "source.tab"
    missing_directory = tmp_path / "missing" / "out.tab"
    stderr = StringIO()
    _write_tab(source)

    status = convert_command(
        str(source),
        str(missing_directory),
        "config.toml",
        streams=CommandStreams(stderr=stderr),
    )

    assert status == cli_convert.EXIT_OUTPUT
    assert "output directory does not exist" in stderr.getvalue()
    assert not missing_directory.parent.exists()


def test_pdf_success_publishes_pdf_and_lilypond_source_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.tab"
    target = tmp_path / "score.pdf"
    _write_tab(source)

    def compile_pdf(_ly_path: str, output_base: str) -> str:
        generated = Path(output_base).with_suffix(".pdf")
        generated.write_bytes(b"%PDF-test")
        return f"Printed {generated}"

    monkeypatch.setattr(cli_convert, "print_lilypond_pdf", compile_pdf)
    stdout = StringIO()
    status = convert_command(
        str(source),
        str(target),
        "config.toml",
        streams=CommandStreams(stdout=stdout, stderr=StringIO()),
    )

    assert status == 0
    assert target.read_bytes() == b"%PDF-test"
    assert target.with_suffix(".ly").read_text(encoding="utf-8").startswith('\\version "2.24.0"')
    assert stdout.getvalue() == f"Wrote {target}\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["score.ly", "score.pdf", "source.tab"]


def test_broken_pipe_is_quiet_success_for_unix_pipeline() -> None:
    class BrokenStream(StringIO):
        def write(self, _value: str) -> int:
            raise BrokenPipeError

    stderr = StringIO()
    status = convert_command(
        "-",
        "-",
        "config.toml",
        options=ConvertOptions(input_format="tab", output_format="tab"),
        streams=CommandStreams(stdin=StringIO(TAB_TEXT), stdout=BrokenStream(), stderr=stderr),
    )

    assert status == 0
    assert stderr.getvalue() == ""
