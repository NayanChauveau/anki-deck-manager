from pathlib import Path

from src.domain import ReleaseAsset, ReleaseInfo, Subscription, status_of
from src.install import Prepared, run_install_queue
from src.store import add_subscription, empty_catalog


def _subscription(
    subscription_id: str = "fr",
    asset_name: str = "wset3-vin-fr.apkg",
    **overrides: object,
) -> Subscription:
    data: dict[str, object] = {
        "id": subscription_id,
        "owner": "NayanChauveau",
        "repository": "wine-theory-anki",
        "repo_url": "https://github.com/NayanChauveau/wine-theory-anki",
        "asset_name": asset_name,
        "display_name": asset_name,
        "installed_release_id": 1,
        "installed_version": "v1.2.0",
        "installed_asset_id": 10,
        "available_version": "v1.2.0",
    }
    data.update(overrides)
    return Subscription(**data)  # type: ignore[arg-type]


def _release(tag: str = "v1.3.0") -> ReleaseInfo:
    def asset(name: str, asset_id: int) -> ReleaseAsset:
        return ReleaseAsset(
            name=name,
            label=name,
            asset_id=asset_id,
            size=4,
            state="uploaded",
            download_url=f"https://github.com/o/r/releases/download/{tag}/{name}",
        )

    return ReleaseInfo(
        release_id=2,
        tag=tag,
        html_url=f"https://github.com/o/r/releases/tag/{tag}",
        assets=(asset("wset3-vin-fr.apkg", 11), asset("wset3-vin-en.apkg", 12)),
    )


def test_a_cancelled_import_keeps_the_installed_version(tmp_path: Path) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"apkg")
    catalog = add_subscription(empty_catalog(), _subscription())
    seen: dict[str, object] = {}

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        done(Prepared(release=_release("v1.3.0"), path=package))

    def import_file(path: Path, done) -> None:  # type: ignore[no-untyped-def]
        assert path.exists()
        done(False)

    def finished(result) -> None:  # type: ignore[no-untyped-def]
        seen["catalog"] = result

    run_install_queue(
        catalog,
        ["fr"],
        prepare=prepare,
        import_file=import_file,
        checked_at=lambda: "2026-10-16T00:00:00+00:00",
        on_finished=finished,
    )
    saved = seen["catalog"].subscriptions[0]  # type: ignore[attr-defined]
    assert saved.installed_version == "v1.2.0"
    assert saved.available_version == "v1.3.0"
    assert not package.exists()


def test_a_confirmed_import_records_the_reread_version(tmp_path: Path) -> None:
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"apkg")
    catalog = add_subscription(
        empty_catalog(),
        _subscription(available_version="v1.2.1"),
    )
    seen: dict[str, object] = {}

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        done(Prepared(release=_release("v1.3.0"), path=package))

    run_install_queue(
        catalog,
        ["fr"],
        prepare=prepare,
        import_file=lambda path, done: done(True),
        checked_at=lambda: "2026-10-16T03:00:00+00:00",
        on_finished=lambda result: seen.update(catalog=result),
    )
    saved = seen["catalog"].subscriptions[0]  # type: ignore[attr-defined]
    assert saved.installed_version == "v1.3.0"
    assert saved.available_version is None
    assert saved.last_installed_at == "2026-10-16T03:00:00+00:00"
    assert not package.exists()


def test_the_next_file_waits_until_the_dialog_closes(tmp_path: Path) -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    catalog = add_subscription(
        catalog,
        _subscription("en", "wset3-vin-en.apkg"),
    )
    started: list[str] = []
    pending: list[object] = []

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        package = tmp_path / f"{subscription.id}.apkg"
        package.write_bytes(b"apkg")
        done(Prepared(release=_release(), path=package))

    def import_file(path: Path, done) -> None:  # type: ignore[no-untyped-def]
        started.append(path.name)
        pending.append(done)

    run_install_queue(
        catalog,
        ["fr", "en"],
        prepare=prepare,
        import_file=import_file,
        checked_at=lambda: "t",
        on_finished=lambda result: started.append("finished"),
    )
    assert started == ["fr.apkg"]
    pending[0](True)  # type: ignore[operator]
    assert started == ["fr.apkg", "en.apkg"]
    pending[1](True)  # type: ignore[operator]
    assert started[-1] == "finished"


def test_cancellation_stops_the_queue() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    catalog = add_subscription(catalog, _subscription("en", "wset3-vin-en.apkg"))
    prepared: list[str] = []

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        prepared.append(subscription.id)
        done(Prepared(error="cancelled"))

    run_install_queue(
        catalog,
        ["fr", "en"],
        prepare=prepare,
        import_file=lambda path, done: done(True),
        checked_at=lambda: "t",
        on_finished=lambda result: prepared.append("finished"),
    )
    assert prepared == ["fr", "finished"]


def test_a_download_error_does_not_change_the_installed_version() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    seen: dict[str, object] = {}

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        done(Prepared(release=_release("v1.4.0"), error="too_large"))

    run_install_queue(
        catalog,
        ["fr"],
        prepare=prepare,
        import_file=lambda path, done: (_ for _ in ()).throw(AssertionError("imported")),
        checked_at=lambda: "t",
        on_finished=lambda result: seen.update(catalog=result),
    )
    saved = seen["catalog"].subscriptions[0]  # type: ignore[attr-defined]
    assert saved.installed_version == "v1.2.0"
    assert saved.last_error == "too_large"
    assert status_of(saved) == "error"


def test_a_non_version_release_is_not_imported() -> None:
    catalog = add_subscription(empty_catalog(), _subscription())
    seen: dict[str, object] = {}

    def prepare(subscription: Subscription, done) -> None:  # type: ignore[no-untyped-def]
        done(Prepared(release=_release("latest-main")))

    run_install_queue(
        catalog,
        ["fr"],
        prepare=prepare,
        import_file=lambda path, done: (_ for _ in ()).throw(AssertionError("imported")),
        checked_at=lambda: "t",
        on_finished=lambda result: seen.update(catalog=result),
    )
    saved = seen["catalog"].subscriptions[0]  # type: ignore[attr-defined]
    assert saved.installed_version == "v1.2.0"
    assert saved.last_error == "unsupported_version"
