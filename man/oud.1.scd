oud(1) | terminal lute tablature editor and viewer

# NAME

**oud** - terminal editor and viewer for lute tablature

# SYNOPSIS

**oud** [*FILE*]

**oud** **tui** [*--readonly*] [*FILE*]

**oud** **ascii** *INPUT* [*-o* *OUTPUT*] [*--bars* *N|START:END*] [*-f*]

**oud** **convert** *INPUT* [*OUTPUT*] [*--input-format* *FORMAT*] [*--format* *FORMAT*] [*-f*]

# DESCRIPTION

**oud** is a curses editor and viewer for Renaissance lute tablature. It reads
TAB, FT3, and supported MusicXML/MXL files, provides a compact terminal proof,
and exports TAB, ASCII, MIDI, LilyPond, PDF, MusicXML, and MXL.

MusicXML is the default save format. TAB files (the original **tab** program's
format) are read and written in full. FT3 is import-only: a score with
tablature opens editable, with its notation staves kept aligned and saved to
MusicXML, and never changes the source. Duet scores and scores without
tablature open in read-only viewer mode so visible material cannot disappear on
save. A save names the marks it cannot keep; an import names the notes it did
not read.

Text conversion can read from or write to **-**. MIDI, MXL, and PDF conversion
require filesystem paths. PDF conversion retains the generated LilyPond source
when LilyPond is unavailable or fails.

# OPTIONS

**--config** *PATH*

: Read settings from *PATH*. The default is **config.toml**, resolved as
described under *FILES*.

**--readonly**

: Open the TUI in read-only viewer mode.

**--version**

: Print the installed version and exit.

**-h**, **--help**

: Print command help and exit.

The **tui** subcommand opens the interactive editor. **ascii** renders a text
snapshot; *INPUT* must be a path. **convert** selects the output format from
the output suffix unless **--format** is supplied; without *OUTPUT* it writes
*INPUT* with the suffix **.musicxml**. When either stream endpoint
is **-**, specify the other format explicitly with **--input-format** or
**--format** as required.

**-f**, **--force**

: Permit replacement of an existing non-interactive output file.

# INTERACTIVE COMMANDS

The TUI uses Vim-like normal, insert, and command modes. **h/j/k/l** or the
arrow keys move; **i** enters insert mode; **Esc** returns to normal mode; and
**Ctrl-C** quits like **q**: with unsaved changes it asks once and quits on the
second press. It also cancels prompts and closes pages. In insert mode letters
and digits are frets and **z** enters a rest.

**:w** [*PATH*]

: Save as MusicXML (**.musicxml**, **.xml**) or TAB (**.tab**), by the suffix. A
first write opens a command prompt prefilled with a sibling or default
**.musicxml** destination.

**:e** *PATH*

: Open a score.

**:midi** [*PATH*]

: Export MIDI.

**:play** [*BAR*]

: Play from a one-based bar number.

**:lilypond** [*PATH*]

: Export LilyPond source.

**:pdf** [*PATH*]

: Export LilyPond and compile a PDF. The default build path is
**build/lilypond/**.

**:set** *OPTION*=*VALUE*

: Change editor, playback, completion, layout, or publication settings. The
**lilypond** setting selects the executable; **completion=fzf** enables optional
fuzzy path ranking; **playbackscroll=off** disables score following.

**:q** or **:q!**

: Quit, subject to the modified-document confirmation for **:q**.

# FILES

**config.toml**

: Settings file. A relative name is read from the current directory only when
that file already has a **[settings]** table; otherwise it lives in
*$XDG_CONFIG_HOME/oud/* (default *~/.config/oud/*). **:set** writes only the
preference keys it changed. Document properties (style, strings, tuning, time,
key, tempo, bassstrings) apply to the open score only. A config file containing
other tables is never rewritten.

**build/lilypond/**

: Default location for interactive LilyPond/PDF build products. This directory
is not created until a PDF build is requested.

**~/.local/share/man/man1/oud.1**

: Default user-local installation target for the manual page.

# ENVIRONMENT

**TERM**

: Selects terminal capabilities used by curses.

**PATH**

: Used to locate the configured LilyPond executable, and optional **fzf**,
**fluidsynth**, and **timidity** playback programs.

**XDG_CONFIG_HOME**

: Base directory for the user settings file; defaults to *~/.config*.

**ESCDELAY**

: Milliseconds curses waits to distinguish **Esc** from escape sequences. Oud
uses 25 ms unless this variable is set.

# EXIT STATUS

0

: Success.

2

: Invalid command-line arguments or bar range.

3

: Input could not be loaded or rendered.

4

: Output could not be written or compiled.

130

: A non-interactive command was interrupted with **Ctrl-C**.

# DIAGNOSTICS

Errors are written to standard error for non-interactive commands. TUI import,
playback, and export failures are shown in the status line. Missing or invalid
source files produce a visible import warning and do not create fabricated
score content.

# EXAMPLES

Open a score:

	oud score.tab

Render selected bars as text:

	oud ascii score.ft3 --bars 1:8

Convert a score to LilyPond:

	oud convert score.ft3 score.ly

Build a PDF and retain generated files under **build/**:

	oud convert score.ft3 build/lilypond/score.pdf -f

Install the manual page for the current user:

	scripts/install_man.sh

# SEE ALSO

**lilypond**(1), **fzf**(1), **fluidsynth**(1), **timidity**(1)

# AUTHORS

Maintained by frnm. See the project repository for contributors:
https://github.com/skrepka-pomoshnik/oud

# LICENSE

GPL-3.0-only. See **LICENSE** in the source distribution.
