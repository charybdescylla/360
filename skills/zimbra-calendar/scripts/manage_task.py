#!/usr/bin/env python3
"""
Manage Zimbra tasks (VTODO): create, update status, delete, list with filters.
After any modification, run: vdirsyncer sync zimbra_tasks
"""

import os
import uuid
import argparse
from datetime import datetime, timedelta, timezone


TASKS_DIR = os.path.expanduser(
    os.environ.get("ZIMBRA_TASKS_DIR", "~/.calendars/zimbra/Tasks/")
)
# ⚠️ Ce dossier est le MIROIR local de la collection CalDAV "Tasks" (vdirsyncer,
# remote en read_only=true) : vdirsyncer écrit à plat dans ~/.calendars/zimbra/Tasks/.
# L'ancien chemin ~/.calendars/zimbra/Tasks/Tasks/ (collection imbriquée) est
# périmé — l'y laisser fait lire une liste fantôme (bug constaté le 11/09/2026).
# Pour LIRE la vérité, préférer le CalDAV direct (zimbra_api.list_tasks/REPORT).

VALID_STATUSES = ["NEEDS-ACTION", "IN-PROGRESS", "COMPLETED", "CANCELLED"]
VALID_CATEGORIES = ["SAÉ", "Admin", "Pédagogie", "Recherche", "Perso"]

# Échéance par défaut quand le mail de départ ne contient aucune date (J+3, décision Xavier 04/09/2026).
DEFAULT_DUE_DAYS = 3
# Rappel par défaut : notifier N jours AVANT l'échéance (VALARM relative à DUE).
DEFAULT_REMIND_DAYS = 1

# Keywords that indicate a task-worthy email (production/validation of documents)
TASK_KEYWORDS = [
    "à valider", "valider", "validation",
    "à relire", "relecture", "relire",
    "à compléter", "compléter", "compléter",
    "à corriger", "corriger", "correction",
    "à vérifier", "vérifier", "vérification",
    "à finaliser", "finaliser", "finalisation",
    "à soumettre", "soumettre", "soumission",
    "à approuver", "approuver", "approbation",
    "à signer", "signer", "signature",
    "à retourner", "retourner",
    "à mettre à jour", "mettre à jour",
    "à préparer", "préparer", "préparation",
    "à rédiger", "rédiger", "rédaction",
    "à transmettre", "transmettre", "transmission",
    "à envoyer", "envoyer",
    "à fournir", "fournir",
    "document", "fichier joint", "pièce jointe",
    "deadline", "échéance", "date limite",
    "rapport", "compte-rendu", "CR",
    "devoir", "rendu", "livrable",
    "dossier", "formulaire",
    "budget", "devis", "facture",
    "planifier", "organiser",
]


def _now_utc():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _date_to_ics(d):
    """Convert datetime/date to ICS date string."""
    if isinstance(d, datetime):
        return d.strftime("%Y%m%dT%H%M%S")
    return d.strftime("%Y%m%d")


def _parse_date_input(s):
    """Parse user date input: YYYY-MM-DD or 'today' or '+Nd'."""
    s = s.strip().lower()
    if s == "today":
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if s.startswith("+"):
        days = int(s[1:])
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return datetime.strptime(s, "%Y-%m-%d")


