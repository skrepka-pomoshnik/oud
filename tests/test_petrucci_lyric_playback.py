from petrucci.terminal.text.lyrics import lyric_display


def test_lyric_display_current_prefers_active_playback_verse() -> None:
    display = lyric_display(
        {"showlyrics": "on", "lyricmode": "current", "lyricverse": "1"},
        active_verse_index=2,
    )

    assert display.verse_index == 2
