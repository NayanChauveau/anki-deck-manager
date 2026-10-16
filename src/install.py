"""Download a re-read release, then import files one at a time.

The installed version changes only after the import callback reports success.
No Anki imports: the caller supplies the download and the import dialog.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .domain import (
    GithubSource,
    ReleaseAsset,
    ReleaseInfo,
    Subscription,
    compare_subscription,
    status_of,
)
from .github import GithubError, fetch_release
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
    source = GithubSource(
        owner=subscription.owner,
        repository=subscription.repository,
        repo_url=subscription.repo_url,
        version=subscription.installed_version or "0.0.0",
        asset_name=subscription.asset_name,
    )
    result = fetch_release(source, latest=True)
    if result.release is None:
        raise GithubError("http_error")
    return result.release


def commit_install(
    subscription: Subscription,
    release: ReleaseInfo,
    *,
    installed_at: str,
) -> Subscription:
    asset = _asset(subscription, release)
    return Subscription(
        **{
            **subscription.__dict__,
            "display_name": asset.display_name if asset else subscription.display_name,
            "installed_release_id": release.release_id,
            "installed_version": release.tag,
            "installed_asset_id": asset.asset_id if asset else subscription.installed_asset_id,
            "available_release_id": None,
            "available_version": None,
            "available_asset_id": None,
            "last_installed_at": installed_at,
            "last_error": None,
        }
    )


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
                raise

        prepare(current, after_prepare)

    advance()


def _asset(subscription: Subscription, release: ReleaseInfo) -> ReleaseAsset | None:
    return next(
        (asset for asset in release.assets if asset.name == subscription.asset_name),
        None,
    )


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
        Subscription(**{**current.__dict__, "last_error": code, "last_checked_at": checked_at}),
    )


def _unlink(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)
