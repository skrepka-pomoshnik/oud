from __future__ import annotations

import importlib
import sys


def alias_module(alias: str, target: str) -> None:
    """Keep an old module path pointing at the canonical Petrucci module."""
    sys.modules[alias] = importlib.import_module(target)
