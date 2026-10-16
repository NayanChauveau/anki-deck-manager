"""Deck Manager add-on entry point.

Anki loads this package from the add-on folder. The startup check is
intentionally absent at this stage.
"""

from __future__ import annotations


def _load() -> None:
    from . import importer as _importer
    from .ui import register

    del _importer
    register()


try:
    import aqt as _aqt
except ImportError:
    _aqt = None

if _aqt is not None:
    _load()
