from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from oud.core.plugin_model import RemoteTab
from oud.editor.command_ops import cmd_open
from oud.editor.keymap import plugin_bindings
from oud.editor.state import EditorState


@dataclass(frozen=True)
class PluginInfo:
    name: str
    title: str
    path: Path


PLUGIN_HEADER = "# oud-plugin"


@lru_cache(maxsize=1)
def _discover_plugins() -> tuple[PluginInfo, ...]:
    infos: list[PluginInfo] = []
    root = Path(__file__).resolve().parents[1] / "plugins"
    if not root.exists():
        return ()
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        if path.name == "__init__.py":
            continue
        header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:2]
        if not header or not any(line.strip().startswith(PLUGIN_HEADER) for line in header):
            continue
        name = path.stem
        title = name
        try:
            module = _load_plugin_module(name, path)
        except Exception:  # noqa: S112
            continue
        title = getattr(module, "PLUGIN_TITLE", name)
        infos.append(PluginInfo(name=name, title=str(title), path=path))
    return tuple(infos)


def _plugin_root() -> list[RemoteTab]:
    return [
        RemoteTab(title=info.title, url=f"plugin:{info.name}", is_dir=True)
        for info in _discover_plugins()
    ]

def _load_plugin_module(name: str, path: Path):
    module_name = f"oud_plugin_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load plugin {name}")  # noqa: TRY003
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def enter_plugin_mode(state: EditorState) -> None:
    state.mode = "plugin"
    state.plugin_title = "Plugins"
    state.plugin_items = _plugin_root()
    state.plugin_index = 0
    state.plugin_offset = 0
    state.plugin_stack = []
    state.plugin_name = None
    state.plugin_query = ""
    state.plugin_query_active = False
    state.plugin_pending = ""


def _push_stack(state: EditorState) -> None:
    state.plugin_stack.append(
        (
            state.plugin_title,
            list(state.plugin_items),
            state.plugin_index,
            state.plugin_offset,
            state.plugin_name,
        ),
    )


def _pop_stack(state: EditorState) -> bool:
    if not state.plugin_stack:
        return False
    title, items, index, offset, plugin_name = state.plugin_stack.pop()
    state.plugin_title = title
    state.plugin_items = items
    state.plugin_index = index
    state.plugin_offset = offset
    state.plugin_name = plugin_name
    return True


def _select_index_item(state: EditorState, kind: str) -> None:
    if state.plugin_name != "lutemusic":
        state.message = "Unknown plugin index"
        return
    from oud.plugins import lutemusic  # noqa: PLC0415

    url = lutemusic.LUTEMUSIC_URLS.get(kind)
    if not url:
        state.message = "Unknown lutemusic index"
        return
    state.message = "Fetching lutemusic..."
    items = lutemusic.fetch_supported_tabs(url)
    if not items:
        state.message = "No supported files found"
        return
    _push_stack(state)
    state.plugin_title = f"{lutemusic.PLUGIN_TITLE}: {kind}"
    state.plugin_items = items
    state.plugin_index = 0
    state.plugin_offset = 0
    state.plugin_name = "lutemusic"
    state.message = f"Loaded {len(items)} entries"


def download_plugin_item(state: EditorState) -> Path | None:
    if not state.plugin_items:
        state.message = "No plugin items"
        return None
    if not state.plugin_name:
        state.message = "Select a plugin first"
        return None
    item = state.plugin_items[state.plugin_index]
    if item.url.startswith("lutemusic:index:") or item.is_dir:
        state.message = "Select a list first"
        return None
    dest_dir = Path("lutemusic")
    if state.plugin_name != "lutemusic":
        state.message = "Plugin does not support downloads"
        return None
    from oud.plugins import lutemusic  # noqa: PLC0415

    try:
        path = lutemusic.download_tab(item, dest_dir)
    except OSError as exc:
        state.message = f"Download failed: {exc}"
        return None
    state.message = f"Downloaded {path.name}"
    return path


