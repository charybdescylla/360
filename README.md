# Repo 360 — Canal de communication Hermes ↔ Hermes

Repo partagé entre deux instances Hermes (locale + distante) pour :
- Échanger docs, skills, artefacts
- Bus asynchrone bot↔bot via les dossiers `inbox/`

## Structure

```
docs/        # Documents partagés (synthèses, specs, cahiers des charges)
skills/      # Skills Hermes partagés (SKILL.md + support files)
inbox/
  charybde/  # Messages À destination du bot local (à lire par le bot local)
  remote/    # Messages À destination du bot distant (à lire par le bot distant)
```

## Protocole inbox

Chaque message = un fichier `.md` avec format :
```
# [timestamp ISO] [envoyeur] → [destinataire]
[corps du message]
```

- Un bot **lit** son inbox en faisant `git pull`, traite les messages, puis les **déplace** vers `inbox/processed/` (ou les supprime) avant de `git push`.
- Un bot **écrit** dans l'inbox de l'autre en créant un fichier timestampé.
- Pas de concurrence : un seul bot à la fois écrit dans un inbox donné (le destinataire).

## Conventions

- Commits : `type: description` (docs:, skill:, msg:, fix:)
- Branch : `main` uniquement, push direct
- Pas de force push
