import pytest

from src.domain import UrlError, parse_github_url


def test_versioned_asset_url() -> None:
    source = parse_github_url(
        "https://www.github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/wset3-vin-fr.apkg"
    )
    assert source.owner == "NayanChauveau"
    assert source.repository == "wine-theory-anki"
    assert source.repo_url == "https://github.com/NayanChauveau/wine-theory-anki"
    assert source.version == "v1.2.0"
    assert source.asset_name == "wset3-vin-fr.apkg"


def test_version_without_a_v_prefix() -> None:
    source = parse_github_url(
        "https://github.com/NayanChauveau/wine-theory-anki/releases/download/1.2.0/wset3-vin-fr.apkg"
    )
    assert source.version == "1.2.0"


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/NayanChauveau/wine-theory-anki",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/latest",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/tag/v1.2.0",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/download/latest-main/wset3-vin-fr.apkg",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2/wset3-vin-fr.apkg",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/notes.txt",
        "http://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/deck.apkg",
        "https://user:token@github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/deck.apkg",
        "https://gitlab.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/deck.apkg",
        "https://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/deck.apkg?raw=1",
    ],
)
def test_rejected_urls(url: str) -> None:
    with pytest.raises(UrlError):
        parse_github_url(url)
