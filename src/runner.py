"""Run a download off the Qt thread, then open Anki's import dialog.

``mw.progress.want_cancel()`` reads the progress window's ``wantCancel`` flag.
The download checks it between chunks. The next file waits until the dialog
emits ``finished``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from . import strings
from .domain import compare_subscription, find_apkg, status_of
from .download import DownloadError, discard_package, download_asset, temporary_package, urllib_open
from .github import GithubError
from .install import Prepared, load_latest, run_install_queue
from .store import Catalog


def start_installs(
    mw: object,
    catalog: Catalog,
    subscription_ids: list[str],
    *,
    max_bytes: int,
    on_finished: Callable[[Catalog], None],
) -> None:
    from aqt.operations import QueryOp

    from .importer import import_package

    def checked_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    def prepare(subscription, done) -> None:  # type: ignore[no-untyped-def]
        held: list[Path | None] = [None]

        def op(_col: object) -> Prepared:
            release = None
            try:
                release = load_latest(subscription)
                compared = compare_subscription(subscription, release)
                if status_of(compared) != "update_available":
                    return Prepared(release=release)
                asset = find_apkg(release, subscription.asset_name)
                if asset is None:
                    return Prepared(release=release, error="asset_missing")
                path = temporary_package(asset.name)
                held[0] = path
                download_asset(
                    asset.download_url,
                    path,
                    max_bytes=max_bytes,
                    announced_size=asset.size,
                    open_url=urllib_open,
                    cancelled=_cancelled(mw),
                )
                return Prepared(release=release, path=path)
            except (GithubError, DownloadError) as exc:
                discard_package(held[0])
                held[0] = None
                return Prepared(release=release, error=exc.code)

        def success(prepared: Prepared) -> None:
            done(prepared)

        def failure(exc: Exception) -> None:
            discard_package(held[0])
            held[0] = None
            code = exc.code if isinstance(exc, (GithubError, DownloadError)) else "http_error"
            done(Prepared(error=code))

        (
            QueryOp(parent=mw, op=op, success=success)
            .failure(failure)
            .without_collection()
            .with_progress(strings.DOWNLOADING)
            .run_in_background()
        )

    def import_file(path: Path, done) -> None:  # type: ignore[no-untyped-def]
        import_package(mw, path, lambda outcome: done(outcome.confirmed))

    run_install_queue(
        catalog,
        subscription_ids,
        prepare=prepare,
        import_file=import_file,
        checked_at=checked_at,
        on_finished=on_finished,
    )


def _cancelled(mw: object) -> Callable[[], bool]:
    def cancelled() -> bool:
        progress = getattr(mw, "progress", None)
        want_cancel = getattr(progress, "want_cancel", None)
        if want_cancel is None:
            return False
        return bool(want_cancel())

    return cancelled
