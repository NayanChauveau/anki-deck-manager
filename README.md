# Deck Manager

Add-on pour Anki Desktop. Il installe un deck `.apkg` publié sur GitHub, et propose une mise à jour quand le numéro de version change.

Anki **26.09** ou plus récent. Menu **Outils → Deck Manager**. Pas de compte et pas de token : les dépôts suivis sont publics. La fenêtre suit la langue d’Anki : français ou anglais. Les autres langues utilisent l’anglais.

## Installer

Télécharge le `.ankiaddon` de la [dernière release](https://github.com/NayanChauveau/anki-deckdock/releases/latest), puis double-clique dessus. Ou, dans Anki : **Outils → Extensions → Installer depuis un fichier**. Redémarre Anki.

## Ajouter un deck

Colle une adresse de cette forme, et seulement celle-là :

```text
https://github.com/propriétaire/dépôt/releases/download/v1.2.0/mon-deck.apkg
```

Le numéro (`v1.2.0` ou `1.2.0`) et le nom du fichier font partie de l’adresse. Le nom du fichier reste le même d’une version à l’autre.

Une page de dépôt, un lien « latest », ou un tag comme `latest-main` est refusé. Deux fichiers du même dépôt, par exemple un français et un anglais, font deux suivis.

Le nom affiché est le label du fichier sur GitHub, sinon le nom du fichier sans `.apkg`.

## Au quotidien

Au démarrage, s’il existe une nouvelle version, une fenêtre propose **Plus tard** ou **Importer**. Plus tard dure jusqu’au prochain démarrage. Plusieurs mises à jour se cochèrent, puis s’importent l’une après l’autre.

Dans la fenêtre, le tableau montre le deck, la source, la version et le statut.

- **Vérifier** regarde tout de suite.
- **Importer** télécharge le fichier, puis ouvre le dialogue d’import d’Anki, le même que **Fichier → Importer**. Les cases de ce dialogue restent les tiennes. La version n’est enregistrée que si tu confirmes.
- **Ouvrir le dépôt** affiche la page GitHub.
- **Retirer** enlève le suivi. Le deck reste dans Anki.

Une vérification automatique a lieu au plus toutes les 24 heures par dépôt, sans bloquer Anki. **Vérifier** ignore ce délai. Hors ligne, dépôt absent, quota GitHub ou fichier introuvable : le statut reste dans le tableau.

## Ce qu’une mise à jour veut dire

Deck Manager lit la release stable du dépôt.

- Le numéro a changé : une mise à jour est proposée.
- Le numéro est le même : rien à faire, même si le fichier a été remplacé.
- `v1.2.0` et `1.2.0` sont deux numéros différents.
- Les numéros ne sont pas classés. `v1.10` n’est pas « plus grand » que `v1.9` : GitHub désigne la release stable, Deck Manager compare les deux textes.

L’import ajoute et met à jour les cartes. Il ne supprime pas celles qui ont disparu du nouveau paquet.

## Publier un deck

1. Une release GitHub par version, avec le tag `vX.Y.Z` (ou `X.Y.Z`).
2. Le `.apkg` garde le même nom de fichier.
3. Donne l’adresse `…/releases/download/vX.Y.Z/fichier.apkg`.
4. Pour changer le contenu, publie un **nouveau** numéro. Ne remplace pas le fichier d’une version déjà publiée.

Un dépôt qui ne publie que `latest-main` ne peut pas être suivi.

## Licence

[GNU AGPL v3.0](https://www.gnu.org/licenses/agpl-3.0.html) ou ultérieure.
