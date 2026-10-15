---
name: zimbra-calendar
description: "Calendrier Zimbra UCA : lire, créer, modifier, supprimer des événements et tâches. Synchronisation CalDAV via vdirsyncer. Gestion des tâches (VTODO) : création manuelle, détection auto depuis email, catégories."
version: 1.0.0
author: charybde
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Calendar, CalDAV, Zimbra, UCA, Productivity]
---

# Calendrier Zimbra UCA

Gère le calendrier Zimbra via CalDAV (vdirsyncer) et des scripts Python locaux.

## Architecture

- **Server** : `https://mail.uca.fr/dav/xavier.nicolas@uca.fr/`
- **Sync** : `vdirsyncer` (CalDAV → fichiers `.ics` locaux)
- **Lecture** : script Python `scripts/list_events.py` (parse les .ics, corrige UTC→heure locale)
- **Création** : script Python `scripts/create_event.py` + `vdirsyncer sync`
- **Chemin password** : `~/.config/vdirsyncer/zimbra.pass` (chmod 600)

## Calendriers configurés

| Nom | Pair vdirsyncer | Chemin local | URL CalDAV distante |
|---|---|---|---|
| Calendar (perso) | `zimbra_cal` | `~/.calendars/zimbra/Calendar/` | `.../Calendar/` |
| Tasks | `zimbra_tasks` | `~/.calendars/zimbra/Tasks/` | `.../Tasks/` |
| ADE 2026 | `zimbra_ade` | `~/.calendars/zimbra/ADE/` | `.../ADE%202026%20avril%20mai/` |
| M1 IPN (Boissonnet) | `zimbra_m1ipn` | `~/.calendars/zimbra/M1IPN/` | `.../M1%20IPN%20de%20Frederic%20BOISSONNET/` |
| M2 IPN (Boissonnet) | `zimbra_m2ipn` | `~/.calendars/zimbra/M2IPN/` | `.../M2%20IPN%20de%20Frederic%20BOISSONNET/` |

## Opérations

### Lire les événements et tâches d'une période

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/list_events.py --from YYYY-MM-DD --to YYYY-MM-DD
```

Paramètres :
- `--from` : date début (défaut : aujourd'hui)
- `--to` : date fin (défaut : +7 jours)
- `--calendar` : filtrer par nom (Calendar, Tasks, ADE, M1IPN, M2IPN)
- `--no-tasks` : exclure les tâches de l'affichage

Exemples :
```bash
# Aujourd'hui (événements + tâches)
python3 ~/.hermes/skills/zimbra-calendar/scripts/list_events.py --from today --to today

# Cette semaine, événements uniquement
python3 ~/.hermes/skills/zimbra-calendar/scripts/list_events.py --no-tasks

# Semaine prochaine, calendrier perso
python3 ~/.hermes/skills/zimbra-calendar/scripts/list_events.py --from 2026-05-26 --to 2026-06-01 --calendar Calendar
```

### Créer un événement

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/create_event.py \
  --date YYYY-MM-DD \
  --start HH:MM \
  --end HH:MM \
  --summary "Titre de l'événement" \
  --description "Description optionnelle" \
  --location "Lieu optionnel"
```

⚠️ **L'événement est créé dans le calendrier perso (Calendar) uniquement.**

**⚠️ CRUCIAL — l'événement n'apparaîtra PAS dans Zimbra après un simple `vdirsyncer sync`.** Le storage distant `zimbra_remote_cal` est **`read_only = true`** (sur le miroir — sync = pull-only). `mail.uca.fr` est un **read-proxy** : tout PUT y est 302-redirigé vers `mail-sync.uca.fr` et perd l'auth. Le répertoire d'écriture fiable est **`mail-sync.uca.fr`** (URL `%40`).

**✅ La méthode propre : l'outil `zpush`** (`~/.local/bin/zpush`, installé par le profil comfyui — c'est LA référence) : écrit sur `mail-sync` **et** maintient le miroir local `~/.calendars/zimbra/Calendar/` (fichier plat nommé `<UID>.ics`) pour rester cohérent avec le pull-only :
```bash
zpush create --summary "Titre" --start "2026-09-10 21:00" --end "2026-09-10 23:00" [--location "Lieu"] [--description "..."] [--uid <uuid>]
zpush delete <uid>
zpush list
```
**Règles (sinon 403) :** le nom du fichier/URL doit = le VEVENT UID ; login = email brut (`xavier.nicolas@uca.fr`), URL = `%40`. Vérifier par GET/`zpush list`, jamais le 201 seul.

