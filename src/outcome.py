"""Pure decision for the native APKG import dialog.

Anki 26.09's ``OpChanges`` has no operation enum. ``Op.Import`` is not a
signal an add-on can read. Two independent facts are.

``importAnkiPackage`` returns ``ImportResponse``, whose first field is
``OpChanges``. The generated client sends ``Anki-Op-Changes: 2``, and
``mediasrv`` then emits ``operation_did_execute`` for that dialog.

``importDone`` runs only after that call resolves. It drops the dialog from
``ApplicationModal`` to ``NonModal``. Closing the dialog before that leaves
it modal and aborts the backend import.
"""

from __future__ import annotations


def import_was_confirmed(
    *, still_application_modal: bool, backend_op_finished: bool
) -> bool:
    """Return whether the native import committed.

    ``backend_op_finished`` is true when ``operation_did_execute`` ran with
    this import dialog as initiator. ``still_application_modal`` is the
    dialog modality when it finishes. Either fact is enough: the backend op
    means the package import returned, and a non-modal dialog means
    ``importDone`` ran after that return.
    """
    return backend_op_finished or not still_application_modal
