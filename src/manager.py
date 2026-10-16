"""Catalog actions for the manager window. No Anki imports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .domain import (
    GithubSource,
    ReleaseInfo,
    Subscription,
    check_is_due,
    find_apkg,
    repository_key,
)
from .github import FetchResult, GithubError
from .store import (
    Catalog,
    apply_error,
    apply_not_modified,
    apply_release,
    repo_etag,
)

DEFAULT_MAX_BYTES = 536870912
DEFAULT_INTERVAL_HOURS = 24


class AssetNotInRelease(Exception):
    pass


def is_duplicate(catalog: Catalog, source: GithubSource) -> bool:
    key = repository_key(source.owner, source.repository)
    return any(
        repository_key(item.owner, item.repository) == key
        and item.asset_name == source.asset_name
        for item in catalog.subscriptions
    )


def make_subscription(
    source: GithubSource,
    release: ReleaseInfo,
    subscription_id: str,
) -> Subscription:
    asset = find_apkg(release, source.asset_name)
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


def due_repositories(
    catalog: Catalog, now: datetime, interval_hours: int
) -> set[tuple[str, str]]:
    """Repositories whose newest check is older than the interval."""
    newest: dict[tuple[str, str], str | None] = {}
    for subscription in catalog.subscriptions:
        key = repository_key(subscription.owner, subscription.repository)
        checked = subscription.last_checked_at
        if key not in newest:
            newest[key] = checked
            continue
        current = newest[key]
        if current is None or checked is None:
            newest[key] = None
        elif checked > current:
            newest[key] = checked
    return {
        key
        for key, checked in newest.items()
        if check_is_due(checked, now, interval_hours)
    }


def pending_updates(catalog: Catalog) -> tuple[Subscription, ...]:
    """An update stays pending even when the last check failed."""
    return tuple(
        subscription
        for subscription in catalog.subscriptions
        if subscription.available_version
    )


def check_catalog(
    catalog: Catalog,
    fetch: Callable[[str, str, str | None], FetchResult],
    checked_at: str,
    only: set[tuple[str, str]] | None = None,
) -> Catalog:
    """Refresh each repository once. ``fetch`` may raise :class:`GithubError`."""
    seen: set[tuple[str, str]] = set()
    for subscription in catalog.subscriptions:
        key = repository_key(subscription.owner, subscription.repository)
        if key in seen:
            continue
        seen.add(key)
        if only is not None and key not in only:
            continue
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


def configured_interval_hours(config: object) -> int:
    if not isinstance(config, dict):
        return DEFAULT_INTERVAL_HOURS
    value = config.get("check_interval_hours", DEFAULT_INTERVAL_HOURS)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_INTERVAL_HOURS


def configured_max_bytes(config: object) -> int:
    if not isinstance(config, dict):
        return DEFAULT_MAX_BYTES
    value = config.get("max_download_bytes", DEFAULT_MAX_BYTES)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_MAX_BYTES
