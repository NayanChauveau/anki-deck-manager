"""French copy for Deck Manager. Code stays in English."""

from __future__ import annotations

from .domain import Subscription, status_of

MENU = "Deck Manager"
WINDOW_TITLE = "Deck Manager"

COLUMN_DECK = "Deck"
COLUMN_SOURCE = "Source"
COLUMN_VERSION = "Version"
COLUMN_STATUS = "Statut"

ADD = "Ajouter"
CHECK = "Vérifier"
IMPORT = "Importer la mise à jour"
OPEN_REPO = "Ouvrir le dépôt"
REMOVE = "Retirer"

ADD_TITLE = "Ajouter un deck"
ADD_HELP = (
    "Collez l’URL …/releases/download/vX.Y.Z/fichier.apkg. "
    "Les notes absentes du nouveau paquet ne sont pas supprimées. "
    "Anki demandera confirmation avant l’import."
)
ADD_PLACEHOLDER = "https://github.com/propriétaire/dépôt/releases/download/v1.2.0/deck.apkg"
CANCEL = "Annuler"

EMPTY = "Aucun deck suivi."
NO_PROFILE = "Ouvrez un profil Anki pour utiliser Deck Manager."
NO_UPDATE = "Aucune mise à jour à importer."
NO_SELECTION = "Sélectionnez un deck."
DUPLICATE = "Ce fichier est déjà suivi."
ASSET_MISSING = "Ce fichier est absent de la release."
CHECKING = "Vérification…"
DOWNLOADING = "Téléchargement"


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
        return "À jour"
    if status == "update_available":
        return "Mise à jour disponible"
    if status == "asset_missing":
        return "Fichier introuvable"
    if status == "unknown":
        return "Pas encore installé"
    return error_text(subscription.last_error)


def url_error_text(code: str) -> str:
    return {
        "empty": "Collez une URL.",
        "https_required": "L’URL doit commencer par https://.",
        "credentials": "L’URL ne doit pas contenir d’identifiant.",
        "host": "Seul github.com est accepté.",
        "query": "L’URL ne doit pas contenir de paramètres.",
        "path": "L’URL doit être de la forme …/releases/download/vX.Y.Z/fichier.apkg.",
        "version": "Le numéro de version doit être vX.Y.Z ou X.Y.Z.",
        "asset": "L’URL doit désigner un fichier .apkg.",
        "owner": "Nom du propriétaire invalide.",
        "repository": "Nom du dépôt invalide.",
    }.get(code, "URL refusée.")


def removal_message(names: list[str]) -> str:
    if len(names) == 1:
        return f"Retirer le suivi de « {names[0]} » ? Le deck reste dans Anki."
    return "Retirer le suivi de ces decks ? Les decks restent dans Anki."


def error_text(code: str | None) -> str:
    return {
        "rate_limited": "Quota GitHub atteint",
        "not_found": "Dépôt introuvable",
        "http_error": "Hors ligne ou erreur réseau",
        "too_large": "Fichier trop volumineux",
        "unsupported_version": "Version non reconnue",
        "redirect_rejected": "Adresse de téléchargement refusée",
        "cancelled": "Téléchargement annulé",
    }.get(code or "", "Erreur")
