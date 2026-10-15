# VTODO Format in Zimbra Tasks

Zimbra Tasks are stored as `VTODO` components in `.ics` files, distinct from `VEVENT` (calendar events).

## Example .ics structure

```
BEGIN:VCALENDAR
PRODID:Zimbra-Calendar-Provider
VERSION:2.0
BEGIN:VTODO
UID:f63b8e21-d289-4dde-977b-bb222765acc5
SUMMARY:Recensement demandes de matériel
DESCRIPTION:\n
PRIORITY:5
PERCENT-COMPLETE:100
COMPLETED:20200305T154148Z
ORGANIZER;CN=Xavier NICOLAS:mailto:xavier.nicolas@uca.fr
DUE;VALUE=DATE:20200227
STATUS:COMPLETED
CLASS:PUBLIC
LAST-MODIFIED:20200305T154148Z
DTSTAMP:20200305T154148Z
SEQUENCE:1
END:VTODO
END:VCALENDAR
```

## Key VTODO fields

| Field | Values | Notes |
|---|---|---|
| `STATUS` | `NEEDS-ACTION`, `COMPLETED`, `IN-PROCESS`, `CANCELLED` | |
| `PERCENT-COMPLETE` | 0-100 | |
| `PRIORITY` | 1-9 (1=highest), 5=normal | |
| `DUE` | Date or DateTime | `DUE;VALUE=DATE:20200227` or `DUE:20200227T235959Z` |
| `COMPLETED` | DateTime (UTC) | Only present when STATUS=COMPLETED |
| `SUMMARY` | Free text | Task title |
| `DESCRIPTION` | Free text | May contain `\n` literal |
| `UID` | UUID | Unique identifier, used as filename |

## Current limitation

`list_events.py` only parses `BEGIN:VEVENT` blocks. To add VTODO support, the script needs a second parser pass for `BEGIN:VTODO` blocks with the field mapping above.

## Reminder (VALARM)

Depuis 2026-09-04, `manage_task.py create` ajoute un bloc `VALARM` **par défaut**
(toutes les tâches ont une échéance — voir défaut J+3 — et un rappel) :

```
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:<titre de la tâche>
TRIGGER:-P1D
END:VALARM
```

- `TRIGGER:-P1D` = notifie 1 jour avant l'échéance (`--remind N` pour N jours, `--no-reminder` pour désactiver).
- `TRIGGER` est **relatif à DUE** → le rappel suit l'échéance si elle bouge.
- Zimbra (web et clients) affiche le rappel sur la tâche ; le `list` signale la présence avec 🔔.

## Échéance par défaut

Si aucune `DUE` n'est fournie à la création, `create_task` applique `+3 jours`
(`DEFAULT_DUE_DAYS = 3`). Toute tâche créée a donc une échéance et un rappel.

## Local storage path

```
~/.calendars/zimbra/Tasks/Tasks/*.ics
```

Each task is a separate `.ics` file named by its UID.

## Sync

```bash
vdirsyncer sync zimbra_tasks
```

The `zimbra_tasks` pair is configured in `~/.config/vdirsyncer/config` and is **read-write** (unlike M1IPN/M2IPN which are read-only).