*NB : `create_event.py` du skill direction écrit dans `~/.calendars/zimbra/Calendar/Calendar/` (sous-dossier) — à usage local, la cible serveur/miroir est `~/.calendars/zimbra/Calendar/`. Vérifié 07/09/2026 (soirée BDE) : événement visible côté serveur + miroir après correction d'emplacement.*

### Gérer les tâches (VTODO)

#### Lister les tâches

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py list
```

Filtres disponibles :
- `--status` : NEEDS-ACTION, IN-PROGRESS, COMPLETED, CANCELLED
- `--category` : SAÉ, Admin, Pédagogie, Recherche, Perso
- `--overdue` : uniquement les tâches en retard
- `--due-before YYYY-MM-DD` : tâches dues avant une date

Exemples :
```bash
# Toutes les tâches en attente
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py list --status NEEDS-ACTION

# Tâches SAÉ en retard
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py list --category SAÉ --overdue

# Tâches dues cette semaine
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py list --due-before 2026-05-27
```

#### Créer une tâche

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py create \
  --summary "Titre de la tâche" \
  --description "Description" \
  --due +7 \
  --categories SAÉ \
  --priority 3
```

Paramètres :
- `--summary` : titre (obligatoire)
- `--description` : description détaillée
- `--due` : échéance (YYYY-MM-DD, today, +Nd). **Défaut : +3j** — si aucune date
  n'est fournie (mail de départ sans date), la tâche reçoit une échéance J+3.
- `--categories` : une ou plusieurs parmi SAÉ, Admin, Pédagogie, Recherche, Perso
- `--priority` : 1 (haute) à 9 (basse), défaut 5
- `--status` : NEEDS-ACTION (défaut), IN-PROGRESS, COMPLETED, CANCELLED
- `--remind N` : rappel N jours avant l'échéance (défaut 1 = J-1). Écrit un bloc
  `VALARM` (`TRIGGER:-PN`J`]) dans le VTODO.
- `--no-reminder` : désactive le bloc VALARM.

**🔔 Rappel (VALARM)** : par défaut chaque tâche créée avec une échéance embarque
un rappel `TRIGGER:-P1D` (J-1). Le rappel s'affiche dans Zimbra (web + clients)
et soulage le point du jour : la tâche rappelle d'elle-même avant l'échéance.
Le `list` affiche un 🔔 sur les tâches avec rappel.

#### Mettre à jour une tâche

```bash
# Par UID
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py update \
  --uid <UID> --status COMPLETED

# Par recherche de titre
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py update \
  --summary "Titre partiel" --status IN-PROGRESS --percent 50
```

#### Supprimer une tâche

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py delete --uid <UID>
```

#### Créer une tâche à partir d'un email

```bash
# Détection seule (montre ce qui serait créé)
python3 ~/.hermes/skills/zimbra-calendar/scripts/email_to_task.py \
  --subject "Sujet" --body "Corps" --sender "Expéditeur"

# Depuis un mail lu via himalaya (pipe JSON)
himalaya message read <id> -o json | python3 ~/.hermes/skills/zimbra-calendar/scripts/email_to_task.py

# Création automatique
himalaya message read <id> -o json | python3 ~/.hermes/skills/zimbra-calendar/scripts/email_to_task.py --auto

# Avec échéance personnalisée
himalaya message read <id> -o json | python3 ~/.hermes/skills/zimbra-calendar/scripts/email_to_task.py --auto --due +14 --categories Admin
```

La détection utilise un modèle LLM local (**qwen3-openclaw** via Ollama, custom Qwen3.5:9B avec fenêtre de contexte élargie) qui analyse le contenu de l'email pour déterminer s'il implique une tâche. C'est beaucoup plus fiable qu'une approche par mots-clés :
- Détecte les demandes implicites et déguisées
- Évite les faux positifs (invitations, notifications, infos)
- Extrait automatiquement l'échéance si mentionnée
- Suggère les catégories et la priorité
- Indique un score de confiance

Le modèle tourne sur le Windows host via Ollama, accessible depuis WSL2 via l'IP de passerelle (détectée dynamiquement via `ip route show default` — **ne pas coder l'IP en dur**, elle change à chaque redémarrage). Temps d'analyse : ~60-90s par mail (mode thinking activé). Voir `references/ollama-integration.md` pour les détails de configuration et les modèles disponibles.