def create_task(summary, description="", due=None, priority=5, categories=None, status="NEEDS-ACTION", remind_days=DEFAULT_REMIND_DAYS):
    """Create a VTODO .ics file.
    due: explicit deadline, or None → defaults to J+3 (DEFAULT_DUE_DAYS).
    remind_days: N days before DUE for the VALARM reminder. 0/None → no alarm."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    # Échéance par défaut quand aucun date n'est fournie (J+3)
    if due is None:
        due = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=DEFAULT_DUE_DAYS)

    uid = str(uuid.uuid4())
    dtstamp = _now_utc()

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:Hermes-Task-Manager",
        "VERSION:2.0",
        "BEGIN:VTODO",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{summary}",
        f"STATUS:{status}",
        f"PRIORITY:{priority}",
        f"PERCENT-COMPLETE:0",
    ]
    if description:
        # Escape newlines in description
        desc = description.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
        lines.append(f"DESCRIPTION:{desc}")
    if categories:
        lines.append(f"CATEGORIES:{','.join(categories)}")
    # DUE toujours présent (le défaut J+3 s'applique quand aucun date n'était fournie)
    due_str = _date_to_ics(due)
    if isinstance(due, datetime):
        lines.append(f"DUE:{due_str}")
    else:
        lines.append(f"DUE;VALUE=DATE:{due_str[:8]}")
    # Rappel (VALARM) relatif à DUE — notifie à l'avance et soulage le point du jour
    if remind_days and remind_days > 0:
        alarm_title = (summary or "Tâche").replace(",", "\\,").replace(";", "\\;")
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{alarm_title}",
            f"TRIGGER:-P{remind_days}D",
            "END:VALARM",
        ]

    lines += ["END:VTODO", "END:VCALENDAR"]

    path = os.path.join(TASKS_DIR, f"{uid}.ics")
    with open(path, "w") as f:
        f.write("\n".join(lines))

    print(f"✅ Tâche créée : {path}")
    print(f"   UID: {uid}")
    print(f"   Titre: {summary}")
    if categories:
        print(f"   Catégories: {', '.join(categories)}")
    print(f"   Échéance: {due.strftime('%Y-%m-%d') if hasattr(due, 'strftime') else due}")
    if remind_days and remind_days > 0:
        print(f"   🔔 Rappel: {remind_days}j avant échéance")
    else:
        print("   (pas de rappel)")
    print(f"\n📌 Pour synchroniser : vdirsyncer sync zimbra_tasks")
    return path, uid


def update_task(uid=None, summary=None, status=None, percent=None, due=None, categories=None, description=None):
    """Update an existing VTODO by UID or partial summary match."""
    os.makedirs(TASKS_DIR, exist_ok=True)

    # Find the file
    target_file = None
    if uid:
        path = os.path.join(TASKS_DIR, f"{uid}.ics")
        if os.path.exists(path):
            target_file = path
    if not target_file and summary:
        # Fuzzy match by summary
        for f in os.listdir(TASKS_DIR):
            if not f.endswith(".ics"):
                continue
            fp = os.path.join(TASKS_DIR, f)
            with open(fp, "r", errors="replace") as fh:
                content = fh.read()
            if summary.lower() in content.lower():
                target_file = fp
                # Extract UID
                for line in content.split("\n"):
                    if line.startswith("UID:"):
                        uid = line[4:]
                        break
                break

    if not target_file:
        print("❌ Tâche non trouvée.")
        return None

    with open(target_file, "r", errors="replace") as f:
        content = f.read()

    # Parse and modify
    lines = content.split("\n")
    new_lines = []
    in_vtodo = False
    for line in lines:
        if line.strip() == "BEGIN:VTODO":
            in_vtodo = True
        elif line.strip() == "END:VTODO":
            in_vtodo = False

        if in_vtodo:
            if status and line.startswith("STATUS:"):
                line = f"STATUS:{status}"
                if status == "COMPLETED":
                    line_before = new_lines[-1] if new_lines else ""
                    if not any(l.startswith("PERCENT-COMPLETE:") for l in new_lines):
                        new_lines.append("PERCENT-COMPLETE:100")
                    if not any(l.startswith("COMPLETED:") for l in new_lines):
                        new_lines.append(f"COMPLETED:{_now_utc()}")
                continue
            if percent is not None and line.startswith("PERCENT-COMPLETE:"):
                line = f"PERCENT-COMPLETE:{percent}"
                continue
            if due and line.startswith("DUE"):
                due_str = _date_to_ics(due)
                if isinstance(due, datetime):
                    line = f"DUE:{due_str}"
                else:
                    line = f"DUE;VALUE=DATE:{due_str[:8]}"
                continue
            if categories is not None and line.startswith("CATEGORIES:"):
                line = f"CATEGORIES:{','.join(categories)}"
                continue
            if description is not None and line.startswith("DESCRIPTION:"):
                desc = description.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
                line = f"DESCRIPTION:{desc}"
                continue
            if summary and line.startswith("SUMMARY:"):
                line = f"SUMMARY:{summary}"
                continue

        new_lines.append(line)

    # Update DTSTAMP
    for i, line in enumerate(new_lines):
        if line.startswith("DTSTAMP:") and in_vtodo:
            new_lines[i] = f"DTSTAMP:{_now_utc()}"

    with open(target_file, "w") as f:
        f.write("\n".join(new_lines))

    print(f"✅ Tâche mise à jour : {target_file}")
    if uid:
        print(f"   UID: {uid}")
    print(f"\n📌 Pour synchroniser : vdirsyncer sync zimbra_tasks")
    return target_file


def delete_task(uid=None, summary=None):
    """Delete a VTODO by UID or partial summary match."""
    target_file = None
    if uid:
        path = os.path.join(TASKS_DIR, f"{uid}.ics")
        if os.path.exists(path):
            target_file = path
    if not target_file and summary:
        for f in os.listdir(TASKS_DIR):
            if not f.endswith(".ics"):
                continue
            fp = os.path.join(TASKS_DIR, f)
            with open(fp, "r", errors="replace") as fh:
                content = fh.read()
            if summary.lower() in content.lower():
                target_file = fp
                break

    if not target_file:
        print("❌ Tâche non trouvée.")
        return False

    os.remove(target_file)
    print(f"🗑️ Tâche supprimée : {target_file}")
    print(f"\n📌 Pour synchroniser : vdirsyncer sync zimbra_tasks")
    return True


def list_tasks(status_filter=None, category_filter=None, overdue=False, due_before=None):
    """List tasks with optional filters."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    tasks = []

    for f in sorted(os.listdir(TASKS_DIR)):
        if not f.endswith(".ics"):
            continue
        fp = os.path.join(TASKS_DIR, f)
        with open(fp, "r", errors="replace") as fh:
            content = fh.read()

        for block in content.split("BEGIN:VTODO")[1:]:
            lines = block.strip().split("\n")
            t_summary = t_uid = t_desc = t_status = t_cats = ""
            t_due_str = t_priority = t_percent = ""
            t_remind = ""
            for line in lines:
                s = line.strip()
                if s.startswith("SUMMARY:"):
                    t_summary = s[8:]
                elif s.startswith("UID:"):
                    t_uid = s[4:]
                elif s.startswith("DESCRIPTION:"):
                    t_desc = s[12:]
                elif s.startswith("STATUS:"):
                    t_status = s[7:]
                elif s.startswith("CATEGORIES:"):
                    t_cats = s[11:]
                elif s.startswith("DUE"):
                    t_due_str = s.split(":", 1)[1] if ":" in s else ""
                elif s.startswith("TRIGGER:"):
                    t_remind = s[8:].strip("-P").replace("D", "").replace("T", "J ")
                elif s.startswith("PRIORITY:"):
                    t_priority = s[9:]
                elif s.startswith("PERCENT-COMPLETE:"):
                    t_percent = s[17:]

            if not t_summary:
                continue

            # Parse due date
            due_date = None
            if t_due_str:
                try:
                    if "T" in t_due_str:
                        due_date = datetime.strptime(t_due_str[:15], "%Y%m%dT%H%M%S")
                    else:
                        due_date = datetime.strptime(t_due_str[:8], "%Y%m%d")
                except ValueError:
                    pass

            # Filters
            if status_filter and t_status != status_filter:
                continue
            if category_filter and category_filter not in (t_cats or ""):
                continue
            if overdue and (not due_date or due_date >= datetime.now()):
                continue
            if due_before and (not due_date or due_date > due_before):
                continue

            tasks.append({
                "uid": t_uid, "summary": t_summary, "description": t_desc,
                "status": t_status, "categories": t_cats, "due": due_date,
                "remind": t_remind, "file": fp,
            })

    if not tasks:
        print("Aucune tâche trouvée.")
        return

    # Sort: incomplete first, then by due date
    tasks.sort(key=lambda t: (
        0 if t["status"] != "COMPLETED" else 1,
        t["due"] or datetime(2099, 12, 31),
    ))

    icons = {"COMPLETED": "✅", "NEEDS-ACTION": "⬜", "IN-PROGRESS": "🔄", "CANCELLED": "❌"}
    print(f"📋 TÂCHES ({len(tasks)})\n{'─' * 50}")
    for t in tasks:
        icon = icons.get(t["status"], "⬜")
        cat = f" [{t['categories']}]" if t["categories"] else ""
        due = f" (échéance: {t['due'].strftime('%d/%m/%Y')})" if t["due"] else ""
        pct = f" {t['percent']}%" if t.get("percent") and t["status"] != "COMPLETED" else ""
        rem = f" 🔔{t['remind']}j" if t.get("remind") else ""
        print(f"  {icon} {t['summary']}{cat}{due}{rem}{pct}")
        if t["description"]:
            print(f"     📝 {t['description'][:80]}")
        print(f"     🔑 {t['uid']}")


