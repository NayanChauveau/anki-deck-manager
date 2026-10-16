"""Download one release asset to a temporary file.

No Anki imports. Redirects stay on the GitHub hosts that actually serve a
release asset. The announced size and the bytes received are both capped.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

USER_AGENT = "DeckManager"
_CHUNK_BYTES = 64 * 1024
_MAX_REDIRECTS = 5
_REDIRECTS = {301, 302, 303, 307, 308}

ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "api.github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }
)


class DownloadError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DownloadResponse:
    def __init__(
        self,
        status: int,
        headers: dict[str, str],
        chunks: Iterable[bytes] = (),
    ) -> None:
        self.status = status
        self.headers = {key.lower(): value for key, value in headers.items()}
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        yield from self._chunks

    def close(self) -> None:
        return None


OpenUrl = Callable[[str], DownloadResponse]


def require_download_url(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_DOWNLOAD_HOSTS:
        raise DownloadError("redirect_rejected")


def download_asset(
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    announced_size: int,
    open_url: OpenUrl,
    cancelled: Callable[[], bool] | None = None,
) -> None:
    """Write ``url`` to ``destination`` or raise :class:`DownloadError`."""
    if announced_size > max_bytes:
        raise DownloadError("too_large")
    should_stop = cancelled or (lambda: False)
    current = url
    for _hop in range(_MAX_REDIRECTS):
        require_download_url(current)
        if should_stop():
            raise DownloadError("cancelled")
        response = open_url(current)
        try:
            if response.status in _REDIRECTS:
                location = response.headers.get("location")
                if not location:
                    raise DownloadError("redirect_rejected")
                current = _join(current, location)
                continue
            if response.status != 200:
                raise DownloadError("http_error")
            length = response.headers.get("content-length")
            if length is not None and length.isdigit() and int(length) > max_bytes:
                raise DownloadError("too_large")
            _write(destination, response, max_bytes, should_stop)
            return
        finally:
            response.close()
    raise DownloadError("redirect_rejected")


def urllib_open(url: str) -> DownloadResponse:
    require_download_url(url)
    opener = build_opener(_StopRedirect)
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        response = opener.open(request, timeout=60)
    except _Redirect as redirect:
        return DownloadResponse(redirect.status, {"location": redirect.target})
    except HTTPError as exc:
        return DownloadResponse(
            exc.code,
            {key.lower(): value for key, value in exc.headers.items()},
        )
    except URLError as exc:
        raise DownloadError("http_error") from exc
    return _UrllibResponse(response)


class _Redirect(Exception):
    def __init__(self, status: int, target: str) -> None:
        super().__init__(target)
        self.status = status
        self.target = target


class _StopRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise _Redirect(code, newurl)


class _UrllibResponse(DownloadResponse):
    def __init__(self, response: object) -> None:
        headers = {key.lower(): value for key, value in response.headers.items()}  # type: ignore[attr-defined]
        super().__init__(response.status, headers)  # type: ignore[attr-defined]
        self._response = response

    def __iter__(self) -> Iterator[bytes]:
        while True:
            block = self._response.read(_CHUNK_BYTES)  # type: ignore[attr-defined]
            if not block:
                return
            yield block

    def close(self) -> None:
        self._response.close()  # type: ignore[attr-defined]


def _join(base: str, location: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base, location)


def _write(
    destination: Path,
    chunks: Iterable[bytes],
    max_bytes: int,
    cancelled: Callable[[], bool],
) -> None:
    total = 0
    try:
        with destination.open("wb") as handle:
            for chunk in chunks:
                if cancelled():
                    raise DownloadError("cancelled")
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadError("too_large")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