#### Détecter si un email implique une tâche

```bash
python3 ~/.hermes/skills/zimbra-calendar/scripts/manage_task.py detect \
  --subject "Sujet du mail" \
  --body "Corps du mail"
```

### Supprimer un événement

1. Trouver l'UID et le chemin du fichier .ics via `list_events.py --verbose`
2. Supprimer le fichier .ics
3. Lancer `vdirsyncer sync zimbra_cal` (l'événement sera supprimé côté Zimbra)

### Resynchroniser

```bash
# Tout synchroniser (robuste — continue même si une paire échoue)
~/.hermes/skills/zimbra-calendar/scripts/sync_calendars.sh

# Tout synchroniser
for pair in zimbra_cal zimbra_tasks zimbra_ade zimbra_m1ipn zimbra_m2ipn; do
  vdirsyncer sync $pair
done

# Ou un seul
vdirsyncer sync zimbra_cal
vdirsyncer sync zimbra_tasks
```

### ⚠️ Sync AVANT lecture (indispensable — ne jamais lire sans sync)

**Depuis 2026-08-20** : `list_events.py` (et donc `point_du_jour.py` qui l'importe)
synchronise CalDAV **automatiquement avant de lire**. Les copies locales `.ics`
peuvent être périmées et faire RATER des événements que l'écran Zimbra montre
pourtant à jour (cas réel : soutenance de mémoire invisible localement).

- Script : `sync_calendars.sh` — torolère les pannes d'une collection, n'efface
  jamais (`--force-delete` interdit), sortie concise.
- Appelé à l'import de `list_events.py` → couvre lecture CLI **et** import dans
  `point_du_jour.py`.
- Désactivable si besoin (offline / rapidité) :
  `ZV_SKIP_SYNC=1 python3 …/list_events.py …`

**Piège rencontré** : le bilan de `zimbra_tasks` affiche souvent
`Storage "zimbra_remote_tasks/Tasks" was completely emptied`. C'est **non fatal**
pour la lecture (les autres paires continuent). Ne **jamais** lancer
`vdirsyncer sync --force-delete` : cela supprimerait toutes les entrées des deux
côtés.

**Réparation** (faite le 11/09/2026) : cet avertissement = le miroir local et le
serveur ont divergé (des `.ics` ont été créés localement sans jamais pouvoir
partir, le remote `zimbra_tasks` étant `read_only=true`). Marche à suivre —
**sauvegarder d'abord**, le remote est pull-only donc rien ne peut être poussé côté Zimbra :
1. copier les `.ics` locaux suspects ailleurs (jamais les supprimer) ;
2. sauvegarder puis **supprimer** `~/.config/vdirsyncer/status/zimbra_tasks*` ;
3. `vdirsyncer discover zimbra_tasks` puis `vdirsyncer sync zimbra_tasks`
   → le miroir local est reconstruit depuis le serveur (source de vérité).

### ⚠️ Piège : `manage_task.py` lisait une liste FANTÔME (corrigé 11/09/2026)

`TASKS_DIR` pointait sur `~/.calendars/zimbra/Tasks/Tasks/` (collection
**imbriquée**, héritage d'une ancienne config). vdirsyncer écrit **à plat** dans
`~/.calendars/zimbra/Tasks/`. Résultat : `manage_task.py list` affichait 16
vieilles tâches locales **inexistantes côté Zimbra**, et ratait les 27 vraies —
le point du jour rapportait donc des échéances fausses (constaté le 11/09, sur
une demande de complétion : « 6 tâches » au lieu de 26).
- Corrigé : `TASKS_DIR = ~/.calendars/zimbra/Tasks/` (+ surcharge `ZIMBRA_TASKS_DIR`).
- **Pour LIRE la vérité, préférer le CalDAV direct** (`zimbra_api` REPORT/PROPFIND
  sur `…/Tasks/`) : c'est la source de vérité, le miroir local n'est qu'un cache.
- Corollaire : `manage_task.py create/update/delete` écrirait **localement sans
  jamais pousser** (remote `read_only`) → pour créer/compléter une tâche, passer
  par `zimbra_api.create_task` / `zimbra_api.complete_task` (PUT CalDAV avec
  `If-Match`, HTTP 204). Vérifier par relecture serveur avant de conclure.

## Fuseau horaire

Zimbra stocke les dates en UTC ou avec `TZID="Europe/Brussels"`. Le script de lecture convertit automatiquement en heure locale (UTC+1/+2). **La France est en UTC+2 en été (heure d'avril à octobre).**

## Sécurité

- Le mot de passe est dans `~/.config/vdirsyncer/zimbra.pass` (chmod 600)
- Ne jamais afficher le mot de passe dans la conversation
- Les calendriers partagés (M1IPN, M2IPN, ADE) ne doivent pas être modifiés

## Limites connues

- `vdirsyncer` ne synchronise que les collections explicitement configurées
## Pitfalls

### Timezone naive vs aware
- Le parser ICS peut retourner des datetimes tz-aware (avec `TZID=Europe/Brussels` ou `Z`) ou naïves (format `VALUE=DATE`).
- **Toujours normaliser** avant de comparer/trier : `if dt.tzinfo is not None: dt = dt.replace(tzinfo=None)`
- Sans ça, `sort()` plante avec `TypeError: can't compare offset-naive and offset-aware datetimes`.

### himalaya `message read` returns raw text, NOT structured JSON
- `himalaya envelope list -o json` → returns structured JSON array ✅
- `himalaya message read <id> -o json` → returns **raw email text** (headers + body), NOT a JSON object ❌
- Must parse manually: extract `From:`, `Subject:`, body after first blank line
- Do NOT use `json.load()` on `himalaya message read` output — it will fail or parse incorrectly

### Ollama Qwen3 thinking models require large num_predict
- Qwen3 models with thinking enabled (qwen3-openclaw, qwen3.5:9b, hermes-extreme) consume ~10K tokens for thinking
- Must set `num_predict: 4096` in Ollama options, otherwise response is truncated/empty
- With sufficient num_predict, the final answer appears in the `response` field (not `thinking`)
- `think: False` parameter is NOT supported by these models — they always think
- Expect ~60s inference time per call due to thinking overhead

### ⚠️ Piège : décalage n-1 des événements dans l'agenda 7 jours (2026-09-01)

**Symptôme** : le point du jour ou tout rendu d'agenda 7 jours affiche chaque événement le jour **avant** sa date réelle (ex. « soutenance de Eve » montrée le 1er/09 alors qu'elle est le 02/09). Les dates brutes dans les fichiers `.ics` sont correctes — l'erreur vient du **regroupement par jour** effectué lors du rendu.

**Cause** : `list_events.py` retourne des tuples `(dt, summary, location, calendar_name)` où `dt` est le datetime **exact** de l'événement (déjà converti en heure locale). Si l'agent regroupe manuellement les événements par jour en utilisant une variable `today` décalée (ex. `today = date.today() - timedelta(days=1)` ou une erreur de timezone dans la normalisation), tous les événements glissent d'un jour.

**Vérification** : comparer la date affichée dans le briefing avec la date `dt.strftime("%Y-%m-%d")` du tuple retourné par `list_events.py`. Si écart de 1 jour → le regroupement par jour est fautif.

**Correction** : s'assurer que le script de rendu regroupe les événements en utilisant `dt.date()` (pas `dt - timedelta(days=1)` ou une autre manipulation), et que `today` est bien `datetime.now().date()` (heure locale), pas une date UTC convertie.

### CLI tool usage: check docs before trial-and-error
- **Ne pas tâtonner** avec les CLI tools (himalaya, vdirsyncer, etc.). Consulter d'abord le skill ou `--help`.
- Le parser de query de himalaya avale tout ce qui suit — toujours mettre les options AVANT la query.
- Exemple : `himalaya envelope list -o json "not flag seen"` ✅ vs `himalaya envelope list "not flag seen" -o json` ❌

### create_event.py : validation de date
- Depuis le 2026-05-27, `create_event.py` valide le format de date (`YYYY-MM-DD HH:MM`) avant d'appeler `strptime`.
- Si la date est invalide (LLM hallucinant, format incorrect), le script imprime une erreur claire et **sort avec exit code 1** au lieu de crasher avec `ValueError`.
- Le script appelant (`process_emails.py` dans email-workflow) capture cette erreur et affiche le message via stdout (pas stderr — le message d'erreur est dans stdout).
