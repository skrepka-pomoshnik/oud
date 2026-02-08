from __future__ import annotations

HELP_LINES = [
    "HELP",
    "",
    "NAVIGATION                              EDITING",
    "Up   k / ^P / Up                        Insert   i / Enter",
    "Down j / ^N / Down                      Replace  r (one)",
    "Left h / ^B / Left                      Delete   x / [count]x",
    "Right l / ^F / Right                    Clear    Space (insert)",
    "Row  { / } / PgUp / PgDn                Yank     yy  Paste  p",
    "Bar  w / b / , / .                      Delete  dd (bar)",
    "Undo u / Redo ^R                         Bar     o/O  +/-",
    "Top  gg / g                             Help    ? (less) / F1",
    "Info I                                   Flags f (cycle style)",
    "Search * / # / n / N                     Marks   m{a}  'a  `a",
    "Match %                                  Play    M",
    "Add  gj (bass string)",
    "Plugins gp or :plugins (plugin: j/k move, h back, l/enter open, d download, / search)",
    "Flags f (cycle style)                   Letters F (c)",
    "End  G / $                              Command : / Search /",
    "",
    "INSERT MODE",
    "Frets: french a-t (no j), italian 0-9/x",
    "Italian multi-fret: ,10 .. ,24 (comma + two digits)",
    "Bass shorthand: /a, //a, ///a (adds 7th/8th/9th course)",
    "Durations: 1 2 4 8 6 3 (french) or Ctrl+1..7 / ;1..7 (italian)",
    "Barline: | sets thin barline",
    "Esc returns to normal",
    "",
    "COMMANDS",
    ":w [path]        write .tab       :wa [path]        write ascii (save-as)",
    ":wascii [path]   write ascii",
    ":wq/:x           write + quit     :q!               quit without save",
    ":e <path>        open             :source [path]    view file with less",
    ":time <sig>      set time sig     :verify           check measure length",
    ":info             show info page",
    ":undo             undo             :redo             redo",
    ":title <text>     set title        :author <text>     set author",
    ":subtitle <text>  set subtitle     :composer <text>   set composer",
    ":footnote <text>  set footnote     :header            insert header template",
    ":midi [path]     export midi      :play [bar] [tempo] play from bar",
    ":lilypond [path] export lilypond  :musicxml [path] export musicxml/mxl",
    ":pdf              compile pdf (P)",
    ":midicmd [path]  show midi command",
    ":bar add|before|after|del         :barline thin|thick|double|hidden|pale",
    (
        ":repeat none|start|end|dots|both|dc|ds|fine|coda|tocoda|"
        "dcalfine|dcalcoda|dsalfine|dsalcoda   :orn <char>|clear"
    ),
    ":annot <text>|clear               :highlight on/off",
    ":slur start/end/clear             :tie start/end/clear",
    ":hold start/end/clear",
    (
        ":set style=... strings=... tuning=... tuninglabels=... "
        "flagstyle=... flagstems=... time=... (or auto)"
    ),
    ":set keys=vim|vim+arrows|casual|casual+arrows",
    (
        ":set spacing=... barsperline=... maxbars=... maxchords=... chordwrap=... bargap=... "
        "linelen=... staffthick=... fontstyle=..."
    ),
    ":set flagredundant=on|off",
    (
        ":set layout=packed|spread|auto|stretch justify=stretch|center|compact|smart|edge "
        "showtuning=on|off"
    ),
    ":set key=... countdots=on/off grid=on/off",
    ":set lute|guitar (preset metasettings)",
    ":set measuresstep=... (used with measures=every)",
    ":set italianorient=normal|reverse italianmultifret=on|off viewinvert=on|off",
    ":set frenchc=normal|alt",
    ":set midipatch=... midigate=... soundfont=... tempo=...",
    ":set charstyle=... title=... author=... composer=...",
    ":tool reflow|gridflags|flagstyle|comments",
]


def help_lines() -> list[str]:
    return list(HELP_LINES)
