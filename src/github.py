"""Read public GitHub release metadata.

Asset bytes are not downloaded here. The transport is injectable so tests
never call GitHub.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .domain import GithubSource, ReleaseAsset, ReleaseInfo

API_VERSION = "2026-03-10"
USER_AGENT = "DeckManager"
_API_HOST = "api.github.com"


class GithubError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class FetchResult:
    release: ReleaseInfo | None
    etag: str | None
    not_modified: bool


Transport = Callable[[str, dict[str, str]], HttpResponse]


def fetch_latest(
    owner: str,
    repository: str,
    *,
    etag: str | None = None,
    transport: Transport | None = None,
) -> FetchResult:
    """Read GitHub's stable latest release for one repository."""
    return _fetch(_release_api_url(owner, repository), etag=etag, transport=transport)


def fetch_tag(
    owner: str,
    repository: str,
    version: str,
    *,
    etag: str | None = None,
    transport: Transport | None = None,
) -> FetchResult:
    """Read the release published at one version tag."""
    return _fetch(
        _release_api_url(owner, repository, version),
        etag=etag,
        transport=transport,
    )


def fetch_release(
    source: GithubSource,
    *,
    latest: bool = False,
    etag: str | None = None,
    transport: Transport | None = None,
) -> FetchResult:
    """Read one release. ``latest`` follows GitHub's stable latest release."""
    if latest:
        return fetch_latest(source.owner, source.repository, etag=etag, transport=transport)
    return fetch_tag(
        source.owner,
        source.repository,
        source.version,
        etag=etag,
        transport=transport,
    )


def _fetch(
    url: str,
    *,
    etag: str | None,
    transport: Transport | None,
) -> FetchResult:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    if etag:
        headers["If-None-Match"] = etag
    response = (transport or urllib_transport)(url, headers)
    response_etag = response.headers.get("etag") or etag
    if response.status == 304:
        return FetchResult(release=None, etag=response_etag, not_modified=True)
    if response.status in {403, 429}:
        raise GithubError("rate_limited")
    if response.status == 404:
        raise GithubError("not_found")
    if response.status != 200:
        raise GithubError("http_error")
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GithubError("http_error") from exc
    return FetchResult(
        release=_parse_release(payload),
        etag=response_etag,
        not_modified=False,
    )


def urllib_transport(url: str, headers: dict[str, str]) -> HttpResponse:
    require_api_url(url)
    opener = build_opener(_ApiRedirectHandler)
    request = Request(url, headers=headers, method="GET")
    try:
        with opener.open(request, timeout=30) as response:
            return HttpResponse(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=response.read(),
            )
    except HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(),
        )
    except URLError as exc:
        raise GithubError("http_error") from exc


def require_api_url(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host != _API_HOST:
        raise GithubError("redirect_rejected")


class _ApiRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        require_api_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _release_api_url(owner: str, repository: str, version: str | None = None) -> str:
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}"
    if version is None:
        return f"{base}/releases/latest"
    return f"{base}/releases/tags/{quote(version, safe='')}"


def _parse_release(payload: object) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise GithubError("http_error")
    try:
        release_id = int(payload["id"])
        tag = str(payload["tag_name"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GithubError("http_error") from exc
    raw_assets = payload.get("assets") or []
    if not isinstance(raw_assets, list):
        raise GithubError("http_error")
    assets: list[ReleaseAsset] = []
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        try:
            name = str(item["name"])
            asset_id = int(item["id"])
            size = int(item.get("size") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        assets.append(
            ReleaseAsset(
                name=name,
                label=str(item.get("label") or ""),
                asset_id=asset_id,
                size=size,
                state=str(item.get("state") or ""),
                download_url=str(item.get("browser_download_url") or ""),
            )
        )
    return ReleaseInfo(
        release_id=release_id,
        tag=tag,
        html_url=str(payload.get("html_url") or ""),
        assets=tuple(assets),
    )
