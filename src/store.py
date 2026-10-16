"""Persist deck subscriptions as a versioned JSON object.

The object is what Anki's collection config will store. This module does not
import Anki.
"""

from __future__ import annotations

from dataclasses import asdict, replace

from .domain import ReleaseInfo, Subscription, compare_subscription, repository_key

CONFIG_KEY = "deck_manager"
SCHEMA_VERSION = 1


class DuplicateSubscription(ValueError):
    pass


class Catalog:
    def __init__(self, subscriptions: tuple[Subscription, ...] = ()) -> None:
        self.subscriptions = subscriptions


def empty_catalog() -> Catalog:
    return Catalog()


def dump_catalog(catalog: Catalog) -> dict[str, object]:
    return {
        "version": SCHEMA_VERSION,
        "subscriptions": [asdict(item) for item in catalog.subscriptions],
    }


def load_catalog(payload: object) -> Catalog:
    if payload is None:
        return empty_catalog()
    if not isinstance(payload, dict):
        raise ValueError("catalog")
    if payload.get("version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("catalog_version")
    raw_items = payload.get("subscriptions", [])
    if not isinstance(raw_items, list):
        raise ValueError("catalog")
    return Catalog(tuple(_load_subscription(item) for item in raw_items))


def add_subscription(catalog: Catalog, subscription: Subscription) -> Catalog:
    if any(_same_asset(existing, subscription) for existing in catalog.subscriptions):
        raise DuplicateSubscription(subscription.asset_name)
    return Catalog(catalog.subscriptions + (subscription,))


def remove_subscription(catalog: Catalog, subscription_id: str) -> Catalog:
    return Catalog(
        tuple(item for item in catalog.subscriptions if item.id != subscription_id)
    )


def repo_etag(catalog: Catalog, owner: str, repository: str) -> str | None:
    for subscription in catalog.subscriptions:
        if _same_repo(subscription, owner, repository) and subscription.etag:
            return subscription.etag
    return None


def apply_release(
    catalog: Catalog,
    *,
    owner: str,
    repository: str,
    release: ReleaseInfo,
    checked_at: str,
    etag: str | None,
) -> Catalog:
    return _map_repo(
        catalog,
        owner,
        repository,
        lambda subscription: _touch(
            compare_subscription(subscription, release),
            checked_at=checked_at,
            etag=etag if etag is not None else subscription.etag,
        ),
    )


def apply_not_modified(
    catalog: Catalog,
    *,
    owner: str,
    repository: str,
    checked_at: str,
    etag: str | None,
) -> Catalog:
    return _map_repo(
        catalog,
        owner,
        repository,
        lambda subscription: _touch(
            subscription,
            checked_at=checked_at,
            etag=etag if etag is not None else subscription.etag,
        ),
    )


def apply_error(
    catalog: Catalog,
    *,
    owner: str,
    repository: str,
    code: str,
    checked_at: str,
) -> Catalog:
    return _map_repo(
        catalog,
        owner,
        repository,
        lambda subscription: _touch(
            replace(subscription, last_error=code),
            checked_at=checked_at,
            etag=subscription.etag,
        ),
    )


def _map_repo(catalog: Catalog, owner: str, repository: str, change) -> Catalog:  # type: ignore[no-untyped-def]
    updated = [
        change(subscription) if _same_repo(subscription, owner, repository) else subscription
        for subscription in catalog.subscriptions
    ]
    return Catalog(tuple(updated))


def merge_checked(live: Catalog, baseline_ids: set[str], checked: Catalog) -> Catalog:
    """Copy a finished check onto rows that still exist, without touching installs."""
    fresh = {item.id: item for item in checked.subscriptions}
    rows: list[Subscription] = []
    for item in live.subscriptions:
        update = fresh.get(item.id)
        if item.id not in baseline_ids or update is None:
            rows.append(item)
            continue
        if item.installed_version and item.installed_version == update.available_version:
            update = replace(
                update,
                available_release_id=None,
                available_version=None,
                available_asset_id=None,
                last_error=None,
            )
        rows.append(
            replace(
                item,
                display_name=update.display_name,
                available_release_id=update.available_release_id,
                available_version=update.available_version,
                available_asset_id=update.available_asset_id,
                last_error=update.last_error,
                last_checked_at=update.last_checked_at,
                etag=update.etag,
            )
        )
    return Catalog(tuple(rows))


def merge_installed(live: Catalog, baseline_ids: set[str], installed: Catalog) -> Catalog:
    """Keep decks added or removed while an install was running."""
    fresh = {item.id: item for item in installed.subscriptions}
    return Catalog(
        tuple(
            fresh[item.id] if item.id in baseline_ids and item.id in fresh else item
            for item in live.subscriptions
        )
    )


def _touch(subscription: Subscription, *, checked_at: str, etag: str | None) -> Subscription:
    return replace(subscription, last_checked_at=checked_at, etag=etag)


def _same_repo(subscription: Subscription, owner: str, repository: str) -> bool:
    return repository_key(subscription.owner, subscription.repository) == repository_key(
        owner, repository
    )


def _same_asset(left: Subscription, right: Subscription) -> bool:
    return _same_repo(left, right.owner, right.repository) and left.asset_name == right.asset_name


def _load_subscription(payload: object) -> Subscription:
    if not isinstance(payload, dict):
        raise ValueError("subscription")
    required = ("id", "owner", "repository", "repo_url", "asset_name", "display_name")
    if any(key not in payload for key in required):
        raise ValueError("subscription")
    known = set(Subscription.__dataclass_fields__)
    extra = set(payload) - known
    if extra:
        raise ValueError("subscription")
    values = {name: payload.get(name, field.default) for name, field in Subscription.__dataclass_fields__.items()}
    try:
        return Subscription(**values)
    except TypeError as exc:
        raise ValueError("subscription") from exc
