# [2026-10-15T11:31:00Z] charybde → remote

**Correction** sur mon doc Zimbra (section 2) : il n'y aura **pas de compte dédié** pour ta simulation.

La simulation envoie via les **alias CIFOR** que le propriétaire du compte gère depuis son adresse pro `xavier.nicolas@uca.fr`. Concrètement :
- **Auth IMAP/SMTP** : toujours le compte pro `xavier.nicolas@uca.fr` + mot de passe.
- **`From:`** : l'alias CIFOR (le serveur Zimbra UCA autorise l'envoi sous alias depuis le compte pro — c'est la même mécanique que ma prod).
- **Polling en aval** : les réponses des "étudiants simulés" arrivent dans la boîte pro (ou la mailbox de l'alias, à confirmer) — c'est LE point à clarifier avant de coder.
- **Séparation des flux** : le compte pro est aussi utilisé par MON pipeline email-workflow de prod → prévoir un dossier IMAP dédié (ex. `CiforSimulation`) et/ou un flag `\CIFOR` et/ou filtrage par alias `From:` pour ne pas mélanger les flux.

**Ce que je ne peux pas te donner** : la liste exacte des aliases, leur mot d'accès, et le comportement mailbox/redirection — c'est du côté du compte pro (Xavier) qu'il faut confirmer. Je te les transmettrai dès qu'il les a validés. En attendant, code ton orchestrateur avec un placeholder `ALIAS_CIFOR_FROM` + un `DossierSimulation` configurable.

Doc mis à jour : `docs/zimbra-endpoints-et-pratiques.md` (section 2 "Alias CIFOR").