def detect_task_from_text(subject, body, sender=""):
    """Detect if an email implies a task. Returns (is_task, reason, suggested_due, suggested_categories)."""
    combined = f"{subject} {body}".lower()

    matched_keywords = [kw for kw in TASK_KEYWORDS if kw.lower() in combined]

    if not matched_keywords:
        return False, "", None, []

    # Determine categories based on content
    categories = []
    cat_keywords = {
        "SAÉ": ["saé", "cifor", "simulation", "campus"],
        "Admin": ["administratif", "formulaire", "dossier", "budget", "devis", "facture", "signature", "signer"],
        "Pédagogie": ["cours", "td", "tp", "évaluation", "exam", "mémoire", "stage", "étudiant", "pédagogique"],
        "Recherche": ["recherche", "article", "publication", "conférence", "poster", "rapport"],
    }
    for cat, keywords in cat_keywords.items():
        if any(kw in combined for kw in keywords):
            categories.append(cat)
    if not categories:
        categories = ["Perso"]

    # Try to extract a due date from the email
    import re
    due_date = None
    # Look for patterns like "avant le 25/05", "pour le 25 mai", "deadline: 2026-05-25"
    date_patterns = [
        r'(?:avant|pour|deadline|échéance|date limite)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, combined)
        if match:
            date_str = match.group(1)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m"]:
                try:
                    due_date = datetime.strptime(date_str, fmt)
                    if fmt == "%d/%m":
                        due_date = due_date.replace(year=datetime.now().year)
                    break
                except ValueError:
                    continue
            if due_date:
                break

    reason = f"Mots-clés détectés : {', '.join(matched_keywords[:5])}"
    return True, reason, due_date, categories


def main():
    parser = argparse.ArgumentParser(description="Manage Zimbra tasks (VTODO)")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Create
    p_create = subparsers.add_parser("create", help="Create a new task")
    p_create.add_argument("--summary", required=True, help="Task title")
    p_create.add_argument("--description", default="", help="Task description")
    p_create.add_argument("--due", default=None, help="Due date (YYYY-MM-DD, today, +Nd). Défaut: +3j")
    p_create.add_argument("--priority", type=int, default=5, help="Priority (1-9)")
    p_create.add_argument("--categories", nargs="+", default=None, choices=VALID_CATEGORIES)
    p_create.add_argument("--status", default="NEEDS-ACTION", choices=VALID_STATUSES)
    p_create.add_argument("--remind", type=int, default=DEFAULT_REMIND_DAYS, help=f"N jours avant l'échéance pour le rappel (défaut: {DEFAULT_REMIND_DAYS})")
    p_create.add_argument("--no-reminder", action="store_true", help="Désactiver le rappel VALARM")

    # Update
    p_update = subparsers.add_parser("update", help="Update a task")
    p_update.add_argument("--uid", default=None, help="Task UID")
    p_update.add_argument("--summary", default=None, help="New title (or match string if no UID)")
    p_update.add_argument("--status", default=None, choices=VALID_STATUSES)
    p_update.add_argument("--percent", type=int, default=None, help="Percent complete (0-100)")
    p_update.add_argument("--due", default=None, help="New due date")
    p_update.add_argument("--categories", nargs="+", default=None, choices=VALID_CATEGORIES)
    p_update.add_argument("--description", default=None, help="New description")

    # Delete
    p_delete = subparsers.add_parser("delete", help="Delete a task")
    p_delete.add_argument("--uid", default=None, help="Task UID")
    p_delete.add_argument("--summary", default=None, help="Task title to match")

    # List
    p_list = subparsers.add_parser("list", help="List tasks")
    p_list.add_argument("--status", default=None, choices=VALID_STATUSES, help="Filter by status")
    p_list.add_argument("--category", default=None, choices=VALID_CATEGORIES, help="Filter by category")
    p_list.add_argument("--overdue", action="store_true", help="Show only overdue tasks")
    p_list.add_argument("--due-before", default=None, help="Show tasks due before date (YYYY-MM-DD)")

    # Detect (for email integration)
    p_detect = subparsers.add_parser("detect", help="Detect if an email implies a task")
    p_detect.add_argument("--subject", required=True, help="Email subject")
    p_detect.add_argument("--body", default="", help="Email body")
    p_detect.add_argument("--sender", default="", help="Email sender")

    args = parser.parse_args()

    if args.command == "create":
        due = _parse_date_input(args.due) if args.due else None
        remind = 0 if args.no_reminder else args.remind
        create_task(args.summary, args.description, due, args.priority, args.categories, args.status, remind)

    elif args.command == "update":
        due = _parse_date_input(args.due) if args.due else None
        update_task(args.uid, args.summary, args.status, args.percent, due, args.categories, args.description)

    elif args.command == "delete":
        delete_task(args.uid, args.summary)

    elif args.command == "list":
        due_before = _parse_date_input(args.due_before) if args.due_before else None
        list_tasks(args.status, args.category, args.overdue, due_before)

    elif args.command == "detect":
        is_task, reason, due, cats = detect_task_from_text(args.subject, args.body, args.sender)
        if is_task:
            print(f"📋 TÂCHE DÉTECTÉE")
            print(f"   Raison: {reason}")
            print(f"   Échéance suggérée: {due.strftime('%Y-%m-%d') if due else f'J+{DEFAULT_DUE_DAYS} (défaut)'}")
            print(f"   Catégories suggérées: {', '.join(cats)}")
        else:
            print("Pas de tâche détectée.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
