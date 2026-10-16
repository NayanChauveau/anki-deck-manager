"""Deck Manager add-on entry point."""

from __future__ import annotations


def _load() -> None:
    from .ui import register

    register()


try:
    import aqt as _aqt
except ImportError:
    _aqt = None

if _aqt is not None:
    _load()
