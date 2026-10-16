import json

import pytest

from src.domain import GithubSource, apkg_assets
from src.github import (
    API_VERSION,
    USER_AGENT,
    FetchResult,
    GithubError,
    HttpResponse,
    fetch_release,
    require_api_url,
)


def _source() -> GithubSource:
    return GithubSource(
        owner="NayanChauveau",
        repository="wine-theory-anki",
        repo_url="https://github.com/NayanChauveau/wine-theory-anki",
        version="v1.2.0",
        asset_name="wset3-vin-fr.apkg",
    )


def _payload(tag: str = "v1.2.0") -> dict[str, object]:
    return {
        "id": 399795516,
        "tag_name": tag,
        "html_url": f"https://github.com/NayanChauveau/wine-theory-anki/releases/tag/{tag}",
        "assets": [
            {
                "name": "wset3-vin-fr.apkg",
                "label": "",
                "id": 20,
                "size": 5304538,
                "state": "uploaded",
                "browser_download_url": f"https://github.com/o/r/releases/download/{tag}/wset3-vin-fr.apkg",
            },
            {
                "name": "notes.zip",
                "label": "",
                "id": 21,
                "size": 10,
                "state": "uploaded",
                "browser_download_url": "https://example.invalid/notes.zip",
            },
            {
                "name": "draft.apkg",
                "label": "Draft",
                "id": 22,
                "size": 10,
                "state": "open",
                "browser_download_url": "https://example.invalid/draft.apkg",
            },
        ],
    }


def test_latest_sends_the_current_github_headers_and_keeps_apkg_assets() -> None:
    seen: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str]) -> HttpResponse:
        seen["url"] = url
        seen["headers"] = headers
        return HttpResponse(200, {"etag": '"v1"'}, json.dumps(_payload("v1.3.0")).encode())

    result = fetch_release(_source(), latest=True, etag='"old"', transport=transport)
    assert seen["url"] == (
        "https://api.github.com/repos/NayanChauveau/wine-theory-anki/releases/latest"
    )
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == API_VERSION
    assert headers["User-Agent"] == USER_AGENT
    assert headers["If-None-Match"] == '"old"'
    assert result.etag == '"v1"'
    assert result.release is not None
    assert result.release.tag == "v1.3.0"
    assert [asset.name for asset in apkg_assets(result.release)] == ["wset3-vin-fr.apkg"]


def test_not_modified_keeps_the_etag_and_skips_the_body() -> None:
    def transport(url: str, headers: dict[str, str]) -> HttpResponse:
        return HttpResponse(304, {"etag": '"same"'}, b"")

    result = fetch_release(_source(), latest=True, etag='"same"', transport=transport)
    assert result == FetchResult(release=None, etag='"same"', not_modified=True)


def test_a_pasted_version_requests_that_version() -> None:
    seen: dict[str, str] = {}

    def transport(url: str, headers: dict[str, str]) -> HttpResponse:
        seen["url"] = url
        return HttpResponse(200, {}, json.dumps(_payload()).encode())

    fetch_release(_source(), transport=transport)
    assert seen["url"].endswith("/releases/tags/v1.2.0")


@pytest.mark.parametrize(
    ("status", "code"),
    [(403, "rate_limited"), (429, "rate_limited"), (404, "not_found"), (500, "http_error")],
)
def test_http_errors(status: int, code: str) -> None:
    def transport(url: str, headers: dict[str, str]) -> HttpResponse:
        return HttpResponse(status, {}, b"")

    with pytest.raises(GithubError) as caught:
        fetch_release(_source(), transport=transport)
    assert caught.value.code == code


def test_redirects_leave_the_github_api() -> None:
    from src.github import _ApiRedirectHandler

    with pytest.raises(GithubError) as caught:
        require_api_url("https://example.invalid/steal")
    assert caught.value.code == "redirect_rejected"
    require_api_url("https://api.github.com/repos/o/r/releases/latest")
    with pytest.raises(GithubError) as caught:
        _ApiRedirectHandler().redirect_request(
            None,
            None,
            302,
            "Found",
            {},
            "https://evil.example/steal",
        )
    assert caught.value.code == "redirect_rejected"
