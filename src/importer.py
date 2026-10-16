"""Open Anki's native APKG import dialog and report whether it committed.

This does not download a file and does not record a subscription. Callers
must wait for ``on_done`` before starting another import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .outcome import import_was_confirmed

_import_open = False


@dataclass(frozen=True)
class ImportOutcome:
    confirmed: bool


def import_package(
    mw: object,
    path: str | Path,
    on_done: Callable[[ImportOutcome], None],
) -> None:
    """Show the same dialog as File → Import and report the result later."""
    global _import_open

    package = Path(path)
    if package.suffix.lower() != ".apkg" or not package.is_file():
        raise ValueError(f"Not an APKG file: {path}")
    if _import_open:
        raise RuntimeError("An import dialog is already open")

    from aqt import gui_hooks
    from aqt.import_export.import_dialog import AnkiPackageArgs, ImportDialog
    from aqt.qt import Qt, qconnect

    dialog = ImportDialog(mw, AnkiPackageArgs(str(package)))
    state = {"backend_op_finished": False}
    _import_open = True

    def on_op(_changes: object, initiator: object) -> None:
        if initiator is dialog:
            state["backend_op_finished"] = True

    def on_finished(_code: int) -> None:
        global _import_open
        gui_hooks.operation_did_execute.remove(on_op)
        _import_open = False
        still_modal = dialog.windowModality() == Qt.WindowModality.ApplicationModal
        on_done(
            ImportOutcome(
                confirmed=import_was_confirmed(
                    still_application_modal=still_modal,
                    backend_op_finished=state["backend_op_finished"],
                )
            )
        )

    gui_hooks.operation_did_execute.append(on_op)
    qconnect(dialog.finished, on_finished)
