"""Persist deck subscriptions as a versioned JSON object.

The object is what Anki's collection config will store. This module does not
import Anki.
"""

from __future__ import annotations

from dataclasses import asdict

from .domain import ReleaseInfo, Subscription, compare_subscription

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
            Subscription(**{**subscription.__dict__, "last_error": code}),
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


def _touch(subscription: Subscription, *, checked_at: str, etag: str | None) -> Subscription:
    return Subscription(
        **{
            **subscription.__dict__,
            "last_checked_at": checked_at,
            "etag": etag,
        }
    )


def _same_repo(subscription: Subscription, owner: str, repository: str) -> bool:
    return (
        subscription.owner.casefold() == owner.casefold()
        and subscription.repository.casefold() == repository.casefold()
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
