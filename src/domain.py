"""GitHub deck identity, URL parsing, and update comparison.

No Anki imports. A deck is the file name inside a versioned release URL:

    https://github.com/{owner}/{repo}/releases/download/{version}/{file}.apkg

The version is ``vX.Y.Z`` or ``X.Y.Z``. A different version on GitHub's latest
stable release is an update. The same version is current, even if the file
bytes changed: publishing a change means cutting a new version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

_OWNER = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"
_REPO = r"^[A-Za-z0-9._-]{1,100}$"
_VERSION = r"^v?\d+\.\d+\.\d+$"


class UrlError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GithubSource:
    owner: str
    repository: str
    repo_url: str
    version: str
    asset_name: str


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    label: str
    asset_id: int
    size: int
    state: str
    download_url: str

    @property
    def display_name(self) -> str:
        label = self.label.strip()
        if label:
            return label
        stem = self.name.rsplit(".", 1)[0]
        return stem or self.name


@dataclass(frozen=True)
class ReleaseInfo:
    release_id: int
    tag: str
    html_url: str
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True)
class Subscription:
    id: str
    owner: str
    repository: str
    repo_url: str
    asset_name: str
    display_name: str
    installed_release_id: int | None = None
    installed_version: str | None = None
    installed_asset_id: int | None = None
    available_release_id: int | None = None
    available_version: str | None = None
    available_asset_id: int | None = None
    etag: str | None = None
    last_checked_at: str | None = None
    last_installed_at: str | None = None
    last_error: str | None = None
    enabled: bool = True


def parse_github_url(text: str) -> GithubSource:
    """Accept only ``.../releases/download/{version}/{file}.apkg``."""
    raw = text.strip()
    if not raw:
        raise UrlError("empty")
    parts = urlsplit(raw)
    if parts.scheme.lower() != "https":
        raise UrlError("https_required")
    if parts.username or parts.password:
        raise UrlError("credentials")
    host = (parts.hostname or "").lower()
    if host == "www.github.com":
        host = "github.com"
    if host != "github.com":
        raise UrlError("host")
    if parts.query:
        raise UrlError("query")

    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if len(segments) != 6 or segments[2:4] != ["releases", "download"]:
        raise UrlError("path")
    owner, repository, version, asset_name = (
        segments[0],
        segments[1],
        segments[4],
        segments[5],
    )
    if repository.endswith(".git"):
        repository = repository[: -len(".git")]
    _require_name(owner, _OWNER, "owner")
    _require_name(repository, _REPO, "repository")
    if not re.fullmatch(_VERSION, version):
        raise UrlError("version")
    if not asset_name.lower().endswith(".apkg"):
        raise UrlError("asset")

    return GithubSource(
        owner=owner,
        repository=repository,
        repo_url=f"https://github.com/{owner}/{repository}",
        version=version,
        asset_name=asset_name,
    )


def apkg_assets(release: ReleaseInfo) -> tuple[ReleaseAsset, ...]:
    return tuple(
        asset
        for asset in release.assets
        if asset.state == "uploaded" and asset.name.lower().endswith(".apkg")
    )


def status_of(subscription: Subscription) -> str:
    if subscription.last_error == "asset_missing":
        return "asset_missing"
    if subscription.last_error:
        return "error"
    if subscription.available_version:
        return "update_available"
    if subscription.installed_version:
        return "up_to_date"
    return "unknown"


def compare_subscription(subscription: Subscription, release: ReleaseInfo) -> Subscription:
    """Offer the latest release when its version differs. Do not sort versions."""
    match = next(
        (asset for asset in apkg_assets(release) if asset.name == subscription.asset_name),
        None,
    )
    if match is None:
        return _replace(
            subscription,
            available_release_id=None,
            available_version=None,
            available_asset_id=None,
            last_error="asset_missing",
        )
    if release.tag == subscription.installed_version:
        return _replace(
            subscription,
            display_name=match.display_name,
            installed_release_id=release.release_id,
            installed_asset_id=match.asset_id,
            available_release_id=None,
            available_version=None,
            available_asset_id=None,
            last_error=None,
        )
    return _replace(
        subscription,
        available_release_id=release.release_id,
        available_version=release.tag,
        available_asset_id=match.asset_id,
        last_error=None,
    )


def check_is_due(
    last_checked_at: str | None, now: datetime, interval_hours: int
) -> bool:
    if last_checked_at is None:
        return True
    checked = datetime.fromisoformat(last_checked_at)
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    return now - checked >= timedelta(hours=interval_hours)


def _require_name(value: str, pattern: str, code: str) -> None:
    if not re.fullmatch(pattern, value) or value in {".", ".."}:
        raise UrlError(code)


def _replace(subscription: Subscription, **changes: object) -> Subscription:
    data = subscription.__dict__.copy()
    data.update(changes)
    return Subscription(**data)
