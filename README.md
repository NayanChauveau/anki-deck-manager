# Deck Manager

Add-on pour Anki Desktop. Il installe un deck `.apkg` publié sur GitHub, retient cette installation, et propose une mise à jour quand le numéro de version change.

Anki **26.09** minimum (`min_point_version` 260900). Pas de serveur, pas de compte, pas de token. Les dépôts suivis sont publics. L’import est celui d’Anki (Fichier → Importer) : Deck Manager ne fusionne pas les cartes lui-même et n’ouvre pas la base SQLite.

Le menu prévu est **Outils → Deck Manager**. Les textes de l’interface sont en français.

## URL à coller

Une seule forme est acceptée :

```text
https://github.com/{propriétaire}/{dépôt}/releases/download/{version}/{fichier}.apkg
```

Exemple :

```text
https://github.com/NayanChauveau/wine-theory-anki/releases/download/v1.2.0/wset3-vin-fr.apkg
```

| Morceau | Rôle |
| --- | --- |
| `propriétaire` / `dépôt` | Dépôt GitHub public. `www.github.com` est ramené à `github.com`. |
| `version` | `vX.Y.Z` ou `X.Y.Z`, par exemple `v1.2.0` ou `1.2.0`. |
| `fichier.apkg` | Le deck. Le nom reste le même d’une version à l’autre. |

HTTPS uniquement. Une URL avec identifiant, mot de passe ou query string est refusée.

Ces adresses sont refusées :

- la page du dépôt (`https://github.com/org/repo`) ;
- `…/releases/latest` ;
- `…/releases/tag/v1.2.0` ;
- un tag qui n’est pas un numéro, dont `latest-main`, `v1.2`, `v1.2.0-beta` ;
- un fichier qui ne finit pas par `.apkg` ;
- un autre hôte que GitHub.

L’URL désigne déjà un fichier et une version. Il n’y a pas de recherche des decks du dépôt.

## Publier un deck

Pour qu’un deck puisse être suivi :

1. Créer une release GitHub par version, avec le tag `vX.Y.Z` (ou `X.Y.Z`).
2. Joindre le `.apkg` sous un nom stable. `wset3-vin-fr.apkg` reste `wset3-vin-fr.apkg` en `v1.3.0`.
3. Donner l’URL `…/releases/download/v1.2.0/wset3-vin-fr.apkg`.
4. Pour une modification du contenu, publier un **nouveau** numéro. Ne pas remplacer le fichier de la version déjà publiée.

Le nom affiché dans Deck Manager est le label GitHub de l’asset, s’il est renseigné. Sinon, c’est le nom du fichier sans `.apkg`. Il n’y a pas de manifeste à ajouter dans le dépôt.

Deux fichiers du même dépôt, par exemple `wset3-vin-fr.apkg` et `wset3-vin-en.apkg`, font deux suivis. Le même triplet propriétaire + dépôt + fichier ne peut pas être ajouté deux fois. La casse du propriétaire et du dépôt ne compte pas ; la casse du nom de fichier compte.

`latest-main` n’est pas une version. Un dépôt qui ne publie que ce tag ne peut pas être suivi. Wine Theory est dans ce cas aujourd’hui : ses paquets existent, mais pas encore sous `…/releases/download/vX.Y.Z/….apkg`.

## Comment une mise à jour est décidée

Deck Manager lit la release **stable** du dépôt, celle que GitHub sert sur `GET /repos/{propriétaire}/{dépôt}/releases/latest`. Les préversions sont hors de ce canal : c’est le choix de GitHub, pas un tri fait ici.

Ensuite, pour le fichier suivi :

- le fichier est absent de cette release : statut « fichier introuvable ». Aucun autre `.apkg` n’est pris à sa place ;
- le tag de cette release n’est pas un numéro `vX.Y.Z` ou `X.Y.Z` : le statut est « Version non reconnue ». `latest-main` ne propose donc pas de mise à jour ;
- le numéro est le même que la version installée : à jour ;
- le numéro est différent : mise à jour proposée.

Le numéro n’est pas comparé comme un texte (`v1.9` n’est pas classé par rapport à `v1.10`) et n’est pas interprété comme un semver. Si GitHub désigne `v1.10.0` comme release stable et que la version installée est `v1.9.0`, la mise à jour proposée est `v1.10.0`. Si les deux chaînes sont identiques, il n’y a pas de mise à jour, même lorsque les octets du fichier ont changé.

Conséquence : republier le même tag avec un autre `.apkg` ne sera pas vu. Un changement de contenu se publie avec un nouveau numéro, le nom de fichier restant le même.

La mise à jour n’est jamais imposée. La version installée n’est enregistrée qu’après un import confirmé dans le dialogue Anki. Fermer ce dialogue avant la fin conserve l’ancienne version.

