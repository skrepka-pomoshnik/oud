from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from oud.core.plugin_model import RemoteTab
from oud.editor.command_ops import cmd_open
from oud.editor.insert_session import set_mode
from oud.editor.keymap import plugin_bindings
from oud.editor.list_menu import (
    MenuNavBindings,
    MenuNavState,
    menu_find_index,
    menu_page_size,
    menu_reduce_nav,
    menu_sync_offset,
)
from oud.editor.plugin_state import (
    plugin_apply_nav,
    plugin_enter_root,
    plugin_open_list,
    plugin_pop_view,
    plugin_push_view,
    plugin_search_append,
    plugin_search_backspace,
    plugin_search_cancel,
    plugin_search_finish,
    plugin_search_start,
)
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
    plugin_enter_root(state, _plugin_root())


def _push_stack(state: EditorState) -> None:
    plugin_push_view(state)


def _pop_stack(state: EditorState) -> bool:
    return plugin_pop_view(state)


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
    plugin_open_list(
        state,
        title=f"{lutemusic.PLUGIN_TITLE}: {kind}",
        items=items,
        plugin_name="lutemusic",
    )
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
        plugin_open_list(
            state,
            title=str(getattr(module, "PLUGIN_TITLE", name)),
            items=list(getattr(module, "root_items", list)()),
            plugin_name=name,
        )
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
        plugin_open_list(state, title=item.title, items=items)
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
        plugin_search_start(state)
        state.message = "Search: "
        return True
    if not state.plugin_query_active:
        return False
    if key in bindings.escape:
        plugin_search_cancel(state)
        state.message = ""
        return True
    if key in bindings.backspace:
        plugin_search_backspace(state)
        state.message = f"Search: {state.plugin_query}"
        return True
    if key in bindings.enter:
        query = plugin_search_finish(state)
        if not query:
            state.message = ""
            return True
        idx = menu_find_index(state.plugin_items, query, lambda item: item.title)
        if idx is not None:
            page_size = menu_page_size(state.screen_height)
            state.plugin_index = idx
            state.plugin_offset = menu_sync_offset(
                state.plugin_index,
                state.plugin_offset,
                page_size,
                len(state.plugin_items),
            )
            state.message = f"Found: {state.plugin_items[idx].title}"
            return True
        state.message = "No match"
        return True
    if 32 <= key <= 126:
        plugin_search_append(state, chr(key))
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


def handle_plugin_key(state: EditorState, key: int) -> bool:  # noqa: PLR0911, C901
    if key == ord("?"):
        from oud.editor.command_ops import show_help  # noqa: PLC0415

        show_help(state)
        return True
    if not state.plugin_items:
        return True
    if _handle_plugin_search(state, key):
        return True
    bindings = plugin_bindings(state)
    action = _plugin_action(state, key)
    if action == "exit":
        if not _pop_stack(state):
            set_mode(state, "normal")
        return True
    if action == "back":
        if not _pop_stack(state):
            set_mode(state, "normal")
        return True

    nav_bindings = MenuNavBindings(
        up=bindings.up,
        down=bindings.down,
        top_prefix=bindings.prefix,
        bottom=bindings.bottom,
    )
    page_size = menu_page_size(state.screen_height)
    nav = MenuNavState(
        index=state.plugin_index,
        offset=state.plugin_offset,
        pending_prefix=state.plugin_pending,
    )
    nav, handled = menu_reduce_nav(
        key,
        nav,
        bindings=nav_bindings,
        length=len(state.plugin_items),
        page_size=page_size,
    )
    plugin_apply_nav(state, index=nav.index, offset=nav.offset, pending=nav.pending_prefix)
    if handled:
        return True
    if action == "open":
        open_plugin_item(state)
        return True
    if action == "download":
        download_plugin_item(state)
        return True
    return True
