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
