from pathlib import Path

from exports.midi import _midi_command


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


def test_midi_command_prefers_fluidsynth_darwin() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont=None,
        platform="darwin",
        fluidsynth="/opt/homebrew/bin/fluidsynth",
        timidity="/opt/homebrew/bin/timidity",
        opener="/usr/bin/open",
    )
    assert cmd == [
        "/opt/homebrew/bin/fluidsynth",
        "-q",
        "-a",
        "coreaudio",
        "out.mid",
    ]


def test_midi_command_prefers_fluidsynth_with_soundfont() -> None:
    cmd = _midi_command(
        path="out.mid",
        soundfont="~/sf2/lute.sf2",
        platform="linux",
        fluidsynth="/usr/bin/fluidsynth",
        timidity="/usr/bin/timidity",
        opener=None,
    )
    assert cmd == [
        "/usr/bin/fluidsynth",
        "-q",
        "-ni",
        str(Path("~/sf2/lute.sf2").expanduser()),
        "out.mid",
    ]


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
