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
- `services` owns file and media boundaries, playback, validation, status, and
  application bootstrap workflows.
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
- `commands/help.py` generates the key sections of the help page and `:help`
  pager from the same table for the active profile. Petrucci only paints the
  lines it receives.

`core/input/modes.py` defines the `Mode` enum; `session.set_mode` rejects
unknown modes.