def open_plugin_item(state: EditorState) -> None:  # noqa: PLR0911
    item = state.plugin_items[state.plugin_index]
    if item.url.startswith("plugin:"):
        name = item.url.split(":", 1)[1]
        try:
            info = next(info for info in _discover_plugins() if info.name == name)
            module = _load_plugin_module(name, info.path)
        except Exception:
            state.message = f"Failed to load plugin {name}"
            return
        _push_stack(state)
        state.plugin_title = getattr(module, "PLUGIN_TITLE", name)
        state.plugin_items = list(getattr(module, "root_items", list)())
        state.plugin_index = 0
        state.plugin_offset = 0
        state.plugin_name = name
        if not state.plugin_items:
            state.message = "Plugin has no items"
        return
    if item.url.startswith("lutemusic:index:"):
        kind = item.url.split(":")[-1]
        _select_index_item(state, kind)
        return
    if item.is_dir:
        if state.plugin_name != "lutemusic":
            state.message = "Plugin does not support folders"
            return
        state.message = "Fetching lutemusic..."
        from oud.plugins import lutemusic  # noqa: PLC0415

        items = lutemusic.fetch_supported_tabs(item.url)
        if not items:
            state.message = "No supported files found"
            return
        _push_stack(state)
        state.plugin_title = item.title
        state.plugin_items = items
        state.plugin_index = 0
        state.plugin_offset = 0
        state.message = f"Loaded {len(items)} entries"
        return
    if state.plugin_name and state.plugin_name != "lutemusic":
        state.message = "Plugin does not support opening files"
        return
    path = download_plugin_item(state)
    if path is None:
        return
    cmd_open(state, str(path))


def _handle_plugin_search(state: EditorState, key: int) -> bool:  # noqa: PLR0911
    bindings = plugin_bindings(state)
    if key in bindings.search:
        state.plugin_query_active = True
        state.plugin_query = ""
        state.message = "Search: "
        return True
    if not state.plugin_query_active:
        return False
    if key in bindings.escape:
        state.plugin_query_active = False
        state.plugin_query = ""
        state.message = ""
        return True
    if key in bindings.backspace:
        state.plugin_query = state.plugin_query[:-1]
        state.message = f"Search: {state.plugin_query}"
        return True
    if key in bindings.enter:
        query = state.plugin_query.strip().lower()
        state.plugin_query_active = False
        if not query:
            state.message = ""
            return True
        for idx, item in enumerate(state.plugin_items):
            if query in item.title.lower():
                state.plugin_index = idx
                page_size = max(1, state.screen_height - 2)
                state.plugin_offset = min(idx, max(0, idx - page_size + 1))
                state.message = f"Found: {item.title}"
                return True
        state.message = "No match"
        return True
    if 32 <= key <= 126:
        state.plugin_query += chr(key)
        state.message = f"Search: {state.plugin_query}"
        return True
    return True


def _plugin_action(state: EditorState, key: int) -> str | None:
    bindings = plugin_bindings(state)
    actions = {
        "exit": bindings.exit,
        "back": bindings.back,
        "top": bindings.prefix,
        "bottom": bindings.bottom,
        "up": bindings.up,
        "down": bindings.down,
        "open": bindings.open,
        "download": bindings.download,
    }
    for name, keys in actions.items():
        if key in keys:
            return name
    return None


def handle_plugin_key(state: EditorState, key: int) -> bool:  # noqa: PLR0911, C901, PLR0912
    if key == ord("?"):
        from oud.editor.command_ops import show_help  # noqa: PLC0415

        show_help(state)
        return True
    if not state.plugin_items:
        return True
    if _handle_plugin_search(state, key):
        return True
    action = _plugin_action(state, key)
    if action == "exit":
        if not _pop_stack(state):
            state.mode = "normal"
        return True
    if action == "back":
        if not _pop_stack(state):
            state.mode = "normal"
        return True
    if action == "top":
        if state.plugin_pending == "g":
            state.plugin_index = 0
            state.plugin_offset = 0
            state.plugin_pending = ""
            return True
        state.plugin_pending = "g"
        return True
    state.plugin_pending = ""
    page_size = max(1, state.screen_height - 2)
    if action == "bottom":
        state.plugin_index = max(0, len(state.plugin_items) - 1)
        state.plugin_offset = max(0, state.plugin_index - page_size + 1)
        return True
    if action == "down":
        state.plugin_index = min(state.plugin_index + 1, len(state.plugin_items) - 1)
        if state.plugin_index >= state.plugin_offset + page_size:
            state.plugin_offset = state.plugin_index - page_size + 1
        return True
    if action == "up":
        state.plugin_index = max(0, state.plugin_index - 1)
        state.plugin_offset = min(state.plugin_offset, state.plugin_index)
        return True
    if action == "open":
        open_plugin_item(state)
        return True
    if action == "download":
        download_plugin_item(state)
        return True
    return True
