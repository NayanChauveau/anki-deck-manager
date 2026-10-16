from pathlib import Path

import pytest

from src.download import (
    DownloadError,
    DownloadResponse,
    discard_package,
    download_asset,
    require_download_url,
    temporary_package,
)

_URL = "https://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/deck.apkg"


def test_announced_size_stops_before_any_request(tmp_path: Path) -> None:
    def open_url(url: str) -> DownloadResponse:
        raise AssertionError(url)

    with pytest.raises(DownloadError) as caught:
        download_asset(
            _URL,
            tmp_path / "deck.apkg",
            max_bytes=8,
            announced_size=9,
            open_url=open_url,
        )
    assert caught.value.code == "too_large"


def test_content_length_over_the_cap_writes_nothing(tmp_path: Path) -> None:
    destination = tmp_path / "deck.apkg"

    def body():  # type: ignore[no-untyped-def]
        raise AssertionError("body")
        yield b""

    def open_url(url: str) -> DownloadResponse:
        return DownloadResponse(200, {"content-length": "99"}, body())

    with pytest.raises(DownloadError) as caught:
        download_asset(
            _URL,
            destination,
            max_bytes=10,
            announced_size=4,
            open_url=open_url,
        )
    assert caught.value.code == "too_large"
    assert not destination.exists()


def test_a_stream_over_the_cap_deletes_the_partial_file(tmp_path: Path) -> None:
    destination = tmp_path / "deck.apkg"

    def open_url(url: str) -> DownloadResponse:
        return DownloadResponse(200, {}, (b"abcd", b"efgh"))

    with pytest.raises(DownloadError) as caught:
        download_asset(
            _URL,
            destination,
            max_bytes=6,
            announced_size=4,
            open_url=open_url,
        )
    assert caught.value.code == "too_large"
    assert not destination.exists()


def test_redirects_stay_on_release_hosts(tmp_path: Path) -> None:
    destination = tmp_path / "deck.apkg"
    seen: list[str] = []

    def open_url(url: str) -> DownloadResponse:
        seen.append(url)
        if url.startswith("https://github.com/"):
            return DownloadResponse(
                302,
                {"location": "https://objects.githubusercontent.com/package"},
            )
        return DownloadResponse(200, {"content-length": "4"}, (b"apkg",))

    download_asset(
        _URL,
        destination,
        max_bytes=10,
        announced_size=4,
        open_url=open_url,
    )
    assert destination.read_bytes() == b"apkg"
    assert seen[1] == "https://objects.githubusercontent.com/package"


def test_a_redirect_to_another_host_is_rejected(tmp_path: Path) -> None:
    seen: list[str] = []

    def open_url(url: str) -> DownloadResponse:
        seen.append(url)
        return DownloadResponse(302, {"location": "https://evil.example/deck.apkg"})

    with pytest.raises(DownloadError) as caught:
        download_asset(
            _URL,
            tmp_path / "deck.apkg",
            max_bytes=10,
            announced_size=4,
            open_url=open_url,
        )
    assert caught.value.code == "redirect_rejected"
    assert seen == [_URL]


def test_cancel_between_chunks_deletes_the_file(tmp_path: Path) -> None:
    destination = tmp_path / "deck.apkg"
    calls = {"count": 0}

    def cancelled() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    def open_url(url: str) -> DownloadResponse:
        return DownloadResponse(200, {}, (b"aa", b"bb"))

    with pytest.raises(DownloadError) as caught:
        download_asset(
            _URL,
            destination,
            max_bytes=10,
            announced_size=4,
            open_url=open_url,
            cancelled=cancelled,
        )
    assert caught.value.code == "cancelled"
    assert not destination.exists()


def test_the_temp_file_uses_the_asset_name() -> None:
    path = temporary_package("folder/wset3-test-fr.apkg")
    try:
        assert path.name == "wset3-test-fr.apkg"
        assert path.parent.name.startswith("deck-manager-")
    finally:
        discard_package(path)
    assert not path.exists()
    assert not path.parent.exists()
    nested = temporary_package("../../wset3-test-fr.apkg")
    try:
        assert nested.name == "wset3-test-fr.apkg"
        assert ".." not in nested.parts
    finally:
        discard_package(nested)
    fallback = temporary_package("notes.txt")
    try:
        assert fallback.name == "deck.apkg"
    finally:
        discard_package(fallback)


def test_download_hosts() -> None:
    require_download_url("https://release-assets.githubusercontent.com/file")
    require_download_url("https://api.github.com/repos/o/r/releases/assets/1")
    with pytest.raises(DownloadError) as caught:
        require_download_url("http://github.com/o/r/deck.apkg")
    assert caught.value.code == "redirect_rejected"
    with pytest.raises(DownloadError) as caught:
        require_download_url("https://codeload.github.com/o/r/legacy.tar.gz")
    assert caught.value.code == "redirect_rejected"
    with pytest.raises(DownloadError) as caught:
        require_download_url("https://evil.objects.githubusercontent.com/package")
    assert caught.value.code == "redirect_rejected"
    with pytest.raises(DownloadError) as caught:
        require_download_url("http://objects.githubusercontent.com/package")
    assert caught.value.code == "redirect_rejected"
