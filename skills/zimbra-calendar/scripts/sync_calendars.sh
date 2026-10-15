#!/usr/bin/env bash
# sync_calendars.sh — Synchronise les calendriers Zimbra (CalDAV) AVANT toute lecture.
#
# Raison d'être : les scripts (list_events.py, point_du_jour.py, …) lisent des
# copies locales .ics. Si elles sont périmées (pas de sync récente), on peut
# RATER des événements que l'interface Zimbra montre pourtant à jour.
# Ce script s'assure que la copie locale reflète le serveur avant lecture.
#
# Robustesse :
#   - Chaque paire est synchronisée individuellement ; l'échec d'une paire
#     (ex. collection « vidée ») ne bloque PAS les autres.
#   - Il n'efface JAMAIS (pas de --force-delete).
#   - Sortie concise sur stdout. Quitte avec code 0 si aucune erreur fatale,
#     1 sinon (les appels supérieurs peuvent ignorer).
#
# Paires gérées : zimbra_cal, zimbra_tasks, zimbra_ade, zimbra_m1ipn, zimbra_m2ipn

PAIRS="zimbra_cal zimbra_tasks zimbra_ade zimbra_m1ipn zimbra_m2ipn"
ERR=0
for p in $PAIRS; do
  if out=$(command vdirsyncer sync "$p" 2>&1); then
    echo "[OK] $p"
  else
    echo "[WARN] $p : $out" | tr '\n' ' ' | cut -c1-200
    echo ""
    ERR=1
  fi
done
exit $ERR