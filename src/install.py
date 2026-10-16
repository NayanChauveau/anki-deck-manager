"""Download a re-read release, then import files one at a time.

The installed version changes only after the import callback reports success.
No Anki imports: the caller supplies the download and the import dialog.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .download import discard_package
from .domain import ReleaseInfo, Subscription, commit_install, status_of
from .github import GithubError, fetch_latest
from .store import Catalog, apply_release


@dataclass(frozen=True)
class Prepared:
    release: ReleaseInfo | None = None
    path: Path | None = None
    error: str | None = None


Prepare = Callable[[Subscription, Callable[[Prepared], None]], None]
ImportFile = Callable[[Path, Callable[[bool], None]], None]


def load_latest(subscription: Subscription) -> ReleaseInfo:
    """Read the stable release. The version stored on the subscription is not used."""
    result = fetch_latest(subscription.owner, subscription.repository)
    if result.release is None:
        raise GithubError("http_error")
    return result.release


def run_install_queue(
    catalog: Catalog,
    subscription_ids: list[str],
    *,
    prepare: Prepare,
    import_file: ImportFile,
    checked_at: Callable[[], str],
    on_finished: Callable[[Catalog], None],
) -> None:
    """Install each id after the previous import dialog has closed."""
    remaining = list(subscription_ids)
    state = {"catalog": catalog}

    def advance() -> None:
        if not remaining:
            on_finished(state["catalog"])
            return
        subscription_id = remaining.pop(0)
        current = _find(state["catalog"], subscription_id)
        if current is None:
            advance()
            return

        def after_prepare(prepared: Prepared) -> None:
            release = prepared.release
            if release is not None:
                state["catalog"] = apply_release(
                    state["catalog"],
                    owner=current.owner,
                    repository=current.repository,
                    release=release,
                    checked_at=checked_at(),
                    etag=None,
                )
            if prepared.error == "cancelled":
                _unlink(prepared.path)
                on_finished(state["catalog"])
                return
            if prepared.error or release is None:
                _unlink(prepared.path)
                state["catalog"] = _mark(
                    state["catalog"],
                    subscription_id,
                    prepared.error or "http_error",
                    checked_at(),
                )
                advance()
                return
            fresh = _find(state["catalog"], subscription_id)
            if fresh is None or prepared.path is None or status_of(fresh) != "update_available":
                _unlink(prepared.path)
                advance()
                return

            def after_import(confirmed: bool) -> None:
                _unlink(prepared.path)
                if confirmed:
                    installed = _find(state["catalog"], subscription_id)
                    if installed is not None:
                        state["catalog"] = _replace(
                            state["catalog"],
                            commit_install(installed, release, installed_at=checked_at()),
                        )
                advance()

            try:
                import_file(prepared.path, after_import)
            except Exception:
                _unlink(prepared.path)
                state["catalog"] = _mark(
                    state["catalog"],
                    subscription_id,
                    "http_error",
                    checked_at(),
                )
                advance()

        prepare(current, after_prepare)

    advance()


def _find(catalog: Catalog, subscription_id: str) -> Subscription | None:
    return next((item for item in catalog.subscriptions if item.id == subscription_id), None)


def _replace(catalog: Catalog, subscription: Subscription) -> Catalog:
    return Catalog(
        tuple(
            subscription if item.id == subscription.id else item
            for item in catalog.subscriptions
        )
    )


def _mark(catalog: Catalog, subscription_id: str, code: str, checked_at: str) -> Catalog:
    current = _find(catalog, subscription_id)
    if current is None:
        return catalog
    return _replace(
        catalog,
        replace(current, last_error=code, last_checked_at=checked_at),
    )


def _unlink(path: Path | None) -> None:
    discard_package(path)
