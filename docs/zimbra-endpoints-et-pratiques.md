# Zimbra UCA — Endpoints, compte, pièges, polling, format

Transféré par charybde-local → remote (2026-10-15) pour l'orchestrateur CIFOR jalon 4.

## 1. Endpoints

| Service | Hôte | Port | Chiffrement | Notes |
|---|---|---|---|---|
| **IMAP** | `imap.uca.fr` | 993 | TLS (implicit) | Lecture/écriture des mails |
| **SMTP** | `smtp.uca.fr` | 587 | STARTTLS | Envoi |
| **CalDAV (lecture)** | `mail.uca.fr` | 443 | HTTPS | `read-proxy` : tout PUT est 302-redirigé vers `mail-sync.uca.fr` et **perd l'auth** |
| **CalDAV (écriture)** | `mail-sync.uca.fr` | 443 | HTTPS | URL avec `%40` au lieu de `@`. C'est le seul endpoint qui accepte les PUT |

Pas de WebSocket, pas de WebDAV pour les mails. L'IMAP est le seul canal de lecture.

## 2. Compte

- **Adresse d'auth (backend IMAP/SMTP)** : `xavier.nicolas@uca.fr`
- **Type** : compte formateur UCA (compte standard)
- **Auth** : mot de passe simple (pas d'app password, pas de 2FA). Le mot de passe est dans un fichier local `~/.imap_pass` (chmod 600) ou `~/.config/vdirsyncer/zimbra.pass` pour CalDAV.
- **Zimbra version** : non documentée précisément, mais le serveur supporte IMAP UID, CalDAV, et les extensions standard. Pas de limitation de quota connue.

### Alias CIFOR (mode d'envoi de la simulation)

> ✅ **Décision (2026-10-15)** : la simulation CIFOR **n'utilise PAS de compte dédié**. Elle envoie via les **alias CIFOR** que le propriétaire du compte gère depuis son adresse pro `xavier.nicolas@uca.fr`.

Concrètement pour ton orchestrateur :
- **Auth IMAP/SMTP** : toujours le compte `xavier.nicolas@uca.fr` + son mot de passe.
- **En-tête `From:`** : l'alias CIFOR (ex. `prenom.nom@cifor-...`) — le serveur Zimbra UCA autorise l'envoi sous ces aliases depuis le compte pro (c'est la même mécanique que mon pipeline de production qui envoie les archives CIFOR depuis un alias).
- **Relecture** : les réponses des "étudiants simulés" arrivent dans la boîte du compte pro (ou dans la boîte de l'alias si Zimbra y a une mailbox propre) — à confirmer avec le propriétaire du compte quel est le comportement exact (alias = redirection vers la boîte pro vs mailbox distincte). C'est LE point à clarifier avant de coder le polling.
- ⚠️ **Séparation des flux** : le compte pro est aussi utilisé par mon pipeline email-workflow de production. Pour ne pas polluer les boîtes, il faudra soit un dossier IMAP dédié (ex. `CiforSimulation`), soit un flag `\CIFOR`, soit un filtrage par alias `From:`. À trancher avec le propriétaire du compte.

> 📌 **Action requise du côté du compte** : le propriétaire (Xavier) doit confirmer (1) la liste exacte des alias CIFOR utilisables, (2) si chaque alias a sa propre mailbox ou si tout redirige vers la boîte pro, (3) le mot d'accès / le mécanisme d'envoi sous alias. Sans ça, ton orchestrateur ne peut pas coder le `From:` et le polling en aval.

## 3. Pièges vécus

### Auth
- Pas d'app password, pas de 2FA sur ce serveur Zimbra UCA. Mot de passe standard.
- Le mot de passe est lu depuis un fichier (`cat ~/.imap_pass`) via la config himalaya — jamais en clair dans la config.

### himalaya (client IMAP/SMTP CLI utilisé en production)
- **`himalaya message read <id> -o json`** retourne du **texte brut** (headers + body), **PAS** du JSON structuré. Il faut parser manuellement : extraire `From:`, `Subject:`, body après la première ligne vide. Ne pas utiliser `json.load()` sur la sortie.
- **`himalaya envelope list -o json`** en revanche retourne bien du JSON structuré (array d'enveloppes).
- **`himalaya message delete`** échoue sur ce compte Zimbra : `command not permitted with UID`. Pour supprimer un brouillon défectueux, passer en IMAP brut : `M.uid('store', uid, '+FLAGS', '(\\Deleted)')` puis `M.expunge()`.
- **`himalaya template write + template save`** crée un draft **sans signature HTML** (texte simple) et peut générer des **doublons**. À ne pas utiliser pour des brouillons destinés à un tiers.
- **Le parser de query de himalaya avale tout ce qui suit** — toujours mettre les options AVANT la query. Ex : `himalaya envelope list -o json "not flag seen"` ✅ vs `himalaya envelope list "not flag seen" -o json` ❌

### IMAP en Python (imaplib)
- Toujours utiliser `M.uid(...)` pour les opérations sur des messages, jamais les numéros de séquence. Un fetch de séquence sur un UID lève `BAD parse error: invalid message sequence number`.
- Le blocage IMAP `command not permitted with UID` s'applique à certaines opérations (delete via himalaya) mais **pas** à `uid('store', ...)` + `expunge()`.

### CalDAV
- `mail.uca.fr` est un **read-proxy** : tout PUT y est 302-redirigé vers `mail-sync.uca.fr` et perd l'auth. Le répertoire d'écriture fiable est **`mail-sync.uca.fr`** (URL `%40`).
- `vdirsyncer sync --force-delete` est **interdit** : cela supprimerait toutes les entrées des deux côtés.
- Le miroir local est un cache, la source de vérité est le serveur. Pour lire la vérité, préférer le CalDAV direct (REPORT/PROPFIND).

## 4. Méthode de polling

### En production (email-workflow)
- **Polling périodique** via `himalaya envelope list` + `himalaya message read` — **pas d'IMAP IDLE**.
- Le script `process_emails.py` tourne via **cron** (périodicité configurable).
- Gestion des états : les mails traités sont marqués `\\Seen` via IMAP. Les pièces jointes sont extraites et déposées dans un dossier Vault. Les tâches/événements détectés sont créés dans Zimbra (CalDAV).

### Recommandation pour l'orchestrateur CIFOR
- **Polling périodique** (intervalles 30s-2min selon la criticité). L'IMAP IDLE est plus élégant mais ajoute de la complexité (gestion de la connexion long-lived, reconnection, timeout). Pour un orchestrateur qui fait aussi d'autres choses (appels Open WebUI, post-traitement), le polling est plus simple et plus robuste.
- **Gestion des états** :
  - `\\Seen` = mail lu (déjà vu par l'orchestrateur)
  - Flag custom `\\CIFOR` (si le serveur le supporte) ou un fichier local d'état pour marquer les mails traités
  - Toujours **re-lire les en-têtes** après un APPEND (ne pas se fier au retour seul)
- **Idempotence** : avant de traiter un mail, vérifier qu'il n'a pas déjà été traité (UID + flag). Évite les doublons si le cron tourne deux fois.

## 5. Format des mails entrants

### Structure typique
- **MIME standard** : `multipart/alternative` (text/plain + text/html) ou `multipart/mixed` (avec pièces jointes)
- **Headers essentiels** : `From`, `To`, `Cc`, `Subject`, `Date`, `Message-ID`, `In-Reply-To`, `References`
- **Encoding** : les subjects peuvent être en `=?utf-8?B?...?=` (base64) ou `=?utf-8?Q?...?=` (quoted-printable) — toujours décoder avec `email.header.decode_header()`

### Expéditeurs typiques (en production)
- Étudiants (adresses @etu.uca.fr)
- Collègues formateurs (adresses @uca.fr)
- Notifications système (Moodle, Zimbra, etc.)
- Pour la simulation CIFOR : les "étudiants" seront des adresses simulées (personas)

### Pièces jointes
- Formats courants : PDF, DOCX, XLSX, ZIP
- Extraction : `email.message_from_bytes(raw)` → iter les parties → `part.get_payload(decode=True)` → écrire dans un dossier
- ⚠️ Les noms de fichiers peuvent contenir des accents/espaces — normaliser avant d'écrire

### Threading
- Zimbra utilise `Message-ID` + `In-Reply-To` + `References` pour le threading
- Pour l'orchestrateur : parser ces headers pour relier un mail de réponse à sa conversation
- ⚠️ Les `References` peuvent contenir une longue chaîne de Message-IDs — ne pas les reconstruire, les utiliser telles quelles

## 6. Scripts existants (dans le skill `zimbra-calendar` + `email-workflow`)

Le skill `zimbra-calendar` est copié dans `skills/zimbra-calendar/` de ce repo. Il contient :
- `scripts/list_events.py` — lire les événements CalDAV
- `scripts/create_event.py` — créer un événement
- `scripts/manage_task.py` — gérer les tâches VTODO
- `scripts/email_to_task.py` — détecter si un email implique une tâche (via LLM local)
- `scripts/sync_calendars.sh` — synchroniser CalDAV

Le skill `email-workflow` (non copé ici — trop spécifique à la production UCA) contient :
- `scripts/process_emails.py` — pipeline complet de traitement des mails
- `scripts/relances_proactives.py` — `_append_draft_imap()` pour créer des brouillons
- `scripts/zimbra_api.py` — API CalDAV directe (create_task, complete_task, etc.)

### Brouillons IMAP (méthode propre)
```python
# Construit un MIME multipart/alternative (text/plain + text/html) avec signature
# et pose le brouillon via IMAP APPEND dans Drafts
from relances_proactives import _append_draft_imap
uid = _append_draft_imap('Destinataire', 'dest@x.fr', 'Re: Sujet', 'Corps du mail')
```
- Retourne un **UID** (pas un numéro de séquence)
- ⚠️ Résoudre l'adresse avant l'appel : un `to_addr=None` crée un brouillon cassé
- ⚠️ Vérifier les brouillons créés en relisant les en-têtes

## 7. Config himalaya (extrait, secrets masqués)

```toml
[accounts."xavier.nicolas"]
default = true
email = "xavier.nicolas@uca.fr"
backend.type = "imap"
backend.host = "imap.uca.fr"
backend.port = 993
backend.login = "xavier.nicolas@uca.fr"
backend.encryption.type = "tls"
backend.auth.type = "password"
backend.auth.command = "cat ~/.imap_pass"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.uca.fr"
message.send.backend.port = 587
message.send.backend.login = "xavier.nicolas@uca.fr"
message.send.backend.encryption.type = "start-tls"
message.send.backend.auth.type = "password"
message.send.backend.auth.command = "cat ~/.imap_pass"
```
