"""Help text: key sections are generated from the key table for the active profile."""

from __future__ import annotations

from oud.editor.core.input.keymap import ActionGroup, HelpRow, help_rows, key_profile
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState

_KEY_COLUMN = 18

_FIRST_SCORE = (
    "FIRST SCORE",
    "Open/create  oud [FILE] / oud       Open here  :e FILE",
    "Enter note   i, type fret a-t or 0-9, then Esc",
    "Undo         u                       Save       :w [FILE.tab]",
    "Quit         :q                      Discard    :q!",
)

_INSERT_CONTENT = (
    "  French frets    a-t (no j); q and r are frets 15 and 16",
    "  Italian frets   0-9 and x; ,10 .. ,24 for two-digit frets",
    "  Durations       French 1-7 = 1 2 4 8 16 32 64; Italian ;1 .. ;7",
    "  Bass courses    /a //a ///a (7th, 8th, 9th course)",
)

_COMMANDS = (
    "COMMANDS",
    ":w [path]         write .tab; the first write of a new or imported score asks for a path",
    ":wa [path]        export ASCII           :wq / :x        write and quit",
    ":e <path>         open                   :q / :q!        quit / discard changes",
    ":source [path]    view file in less      :help           this help in less",
    ":info / :notes    info and notes pages   :ack            dismiss persistent notice",
    ":undo / :redo     undo / redo            :verify         check measure lengths",
    ":time <sig>       time signature         :header         insert header template",
    ":title :subtitle :author :composer :footnote <text>   set metadata",
    ":midi [path]      export MIDI            :play [bar] [tempo]   play from bar",
    ":play loop [n]    loop bar or selection  :pause          stop playback",
    ":lilypond [path]  export LilyPond        :musicxml [path]      export MusicXML/MXL",
    ":pdf [path]       build PDF              :midicmd [path] show playback command",
    ":hide             toggle status panel    :plugins        plugin browser",
    ":bar add|before|after|del                :barline thin|thick|double|hidden|pale",
    ":repeat none|start|end|dots|both|dc|ds|fine|coda|tocoda|dcalfine|dcalcoda|dsalfine|dsalcoda",
    ":ending clear|1|1,2                      :vocal clear    remove imported melody/lyrics",
    ":orn <char>|clear  :annot <text>|clear   :highlight on|off",
    ":slur :tie :hold start|end|clear         :tuplet 2..9|clear",
    ":arpeggio on|off|toggle                  :separee on|off|toggle",
    ":transpose <int>   :retune <tuning>      :courseshift up|down",
    ":tool reflow|gridflags|flagstyle|comments",
    "",
    "SETTINGS (:set key=value ...; preferences persist, document keys stay in the session)",
    ":set keys=vim|vim+arrows|casual|casual+arrows      :dark / :light / :set theme=auto",
    ":set scoreview=score|staff  showlyrics=on|off  lyricmode=first|current|all  lyricverse=N",
    ":set layout=packed|spread|auto  justify=stretch|center|compact|smart|edge",
    ":set spacing=N barsperline=N maxbars=N measures=start|system|every|five measuresstep=N",
    ":set flagstyle=... flagstems=single|double dotplacement=afterflag|afterstem showdur=on|off",
    ":set playbackscroll=on|off playverses=once|all midipatch=N soundfont=PATH",
    "Document keys: style strings tuning time key tempo bassstrings (and :set lute|guitar)",
)


def help_lines(state: EditorState) -> list[str]:
    profile = key_profile(state)
    viewer = " (read-only viewer)" if profile.read_only else ""
    lines = [f"HELP  keys={profile.label}{viewer}", ""]
    if not profile.read_only:
        lines.extend([*_FIRST_SCORE, ""])
    normal = help_rows(profile, Mode.NORMAL)
    lines.extend(_grouped_section("NORMAL MODE", normal))
    visual_only = tuple(row for row in help_rows(profile, Mode.VISUAL) if row.group is ActionGroup.VISUAL)
    lines.extend(_grouped_section("VISUAL MODE (motions as in normal mode)", _unique(visual_only, normal)))
    if not profile.read_only:
        lines.extend(_grouped_section("INSERT MODE", help_rows(profile, Mode.INSERT)))
        lines.extend([*_INSERT_CONTENT, ""])
    lines.extend(_grouped_section("PROMPTS (:, / and plugin search)", help_rows(profile, Mode.COMMAND)))
    lines.extend(_grouped_section("PAGES", help_rows(profile, Mode.HELP)))
    lines.extend(_grouped_section("PLUGIN BROWSER", help_rows(profile, Mode.PLUGIN)))
    lines.extend(_COMMANDS)
    return lines


def _unique(rows: tuple[HelpRow, ...], seen: tuple[HelpRow, ...]) -> tuple[HelpRow, ...]:
    return tuple(row for row in rows if row not in seen)


def _grouped_section(title: str, rows: tuple[HelpRow, ...]) -> list[str]:
    lines = [title]
    for group in ActionGroup:
        group_rows = [row for row in rows if row.group is group]
        if not group_rows:
            continue
        lines.append(f" {group.value}")
        lines.extend(f"  {row.keys:<{_KEY_COLUMN}} {row.text}" for row in group_rows)
    lines.append("")
    return lines
