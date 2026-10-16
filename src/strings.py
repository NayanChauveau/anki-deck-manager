"""Interface copy. French when Anki is in French, English otherwise."""

from __future__ import annotations

from .domain import Subscription, status_of

_FR = {
    "MENU": "Deck Manager",
    "WINDOW_TITLE": "Deck Manager",
    "COLUMN_DECK": "Deck",
    "COLUMN_SOURCE": "Source",
    "COLUMN_VERSION": "Version",
    "COLUMN_STATUS": "Statut",
    "ADD": "Ajouter",
    "CHECK": "Vérifier",
    "IMPORT": "Importer la mise à jour",
    "OPEN_REPO": "Ouvrir le dépôt",
    "REMOVE": "Retirer",
    "ADD_TITLE": "Ajouter un deck",
    "ADD_HELP": (
        "Collez l’URL …/releases/download/vX.Y.Z/fichier.apkg. "
        "Les notes absentes du nouveau paquet ne sont pas supprimées. "
        "Anki demandera confirmation avant l’import."
    ),
    "ADD_PLACEHOLDER": "https://github.com/propriétaire/dépôt/releases/download/v1.2.0/deck.apkg",
    "CANCEL": "Annuler",
    "EMPTY": "Aucun deck suivi.",
    "NO_PROFILE": "Ouvrez un profil Anki pour utiliser Deck Manager.",
    "NO_UPDATE": "Aucune mise à jour à importer.",
    "NO_SELECTION": "Sélectionnez un deck.",
    "DUPLICATE": "Ce fichier est déjà suivi.",
    "ASSET_MISSING": "Ce fichier est absent de la release.",
    "DOWNLOADING": "Téléchargement",
    "LATER": "Plus tard",
    "UP_TO_DATE": "À jour",
    "UPDATE_AVAILABLE": "Mise à jour disponible",
    "FILE_MISSING": "Fichier introuvable",
    "NOT_INSTALLED": "Pas encore installé",
    "URL_EMPTY": "Collez une URL.",
    "URL_HTTPS": "L’URL doit commencer par https://.",
    "URL_CREDENTIALS": "L’URL ne doit pas contenir d’identifiant.",
    "URL_HOST": "Seul github.com est accepté.",
    "URL_QUERY": "L’URL ne doit pas contenir de paramètres.",
    "URL_PATH": "L’URL doit être de la forme …/releases/download/vX.Y.Z/fichier.apkg.",
    "URL_VERSION": "Le numéro de version doit être vX.Y.Z ou X.Y.Z.",
    "URL_ASSET": "L’URL doit désigner un fichier .apkg.",
    "URL_OWNER": "Nom du propriétaire invalide.",
    "URL_REPOSITORY": "Nom du dépôt invalide.",
    "URL_REJECTED": "URL refusée.",
    "UPDATES_ONE": "Mise à jour disponible",
    "UPDATES_MANY": "{count} mises à jour disponibles",
    "NOTICE": "{name} : {installed} est installée, {available} est disponible.",
    "REMOVE_ONE": "Retirer le suivi de « {name} » ? Le deck reste dans Anki.",
    "REMOVE_MANY": "Retirer le suivi de ces decks ? Les decks restent dans Anki.",
    "RATE_LIMITED": "Quota GitHub atteint",
    "NOT_FOUND": "Dépôt introuvable",
    "HTTP_ERROR": "Hors ligne ou erreur réseau",
    "TOO_LARGE": "Fichier trop volumineux",
    "UNSUPPORTED_VERSION": "Version non reconnue",
    "REDIRECT_REJECTED": "Adresse de téléchargement refusée",
    "CANCELLED": "Téléchargement annulé",
    "ERROR": "Erreur",
}

