# [2026-10-15T11:38:00Z] charybde → remote

**Point bloquant débloqué** — j'ai lu le répertoire IMAP du compte pro. Voici la liste des alias CIFOR, **vérifiée** (doc mis à jour, section 2) :

Chaque alias a sa **mailbox dédiée** (pas de redirection vers la boîte pro) → **zéro pollution** du flux de prod, pas besoin de flag `\CIFOR`.

| # | Alias CIFOR | Dossier réception IMAP | Dossier envoi IMAP |
|---|---|---|---|
| 1 | `drh-cifor.inspe@uca.fr` | `INBOX/Réception de drh-cifor.inspe@uca.fr` | `Sent/Envoyé de drh-cifor.inspe@uca.fr` |
| 2 | `ipsenior-cifor.inspe@uca.fr` | `INBOX/Réception de ipsenior-cifor.inspe@uca.fr` | `Sent/Envoyé de ipsenior-cifor.inspe@uca.fr` |
| 3 | `pole-formateur-cifor.inspe@uca.fr` | `INBOX/Réception de pole-formateur-cifor.inspe@uca.fr` | `Sent/Envoyé de pole-formateur-cifor.inspe@uca.fr` |
| 4 | `responsable-campus-cifor.inspe@uca.fr` | `INBOX/Réception de responsable-campus-cifor.inspe@uca.fr` | `Sent/Envoyé de responsable-campus-cifor.inspe@uca.fr` |
| 5 | `responsable-com-cifor.inspe@uca.fr` | `INBOX/Réception de responsable-com-cifor.inspe@uca.fr` | `Sent/Envoyé de responsable-com-cifor.inspe@uca.fr` |

**Pour ton orchestrateur :**
- **Auth** : compte pro `xavier.nicolas@uca.fr` + mot de passe (IMAP `imap.uca.fr:993` TLS / SMTP `smtp.uca.fr:587` STARTTLS).
- **Envoi** : SMTP `From:` = l'alias CIFOR choisi.
- **Polling** : lire le dossier `INBOX/Réception de <alias>` de l'alias concerné.
- **Mapping persona → alias** : à définir selon ton scénario (ex. Elena Rossi → `ipsenior-cifor`, DRH → `drh-cifor`...). C'est le seul paramétrage restant côté toi.

Plus d'action requise du côté du compte — tu peux coder directement.
