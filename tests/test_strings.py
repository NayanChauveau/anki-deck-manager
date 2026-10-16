from src.domain import Subscription
from src import strings


def _subscription(**overrides: object) -> Subscription:
    data: dict[str, object] = {
        "id": "fr",
        "owner": "NayanChauveau",
        "repository": "anki-test",
        "repo_url": "https://github.com/NayanChauveau/anki-test",
        "asset_name": "deck.apkg",
        "display_name": "Deck",
        "installed_version": "v1.0.0",
        "available_version": "v1.3.0",
        "last_error": "rate_limited",
    }
    data.update(overrides)
    return Subscription(**data)  # type: ignore[arg-type]


def test_both_languages_have_the_same_phrases() -> None:
    assert strings._FR.keys() == strings._EN.keys()


def test_without_anki_the_copy_stays_french() -> None:
    assert strings.language() == "fr"
    assert strings.ADD == "Ajouter"
    assert strings.status_text(_subscription()) == "Quota GitHub atteint"


def test_english_anki_uses_english_copy(monkeypatch) -> None:
    monkeypatch.setattr(strings, "language", lambda: "en")
    subscription = _subscription()
    assert strings.ADD == "Add"
    assert strings.LATER == "Later"
    assert strings.status_text(subscription) == "GitHub rate limit reached"
    assert strings.updates_title(2) == "2 updates available"
    assert strings.update_notice(subscription) == "Deck: v1.0.0 is installed, v1.3.0 is available."
    assert "stays in Anki" in strings.removal_message(["Deck"])


def test_a_non_french_anki_language_uses_english(monkeypatch) -> None:
    monkeypatch.setattr(strings, "language", lambda: "en")
    assert strings.CHECK == "Check"
