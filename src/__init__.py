"""Deck Manager add-on entry point.

Anki loads this package from the add-on folder. The manager window, GitHub
client and startup check are intentionally absent at this stage.
"""

from __future__ import annotations


def _load() -> None:
    # Importing the dialog wrapper fails fast if this Anki build cannot host it.
    # Nothing is shown until a later point adds the Tools menu.
    from . import importer as _importer

    del _importer


try:
    import aqt as _aqt
except ImportError:
    _aqt = None

if _aqt is not None:
    _load()