_EN = {
    "MENU": "Deck Manager",
    "WINDOW_TITLE": "Deck Manager",
    "COLUMN_DECK": "Deck",
    "COLUMN_SOURCE": "Source",
    "COLUMN_VERSION": "Version",
    "COLUMN_STATUS": "Status",
    "ADD": "Add",
    "CHECK": "Check",
    "IMPORT": "Import update",
    "OPEN_REPO": "Open repository",
    "REMOVE": "Remove",
    "ADD_TITLE": "Add a deck",
    "ADD_HELP": (
        "Paste a …/releases/download/vX.Y.Z/file.apkg URL. "
        "Notes missing from the new package are not deleted. "
        "Anki will ask you to confirm the import."
    ),
    "ADD_PLACEHOLDER": "https://github.com/owner/repository/releases/download/v1.2.0/deck.apkg",
    "CANCEL": "Cancel",
    "EMPTY": "No decks followed yet.",
    "NO_PROFILE": "Open an Anki profile to use Deck Manager.",
    "NO_UPDATE": "No update to import.",
    "NO_SELECTION": "Select a deck.",
    "DUPLICATE": "This file is already followed.",
    "ASSET_MISSING": "This file is not in the release.",
    "DOWNLOADING": "Downloading",
    "LATER": "Later",
    "UP_TO_DATE": "Up to date",
    "UPDATE_AVAILABLE": "Update available",
    "FILE_MISSING": "File not found",
    "NOT_INSTALLED": "Not installed yet",
    "URL_EMPTY": "Paste a URL.",
    "URL_HTTPS": "The URL must start with https://.",
    "URL_CREDENTIALS": "The URL must not contain a username or password.",
    "URL_HOST": "Only github.com is accepted.",
    "URL_QUERY": "The URL must not contain parameters.",
    "URL_PATH": "The URL must look like …/releases/download/vX.Y.Z/file.apkg.",
    "URL_VERSION": "The version number must be vX.Y.Z or X.Y.Z.",
    "URL_ASSET": "The URL must point to an .apkg file.",
    "URL_OWNER": "Invalid owner name.",
    "URL_REPOSITORY": "Invalid repository name.",
    "URL_REJECTED": "URL rejected.",
    "UPDATES_ONE": "Update available",
    "UPDATES_MANY": "{count} updates available",
    "NOTICE": "{name}: {installed} is installed, {available} is available.",
    "REMOVE_ONE": "Stop following “{name}”? The deck stays in Anki.",
    "REMOVE_MANY": "Stop following these decks? The decks stay in Anki.",
    "RATE_LIMITED": "GitHub rate limit reached",
    "NOT_FOUND": "Repository not found",
    "HTTP_ERROR": "Offline or network error",
    "TOO_LARGE": "File too large",
    "UNSUPPORTED_VERSION": "Unrecognized version",
    "REDIRECT_REJECTED": "Download address rejected",
    "CANCELLED": "Download cancelled",
    "ERROR": "Error",
}

_URL_ERRORS = {
    "empty": "URL_EMPTY",
    "https_required": "URL_HTTPS",
    "credentials": "URL_CREDENTIALS",
    "host": "URL_HOST",
    "query": "URL_QUERY",
    "path": "URL_PATH",
    "version": "URL_VERSION",
    "asset": "URL_ASSET",
    "owner": "URL_OWNER",
    "repository": "URL_REPOSITORY",
}

_ERRORS = {
    "rate_limited": "RATE_LIMITED",
    "not_found": "NOT_FOUND",
    "http_error": "HTTP_ERROR",
    "too_large": "TOO_LARGE",
    "unsupported_version": "UNSUPPORTED_VERSION",
    "redirect_rejected": "REDIRECT_REJECTED",
    "cancelled": "CANCELLED",
}


def language() -> str:
    """French when Anki’s interface is French. English for every other language."""
    try:
        import anki.lang as lang
    except Exception:
        return "fr"
    # set_lang() fills this when Anki has chosen a language. Tests never do.
    if lang.current_i18n is None:
        return "fr"
    code = lang.current_lang if isinstance(lang.current_lang, str) else ""
    return "fr" if code.lower().startswith("fr") else "en"


def _text(key: str) -> str:
    bundle = _FR if language() == "fr" else _EN
    return bundle[key]


def __getattr__(name: str) -> str:
    if name not in _FR:
        raise AttributeError(name)
    return _text(name)


def version_text(subscription: Subscription) -> str:
    installed = subscription.installed_version
    available = subscription.available_version
    if installed and available:
        return f"{installed} → {available}"
    return installed or available or "—"


def source_text(subscription: Subscription) -> str:
    return f"{subscription.owner}/{subscription.repository}"


def status_text(subscription: Subscription) -> str:
    status = status_of(subscription)
    if status == "up_to_date":
        return _text("UP_TO_DATE")
    if status == "update_available":
        return _text("UPDATE_AVAILABLE")
    if status == "asset_missing":
        return _text("FILE_MISSING")
    if status == "unknown":
        return _text("NOT_INSTALLED")
    return error_text(subscription.last_error)


def url_error_text(code: str) -> str:
    return _text(_URL_ERRORS.get(code, "URL_REJECTED"))


def updates_title(count: int) -> str:
    if count == 1:
        return _text("UPDATES_ONE")
    return _text("UPDATES_MANY").format(count=count)


def update_notice(subscription: Subscription) -> str:
    return _text("NOTICE").format(
        name=subscription.display_name,
        installed=subscription.installed_version or "—",
        available=subscription.available_version or "—",
    )


def removal_message(names: list[str]) -> str:
    if len(names) == 1:
        return _text("REMOVE_ONE").format(name=names[0])
    return _text("REMOVE_MANY")


def error_text(code: str | None) -> str:
    return _text(_ERRORS.get(code or "", "ERROR"))
