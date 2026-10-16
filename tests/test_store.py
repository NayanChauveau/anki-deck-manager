import pytest

from src.domain import ReleaseAsset, ReleaseInfo, Subscription, status_of
from src.store import (
    DuplicateSubscription,
    add_subscription,
    apply_error,
    apply_not_modified,
    apply_release,
    dump_catalog,
    empty_catalog,
    load_catalog,
    merge_checked,
    merge_installed,
    remove_subscription,
)


def _subscription(asset_name: str = "wset3-vin-fr.apkg", **overrides: object) -> Subscription:
    data: dict[str, object] = {
        "id": asset_name,
        "owner": "NayanChauveau",
        "repository": "wine-theory-anki",
        "repo_url": "https://github.com/NayanChauveau/wine-theory-anki",
        "asset_name": asset_name,
        "display_name": asset_name,
        "installed_release_id": 1,
        "installed_version": "v1.2.0",
        "installed_asset_id": 10,
    }
    data.update(overrides)
    return Subscription(**data)  # type: ignore[arg-type]


def _release() -> ReleaseInfo:
    return ReleaseInfo(
        release_id=2,
        tag="v1.3.0",
        html_url="https://github.com/NayanChauveau/wine-theory-anki/releases/tag/v1.3.0",
        assets=(
            ReleaseAsset(
                name="wset3-vin-fr.apkg",
                label="FR",
                asset_id=11,
                size=10,
                state="uploaded",
                download_url="https://github.com/o/r/releases/download/v1.3.0/wset3-vin-fr.apkg",
            ),
        ),
    )


def test_duplicate_asset_is_rejected_without_caring_about_owner_case() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    other_case = _subscription(id="other", owner="nayanchauveau")
    with pytest.raises(DuplicateSubscription):
        add_subscription(catalog, other_case)


def test_two_assets_from_one_repository_are_independent() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    catalog = add_subscription(catalog, _subscription("wset3-vin-en.apkg", id="en"))
    catalog = apply_release(
        catalog,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        release=_release(),
        checked_at="2026-10-16T00:00:00+00:00",
        etag='"rel"',
    )
    french, english = catalog.subscriptions
    assert status_of(french) == "update_available"
    assert french.available_version == "v1.3.0"
    assert status_of(english) == "asset_missing"
    assert french.etag == '"rel"'
    assert english.etag == '"rel"'


def test_not_modified_only_refreshes_the_check_time() -> None:
    catalog = add_subscription(
        empty_catalog(),
        _subscription(available_version="v9.9.9", available_release_id=9, etag='"old"'),
    )
    catalog = apply_not_modified(
        catalog,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        checked_at="2026-10-16T01:00:00+00:00",
        etag='"old"',
    )
    subscription = catalog.subscriptions[0]
    assert subscription.available_version == "v9.9.9"
    assert subscription.available_release_id == 9
    assert subscription.etag == '"old"'
    assert subscription.last_checked_at == "2026-10-16T01:00:00+00:00"
    assert subscription.installed_version == "v1.2.0"


def test_network_error_keeps_the_installed_version() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    catalog = apply_error(
        catalog,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        code="rate_limited",
        checked_at="2026-10-16T02:00:00+00:00",
    )
    subscription = catalog.subscriptions[0]
    assert status_of(subscription) == "error"
    assert subscription.installed_version == "v1.2.0"


def test_catalog_roundtrip_and_removal() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    restored = load_catalog(dump_catalog(catalog))
    assert restored.subscriptions == catalog.subscriptions
    assert remove_subscription(restored, "wset3-vin-fr.apkg").subscriptions == ()
    assert load_catalog(None).subscriptions == ()


def test_unknown_schema_is_rejected() -> None:
    with pytest.raises(ValueError):
        load_catalog({"version": 2, "subscriptions": []})


def test_a_finished_check_keeps_a_deck_added_meanwhile() -> None:
    baseline = add_subscription(empty_catalog(), _subscription())
    live = add_subscription(baseline, _subscription("wset3-vin-en.apkg", id="en"))
    checked = apply_release(
        baseline,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        release=_release(),
        checked_at="2026-10-16T03:00:00+00:00",
        etag='"new"',
    )
    merged = merge_checked(live, {item.id for item in baseline.subscriptions}, checked)
    french, english = merged.subscriptions
    assert french.available_version == "v1.3.0"
    assert french.etag == '"new"'
    assert english.id == "en"
    assert english.available_version is None


def test_a_finished_check_does_not_reopen_an_installed_version() -> None:
    baseline = add_subscription(empty_catalog(), _subscription())
    checked = apply_release(
        baseline,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        release=_release(),
        checked_at="2026-10-16T03:00:00+00:00",
        etag='"new"',
    )
    live = add_subscription(
        empty_catalog(),
        _subscription(installed_version="v1.3.0", installed_release_id=2),
    )
    merged = merge_checked(live, {"wset3-vin-fr.apkg"}, checked)
    assert merged.subscriptions[0].available_version is None
    assert merged.subscriptions[0].installed_version == "v1.3.0"


def test_a_finished_install_does_not_drop_or_restore_rows() -> None:
    baseline = add_subscription(empty_catalog(), _subscription())
    added = add_subscription(baseline, _subscription("wset3-vin-en.apkg", id="en"))
    removed = remove_subscription(baseline, "wset3-vin-fr.apkg")
    installed = apply_release(
        baseline,
        owner="NayanChauveau",
        repository="wine-theory-anki",
        release=_release(),
        checked_at="2026-10-16T03:00:00+00:00",
        etag='"new"',
    )
    kept = merge_installed(added, {"wset3-vin-fr.apkg"}, installed)
    assert [item.id for item in kept.subscriptions] == ["wset3-vin-fr.apkg", "en"]
    assert kept.subscriptions[0].available_version == "v1.3.0"
    assert merge_installed(removed, {"wset3-vin-fr.apkg"}, installed).subscriptions == ()
