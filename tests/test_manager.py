from src.domain import GithubSource, ReleaseAsset, ReleaseInfo, Subscription
from src.github import FetchResult, GithubError
from src.manager import (
    AssetNotInRelease,
    check_catalog,
    configured_max_bytes,
    is_duplicate,
    make_subscription,
)
from src.store import add_subscription, empty_catalog
from src import strings


def _source() -> GithubSource:
    return GithubSource(
        owner="NayanChauveau",
        repository="wine-theory-anki",
        repo_url="https://github.com/NayanChauveau/wine-theory-anki",
        version="v1.2.0",
        asset_name="wset3-vin-fr.apkg",
    )


def _release(tag: str = "v1.2.0", name: str = "wset3-vin-fr.apkg") -> ReleaseInfo:
    return ReleaseInfo(
        release_id=2,
        tag=tag,
        html_url=f"https://github.com/o/r/releases/tag/{tag}",
        assets=(
            ReleaseAsset(
                name=name,
                label="WSET 3 — Vin (français)",
                asset_id=11,
                size=4,
                state="uploaded",
                download_url=f"https://github.com/o/r/releases/download/{tag}/{name}",
            ),
            ReleaseAsset(
                name="wset3-vin-en.apkg",
                label="EN",
                asset_id=12,
                size=4,
                state="uploaded",
                download_url=f"https://github.com/o/r/releases/download/{tag}/wset3-vin-en.apkg",
            ),
        ),
    )


def _subscription(subscription_id: str, asset_name: str, **overrides: object) -> Subscription:
    data: dict[str, object] = {
        "id": subscription_id,
        "owner": "NayanChauveau",
        "repository": "wine-theory-anki",
        "repo_url": "https://github.com/NayanChauveau/wine-theory-anki",
        "asset_name": asset_name,
        "display_name": asset_name,
        "installed_version": "v1.0.0",
    }
    data.update(overrides)
    return Subscription(**data)  # type: ignore[arg-type]


def test_a_pasted_release_becomes_one_subscription() -> None:
    subscription = make_subscription(_source(), _release(), "abc")
    assert subscription.id == "abc"
    assert subscription.display_name == "WSET 3 — Vin (français)"
    assert subscription.installed_version is None
    assert is_duplicate(add_subscription(empty_catalog(), subscription), _source())


def test_a_missing_file_is_not_added() -> None:
    try:
        make_subscription(_source(), _release(name="other.apkg"), "abc")
    except AssetNotInRelease:
        return
    raise AssertionError("expected AssetNotInRelease")


def test_one_check_covers_both_files_of_a_repository() -> None:
    catalog = add_subscription(empty_catalog(), _subscription("fr", "wset3-vin-fr.apkg"))
    catalog = add_subscription(catalog, _subscription("en", "wset3-vin-en.apkg"))
    calls: list[str] = []

    def fetch(owner: str, repository: str, etag: str | None) -> FetchResult:
        calls.append(f"{owner}/{repository}:{etag}")
        return FetchResult(release=_release("v1.3.0"), etag='"new"', not_modified=False)

    updated = check_catalog(catalog, fetch, "2026-10-16T00:00:00+00:00")
    assert calls == ["NayanChauveau/wine-theory-anki:None"]
    assert [item.available_version for item in updated.subscriptions] == ["v1.3.0", "v1.3.0"]
    assert updated.subscriptions[0].installed_version == "v1.0.0"


def test_a_not_modified_response_keeps_the_available_version() -> None:
    catalog = add_subscription(
        empty_catalog(),
        _subscription("fr", "wset3-vin-fr.apkg", available_version="v9.0.0", etag='"old"'),
    )

    def fetch(owner: str, repository: str, etag: str | None) -> FetchResult:
        assert etag == '"old"'
        return FetchResult(release=None, etag='"old"', not_modified=True)

    updated = check_catalog(catalog, fetch, "t")
    assert updated.subscriptions[0].available_version == "v9.0.0"
    assert updated.subscriptions[0].last_checked_at == "t"


def test_a_rate_limit_is_shown_as_an_error() -> None:
    catalog = add_subscription(empty_catalog(), _subscription("fr", "wset3-vin-fr.apkg"))

    def fetch(owner: str, repository: str, etag: str | None) -> FetchResult:
        raise GithubError("rate_limited")

    updated = check_catalog(catalog, fetch, "t")
    subscription = updated.subscriptions[0]
    assert subscription.installed_version == "v1.0.0"
    assert strings.status_text(subscription) == "Quota GitHub atteint"


def test_version_and_removal_copy() -> None:
    subscription = _subscription(
        "fr",
        "wset3-vin-fr.apkg",
        installed_version="v1.2.0",
        available_version="v1.3.0",
    )
    assert strings.version_text(subscription) == "v1.2.0 → v1.3.0"
    assert strings.status_text(subscription) == "Mise à jour disponible"
    assert "Le deck reste dans Anki" in strings.removal_message(["WSET"])
    assert "Les decks restent dans Anki" in strings.removal_message(["A", "B"])
    assert "vX.Y.Z" in strings.url_error_text("path")


def test_download_cap_comes_from_addon_config() -> None:
    assert configured_max_bytes(None) == 536870912
    assert configured_max_bytes({"max_download_bytes": 10}) == 10
    assert configured_max_bytes({"max_download_bytes": 0}) == 536870912
