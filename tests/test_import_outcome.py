from outcome import import_was_confirmed


def test_closing_the_modal_dialog_is_not_an_import() -> None:
    assert (
        import_was_confirmed(still_application_modal=True, backend_op_finished=False)
        is False
    )


def test_import_done_confirms_even_when_no_hook_was_seen() -> None:
    assert (
        import_was_confirmed(still_application_modal=False, backend_op_finished=False)
        is True
    )


def test_backend_op_confirms_even_if_the_dialog_stays_modal() -> None:
    assert (
        import_was_confirmed(still_application_modal=True, backend_op_finished=True)
        is True
    )


def test_both_signals_confirm() -> None:
    assert (
        import_was_confirmed(still_application_modal=False, backend_op_finished=True)
        is True
    )
