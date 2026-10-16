"""Catalog actions for the manager window. No Anki imports."""

from __future__ import annotations

from collections.abc import Callable

from .domain import GithubSource, ReleaseInfo, Subscription, apkg_assets
from .github import FetchResult, GithubError
from .store import (
    Catalog,
    apply_error,
    apply_not_modified,
    apply_release,
    repo_etag,
)

DEFAULT_MAX_BYTES = 536870912


class AssetNotInRelease(Exception):
    pass


def is_duplicate(catalog: Catalog, source: GithubSource) -> bool:
    return any(
        item.owner.casefold() == source.owner.casefold()
        and item.repository.casefold() == source.repository.casefold()
        and item.asset_name == source.asset_name
        for item in catalog.subscriptions
    )


def make_subscription(
    source: GithubSource,
    release: ReleaseInfo,
    subscription_id: str,
) -> Subscription:
    asset = next(
        (item for item in apkg_assets(release) if item.name == source.asset_name),
        None,
    )
    if asset is None:
        raise AssetNotInRelease(source.asset_name)
    return Subscription(
        id=subscription_id,
        owner=source.owner,
        repository=source.repository,
        repo_url=source.repo_url,
        asset_name=source.asset_name,
        display_name=asset.display_name,
    )


def check_catalog(
    catalog: Catalog,
    fetch: Callable[[str, str, str | None], FetchResult],
    checked_at: str,
) -> Catalog:
    """Refresh each repository once. ``fetch`` may raise :class:`GithubError`."""
    seen: set[tuple[str, str]] = set()
    for subscription in catalog.subscriptions:
        key = (subscription.owner.casefold(), subscription.repository.casefold())
        if key in seen:
            continue
        seen.add(key)
        etag = repo_etag(catalog, subscription.owner, subscription.repository)
        try:
            result = fetch(subscription.owner, subscription.repository, etag)
        except GithubError as exc:
            catalog = apply_error(
                catalog,
                owner=subscription.owner,
                repository=subscription.repository,
                code=exc.code,
                checked_at=checked_at,
            )
            continue
        if result.not_modified:
            catalog = apply_not_modified(
                catalog,
                owner=subscription.owner,
                repository=subscription.repository,
                checked_at=checked_at,
                etag=result.etag,
            )
            continue
        if result.release is None:
            catalog = apply_error(
                catalog,
                owner=subscription.owner,
                repository=subscription.repository,
                code="http_error",
                checked_at=checked_at,
            )
            continue
        catalog = apply_release(
            catalog,
            owner=subscription.owner,
            repository=subscription.repository,
            release=result.release,
            checked_at=checked_at,
            etag=result.etag,
        )
    return catalog


def configured_max_bytes(config: object) -> int:
    if not isinstance(config, dict):
        return DEFAULT_MAX_BYTES
    value = config.get("max_download_bytes", DEFAULT_MAX_BYTES)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_MAX_BYTES