Une vérification automatique a lieu au plus toutes les 24 heures par dépôt (`check_interval_hours` dans `src/config.json`). Le bouton Vérifier ignore ce délai. Une seule requête est faite par dépôt, même s’il contient plusieurs fichiers suivis. Si GitHub répond `304`, seule la date de vérification est mise à jour.

Sans token, GitHub autorise 60 requêtes par heure. Une réponse `403` ou `429` est affichée comme un quota, sans nouvel essai.

## Import

Le fichier est téléchargé, puis ouvert avec le dialogue d’import d’Anki. Les options de ce dialogue (planification, notes, modèles) restent celles que la personne choisit. Deck Manager ne les force pas.

L’import Anki ajoute et met à jour. Il ne retire pas les notes qui ont disparu du nouveau paquet. Retirer un suivi ne supprime pas le deck dans Anki.

Plusieurs fichiers s’importent l’un après l’autre : téléchargement, dialogue, fermeture, fichier suivant.

Au moment du clic, la release stable est relue. Le fichier téléchargé est celui de cette relecture. La taille annoncée et la taille reçue sont plafonnées à 512 Mio (`max_download_bytes`). Un timeout ou une réponse HTTP autre que 200 supprime le fichier temporaire et n’ouvre pas l’import.

Hôtes autorisés pour le téléchargement : `github.com`, `api.github.com`, `release-assets.githubusercontent.com`, `objects.githubusercontent.com`. Toute autre redirection est refusée. L’API elle-même ne suit une redirection que si elle reste sur `api.github.com`.

Le réseau ne bloque pas le démarrage d’Anki. Aucun code du dépôt GitHub n’est exécuté. Le HTML et le JavaScript éventuels d’un modèle de carte restent du contenu Anki, importés seulement après confirmation dans son dialogue.

## Fenêtre

Tableau : deck, source (`propriétaire/dépôt`), version, statut.

Actions : Ajouter, Vérifier, Importer la mise à jour, Ouvrir le dépôt, Retirer. Retirer demande confirmation et précise que le deck Anki reste en place.

À l’ajout, un texte rappelle que les notes absentes du paquet ne sont pas supprimées.

Au démarrage, une seule notification par session. Elle indique la version installée et la nouvelle version, avec **Plus tard** et **Importer**. Plus tard dure jusqu’au prochain démarrage. Plusieurs mises à jour sont listées ; les lignes cochées s’importent dans l’ordre.

Les erreurs restent dans le tableau : hors ligne, dépôt absent, quota, fichier introuvable.

## Ce qui est enregistré

Les suivis sont dans la collection Anki, clé `deck_manager`, schéma version 1. Ils suivent le profil et la synchronisation Anki. Chaque suivi retient le dépôt, le nom du fichier, le nom affiché, la version installée, la version disponible, la date de vérification et la dernière erreur.

Il n’y a pas d’interrupteur pour désactiver un suivi.

## Ce que Deck Manager ne fait pas

- dépôts privés, token, AnkiWeb, une autre forge que GitHub ;
- import sans afficher le dialogue Anki ;
- ignorer une version précise pour toujours ;
- promettre une fusion sans conflit sur un `.apkg` quelconque ;
- supprimer les cartes retirées du paquet publié ;
- supprimer le deck Anki quand on retire le suivi.

## Dans ce dépôt aujourd’hui

Le contrat ci-dessus est celui du produit. Le code présent couvre la lecture de l’URL, l’API GitHub, la comparaison des numéros, le stockage, le téléchargement (hôtes, taille, annulation entre les blocs) et l’import un fichier à la fois. La version n’est enregistrée que si le dialogue Anki confirme l’import. Ces chemins sont testés sans lancer Anki.

Le menu **Outils → Deck Manager** ouvre la fenêtre : ajout par URL, vérification, import des mises à jour, ouverture du dépôt, retrait du suivi. Retirer un suivi laisse le deck dans Anki.

Au démarrage, une vérification part après l’ouverture du profil, au plus toutes les 24 heures par dépôt, sans bloquer Anki et sans dialogue de progression. S’il y a une mise à jour, une fenêtre propose **Plus tard** ou **Importer**. Plusieurs mises à jour sont cochées dans la même fenêtre, puis importées l’une après l’autre. Plus tard dure jusqu’au prochain démarrage. Redémarrer Anki pour charger le code.

Installation de développement, une fois Anki 26.09 ouvert au moins une fois :

```bash
ln -s /chemin/vers/anki-deckdock/src \
  "$HOME/Library/Application Support/Anki2/addons21/deck_manager"
```

Le dossier lié doit s’appeler `deck_manager`, comme le champ `package` de `src/manifest.json`. Après un changement de code, redémarrer Anki.

Tests, sans Anki :

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

Python 3.13 ou plus récent. Les tests n’importent pas `aqt`.

## Licence

[GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html) ou ultérieure.
