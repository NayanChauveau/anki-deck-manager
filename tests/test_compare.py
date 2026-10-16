from datetime import datetime, timedelta, timezone

from src.domain import (
    ReleaseAsset,
    ReleaseInfo,
    Subscription,
    check_is_due,
    compare_subscription,
    status_of,
)


def _asset(name: str = "wset3-vin-fr.apkg", asset_id: int = 10) -> ReleaseAsset:
    return ReleaseAsset(
        name=name,
        label="WSET 3 — Vin (français)",
        asset_id=asset_id,
        size=100,
        state="uploaded",
        download_url=f"https://github.com/o/r/releases/download/v1.10.0/{name}",
    )


def _release(tag: str = "v1.10.0", assets: tuple[ReleaseAsset, ...] | None = None) -> ReleaseInfo:
    return ReleaseInfo(
        release_id=2,
        tag=tag,
        html_url=f"https://github.com/o/r/releases/tag/{tag}",
        assets=assets if assets is not None else (_asset(),),
    )


def _subscription(**overrides: object) -> Subscription:
    data: dict[str, object] = {
        "id": "sub-1",
        "owner": "NayanChauveau",
        "repository": "wine-theory-anki",
        "repo_url": "https://github.com/NayanChauveau/wine-theory-anki",
        "asset_name": "wset3-vin-fr.apkg",
        "display_name": "wset3-vin-fr",
        "installed_release_id": 1,
        "installed_version": "v1.9.0",
        "installed_asset_id": 9,
    }
    data.update(overrides)
    return Subscription(**data)  # type: ignore[arg-type]


def test_the_same_version_is_current() -> None:
    updated = compare_subscription(_subscription(installed_version="v1.10.0"), _release())
    assert status_of(updated) == "up_to_date"
    assert updated.available_version is None
    assert updated.display_name == "WSET 3 — Vin (français)"


def test_a_different_version_is_an_update() -> None:
    updated = compare_subscription(_subscription(), _release("v1.10.0"))
    assert status_of(updated) == "update_available"
    assert updated.installed_version == "v1.9.0"
    assert updated.available_version == "v1.10.0"


def test_versions_are_not_sorted_as_text() -> None:
    updated = compare_subscription(
        _subscription(installed_version="v1.10.0"),
        _release("v1.9.0"),
    )
    assert updated.available_version == "v1.9.0"
    assert updated.installed_version == "v1.10.0"


def test_missing_asset_is_not_replaced() -> None:
    updated = compare_subscription(
        _subscription(),
        _release(assets=(_asset("wset3-vin-en.apkg"),)),
    )
    assert status_of(updated) == "asset_missing"
    assert updated.installed_version == "v1.9.0"
    assert updated.available_version is None


def test_check_interval_skips_a_recent_check() -> None:
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=1)).isoformat()
    assert check_is_due(None, now, 24) is True
    assert check_is_due(recent, now, 24) is False
    assert check_is_due((now - timedelta(hours=24)).isoformat(), now, 24) is True
