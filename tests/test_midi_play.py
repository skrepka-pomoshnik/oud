
import sys

import pytest

from oud.exports.midi import _midi_command


@pytest.mark.skipif(sys.platform != "darwin", reason="uses a macOS user SoundFont path")
def test_midi_command_fluidsynth_with_soundfont_darwin() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont="/Users/s/Library/Audio/Sounds/Banks/SC-55 SoundFont v1.2b.sf2",
        platform="darwin",
        fluidsynth="/usr/local/bin/fluidsynth",
        timidity="/usr/bin/timidity",
        opener="/usr/bin/open",
    )
    assert cmd == [
        "/usr/local/bin/fluidsynth",
        "-q",
        "-a",
        "coreaudio",
        "-ni",
        "/Users/s/Library/Audio/Sounds/Banks/SC-55 SoundFont v1.2b.sf2",
        "out.mid",
    ]


def test_midi_command_prefers_timidity_without_soundfont_on_darwin() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="darwin",
        fluidsynth="/opt/homebrew/bin/fluidsynth",
        timidity="/opt/homebrew/bin/timidity",
        opener="/usr/bin/open",
    )
    assert cmd == ["/opt/homebrew/bin/timidity", "out.mid"]


def test_midi_command_prefers_fluidsynth_with_soundfont(tmp_path) -> None:
    soundfont = tmp_path / "lute.sf2"
    soundfont.write_bytes(b"sf2")
    cmd = _midi_command(
        path="out.mid",
        soundfont=str(soundfont),
        platform="linux",
        fluidsynth="/usr/bin/fluidsynth",
        timidity="/usr/bin/timidity",
        opener=None,
    )
    assert cmd == [
        "/usr/bin/fluidsynth",
        "-q",
        "-ni",
        str(soundfont),
        "out.mid",
    ]


def test_midi_command_missing_soundfont_falls_back_to_timidity() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont="~/sf2/missing.sf2",
        platform="darwin",
        fluidsynth="/opt/homebrew/bin/fluidsynth",
        timidity="/opt/homebrew/bin/timidity",
        opener="/usr/bin/open",
    )
    assert cmd == ["/opt/homebrew/bin/timidity", "out.mid"]


def test_midi_command_fluidsynth_when_only_player() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="linux",
        fluidsynth="/usr/bin/fluidsynth",
        timidity=None,
        opener=None,
    )
    assert cmd == ["/usr/bin/fluidsynth", "-q", "out.mid"]


def test_midi_command_timidity_fallback() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="linux",
        fluidsynth=None,
        timidity="/usr/bin/timidity",
        opener=None,
    )
    assert cmd == ["/usr/bin/timidity", "out.mid"]


def test_midi_command_darwin_open() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="darwin",
        fluidsynth=None,
        timidity=None,
        opener="/usr/bin/open",
    )
    assert cmd == ["/usr/bin/open", "out.mid"]


def test_midi_command_none_without_player() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="linux",
        fluidsynth=None,
        timidity=None,
        opener=None,
    )
    assert cmd is None
