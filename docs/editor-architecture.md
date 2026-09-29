# Editor architecture

`oud.editor` is a hierarchy of explicit domains rather than a flat collection
of operation modules. Package directories contain at most seven direct Python
or package entities, including `__init__.py`.

The intended dependency direction is:

```text
core <- navigation <- editing <- services <- commands <- interaction
```

- `core` owns editor state, documents, coordinates, mode sessions, feedback,
  key descriptions, histories, keymaps, and menu records.
- `navigation` owns layout planning, cursor motion, viewport projection, and
  persistent view state. It does not mutate score content.
- `editing` owns atomic mutations, undo, rhythm, notation, score transforms,
  tablature assignment, and visual selections.
- `services` owns file and media boundaries, playback, validation, application
  bootstrap workflows, and screen composition (`services/screen`).
- `commands` owns command dispatch, command handlers, queries, settings, and
  plugin/tool commands.
- `interaction` owns modal keyboard orchestration. It calls lower domains but
  does not own their behavior.

Imports use canonical hierarchical paths. The old flat module paths are not
retained as forwarding shims.

## Modal keys

`core/input/keymap.py` is the only key table. Each `Binding` maps a key
sequence to an `Action` for one table mode (normal, visual, insert, command
prompt, go-to-bar prompt, help/info/notes pages, plugin browser), optionally
limited to a key style (`vim`/`casual`), to `+arrows` profiles, or to editable
or read-only documents. `ACTION_SPECS` gives every action a help group, a help
text, a `mutates` flag and whether it takes a character argument.

- `interaction/normal/actions.py` resolves counts, multi-key sequences and
  character arguments generically. It refuses every `mutates` action in
  read-only documents; this is the only read-only gate for keys.
- `interaction/normal/handlers.py` and the insert handler map bind each action
  to its behaviour. Tests require a handler for every bound action, one
  meaning per key sequence, and no insert binding that shadows a fret.
- The prompt line editor and the plugin browser's menu helper read their keys
  from the same table (`keys_for`, `first_keys_for` for `gg`).
- `core/input/help.py` generates the key sections of the help page and `:help`
  pager from the same table for the active profile.

`core/input/modes.py` defines the `Mode` enum; `session.set_mode` rejects
unknown modes.

## Screen composition

`services/screen/compose.py` builds every editor frame, for the TUI loop and
for the ASCII screen export alike. Petrucci's `render_piece` paints score
content into every row of the screen it is given and returns whether it drew
the notation or the tablature view. Everything else on screen belongs to Oud:

- `services/screen/status.py` composes the status row and its attributes.
- `services/screen/rhythm.py` computes the tablature duration and bar-meter
  diagnostics shown in that row.
- `services/screen/pages.py` owns the help, info, notes, plugin-browser, and
  ASCII-preview pages.

The status row takes the last screen row unless the bottom panel is off; the
command prompt, search prompt, and pages always show it. `StatusModel` holds its
segments. Identity and position start at the left edge; pending count and keys
(and the insert prefix while inserting), duration, and mode end at the right
edge, so moving the cursor does not move them; the message sits between. When
the row is too narrow, identity, duration, pending keys, meter, and position are
dropped in that order, then the message is cut; the mode is never dropped. The
last column stays empty because curses reports an error when it is written.
