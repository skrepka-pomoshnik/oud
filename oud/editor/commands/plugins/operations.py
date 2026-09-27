from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from oud.editor.commands.dispatch import cmd_open
from oud.editor.commands.plugins.state import (
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
from oud.editor.core.input.keymap import Action, ResolvedKeymap, keymap_for
from oud.editor.core.input.menu import (
    MenuNavBindings,
    MenuNavState,
    menu_find_index,
    menu_page_size,
    menu_reduce_nav,
    menu_sync_offset,
)
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.services import plugins as plugin_package
from oud.services.plugins.model import RemoteTab


@dataclass(frozen=True)
class PluginInfo:
    name: str
    title: str
    path: Path


PLUGIN_HEADER = "# oud-plugin"
PLUGIN_DOWNLOAD_ROOT = Path("downloads/lutemusic")


@lru_cache(maxsize=1)
def _discover_plugins() -> tuple[PluginInfo, ...]:
    infos: list[PluginInfo] = []
    root = Path(plugin_package.__file__).resolve().parent
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
    return [RemoteTab(title=info.title, url=f"plugin:{info.name}", is_dir=True) for info in _discover_plugins()]


def _clear_plugin_confirm(state: EditorState) -> None:
    state.plugins.confirm = ""


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
    from oud.services.plugins import lutemusic  # noqa: PLC0415

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


def _open_random_lutemusic_ft3(state: EditorState) -> None:
    from oud.services.plugins import lutemusic  # noqa: PLC0415

    state.message = "Searching random FT3..."
    item = lutemusic.random_ft3()
    if item is None:
        state.message = "No random FT3 found"
        return
    _push_stack(state)
    plugin_open_list(
        state,
        title=f"{lutemusic.PLUGIN_TITLE}: random",
        items=[item],
        plugin_name="lutemusic",
    )
    state.message = f"Random: {item.title}"


def _open_plugin_root_item(state: EditorState, item: RemoteTab) -> bool:
    if item.url == "lutemusic:random":
        _open_random_lutemusic_ft3(state)
        return True
    if not item.url.startswith("plugin:"):
        return False
    name = item.url.split(":", 1)[1]
    try:
        info = next(info for info in _discover_plugins() if info.name == name)
        module = _load_plugin_module(name, info.path)
    except Exception:
        state.message = f"Failed to load plugin {name}"
        return True
    _push_stack(state)
    plugin_open_list(
        state,
        title=str(getattr(module, "PLUGIN_TITLE", name)),
        items=list(getattr(module, "root_items", list)()),
        plugin_name=name,
    )
    if not state.plugin_items:
        state.message = "Plugin has no items"
    return True


def _open_lutemusic_dir_item(state: EditorState, item: RemoteTab) -> bool:
    if item.url.startswith("lutemusic:index:"):
        kind = item.url.split(":")[-1]
        _select_index_item(state, kind)
        return True
    if not item.is_dir:
        return False
    _clear_plugin_confirm(state)
    if state.plugin_name != "lutemusic":
        state.message = "Plugin does not support folders"
        return True
    state.message = "Fetching lutemusic..."
    from oud.services.plugins import lutemusic  # noqa: PLC0415

    items = lutemusic.fetch_supported_tabs(item.url)
    if not items:
        state.message = "No supported files found"
        return True
    _push_stack(state)
    plugin_open_list(state, title=item.title, items=items)
    state.message = f"Loaded {len(items)} entries"
    return True


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
    dest_dir = PLUGIN_DOWNLOAD_ROOT
    if state.plugin_name != "lutemusic":
        state.message = "Plugin does not support downloads"
        return None
    from oud.services.plugins import lutemusic  # noqa: PLC0415

    try:
        path = lutemusic.download_tab(item, dest_dir)
    except OSError as exc:
        state.message = f"Download failed: {exc}"
        return None
    state.message = f"Downloaded {path.name}"
    _clear_plugin_confirm(state)
    return path


def download_plugin_folder_recursive(state: EditorState) -> list[Path] | None:
    if not state.plugin_items:
        state.message = "No plugin items"
        return None
    if state.plugin_name != "lutemusic":
        state.message = "Plugin does not support folder downloads"
        return None
    item = state.plugin_items[state.plugin_index]
    if not item.is_dir:
        state.message = "Select a folder"
        return None
    token = f"download-tree:{item.url}"
    if state.plugins.confirm != token:
        state.plugins.confirm = token
        state.message = "Press D again: download folder recursively (FT3 only)"
        return None
    from oud.services.plugins import lutemusic  # noqa: PLC0415

    dest_dir = PLUGIN_DOWNLOAD_ROOT / item.title
    try:
        paths = lutemusic.download_folder_ft3(item, dest_dir)
    except OSError as exc:
        state.message = f"Download failed: {exc}"
        _clear_plugin_confirm(state)
        return None
    _clear_plugin_confirm(state)
    state.message = f"Downloaded {len(paths)} ft3 files"
    return paths


def open_plugin_item(state: EditorState) -> None:
    item = state.plugin_items[state.plugin_index]
    if _open_plugin_root_item(state, item):
        return
    if _open_lutemusic_dir_item(state, item):
        return
    if state.plugin_name and state.plugin_name != "lutemusic":
        state.message = "Plugin does not support opening files"
        return
    path = download_plugin_item(state)
    if path is None:
        return
    cmd_open(state, str(path))


def _finish_plugin_search(state: EditorState) -> bool:
    query = plugin_search_finish(state)
    if not query:
        state.message = ""
        return True
    idx = menu_find_index(state.plugin_items, query, lambda item: item.title)
    if idx is None:
        state.message = "No match"
        return True
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


def _handle_plugin_search(state: EditorState, key: int) -> bool:
    if not state.plugin_query_active:
        if keymap_for(state, Mode.PLUGIN).lookup((key,)) is not Action.PLUGIN_FILTER:
            return False
        plugin_search_start(state)
        state.message = "Search: "
        return True
    # While filtering, the browser edits a query line with the prompt keys.
    action = keymap_for(state, Mode.SEARCH).lookup((key,))
    if action is Action.PROMPT_CANCEL:
        plugin_search_cancel(state)
        state.message = ""
    elif action is Action.PROMPT_BACKSPACE:
        plugin_search_backspace(state)
        state.message = f"Search: {state.plugin_query}"
    elif action is Action.PROMPT_SUBMIT:
        return _finish_plugin_search(state)
    elif ord(" ") <= key <= ord("~"):
        plugin_search_append(state, chr(key))
        state.message = f"Search: {state.plugin_query}"
    return True


def _leave_plugin_mode(state: EditorState) -> None:
    _clear_plugin_confirm(state)
    if not _pop_stack(state):
        set_mode(state, Mode.NORMAL)


def _handle_plugin_navigation(state: EditorState, key: int, keymap: ResolvedKeymap) -> bool:
    nav_bindings = MenuNavBindings(
        up=keymap.keys_for(Action.PLUGIN_UP),
        down=keymap.keys_for(Action.PLUGIN_DOWN),
        top_prefix=keymap.first_keys_for(Action.PLUGIN_TOP),
        bottom=keymap.keys_for(Action.PLUGIN_BOTTOM),
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
        _clear_plugin_confirm(state)
    return handled


_PLUGIN_COMMANDS: Mapping[Action, Callable[[EditorState], object]] = MappingProxyType(
    {
        Action.PLUGIN_OPEN: open_plugin_item,
        Action.PLUGIN_DOWNLOAD: download_plugin_item,
        Action.PLUGIN_DOWNLOAD_TREE: download_plugin_folder_recursive,
    },
)
# Navigation actions are reduced by the shared menu helper.
PLUGIN_NAVIGATION = frozenset({Action.PLUGIN_UP, Action.PLUGIN_DOWN, Action.PLUGIN_TOP, Action.PLUGIN_BOTTOM})
_PLUGIN_EXITS = frozenset({Action.PLUGIN_CLOSE, Action.PLUGIN_BACK})
PLUGIN_HANDLED_ACTIONS = frozenset(
    {*_PLUGIN_COMMANDS, *PLUGIN_NAVIGATION, *_PLUGIN_EXITS, Action.PLUGIN_FILTER, Action.PLUGIN_HELP},
)


def handle_plugin_key(state: EditorState, key: int) -> bool:
    keymap = keymap_for(state, Mode.PLUGIN)
    action = keymap.lookup((key,))
    if action is Action.PLUGIN_HELP and not state.plugin_query_active:
        from oud.editor.commands.dispatch import show_help  # noqa: PLC0415

        show_help(state)
        return True
    if _handle_plugin_search(state, key):
        return True
    if action in _PLUGIN_EXITS:
        _leave_plugin_mode(state)
        return True
    if not state.plugin_items:
        return True
    if _handle_plugin_navigation(state, key, keymap):
        return True
    command = _PLUGIN_COMMANDS.get(action) if action is not None else None
    if command is None:
        _clear_plugin_confirm(state)
    else:
        command(state)
    return True
