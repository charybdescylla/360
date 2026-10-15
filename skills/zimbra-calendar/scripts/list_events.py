#!/usr/bin/env python3
"""
List events from Zimbra calendars stored as local .ics files.
Handles UTC→local timezone conversion (Europe/Brussels).
"""

import os
import glob
import sys
import subprocess
import argparse
from datetime import datetime, timedelta, timezone

# ── Sync avant lecture ─────────────────────────────────────────────────────────
# Les copies locales .ics peuvent être périmées si la synchro CalDAV n'a pas été
# faite récemment → on RATERAIT des événements/tâches que le serveur Zimbra
# montre pourtant à jour. On synchronise donc avant de lire.
#   - best-effort : en cas de pépin on lit quand même la copie locale.
#   - désactivable : ZV_SKIP_SYNC=1 (pour les exécutions qui doivent rester
#     ultra-rapides / offline).
SYNC_SCRIPT = os.path.expanduser("~/.hermes/skills/zimbra-calendar/scripts/sync_calendars.sh")

def _sync_before_read():
    if os.environ.get("ZV_SKIP_SYNC"):
        return
    if not os.path.exists(SYNC_SCRIPT):
        return
    try:
        r = subprocess.run([SYNC_SCRIPT], capture_output=True, text=True, timeout=180)
        if r.returncode != 0 and r.stdout:
            last = r.stdout.strip().splitlines()[-1]
            sys.stderr.write(f"[sync] Synchronisation CalDAV : {last}\n")
    except Exception as e:
        sys.stderr.write(f"[sync] indisponible : {e}\n")

_sync_before_read()


def get_local_tz(dt):
    """Return timezone offset for Europe/Brussels (DST aware)."""
    year = dt.year
    mar31 = datetime(year, 3, 31)
    dst_start = mar31 - timedelta(days=(mar31.weekday() + 1) % 7)
    dst_start = dst_start.replace(hour=2, minute=0, second=0)
    oct31 = datetime(year, 10, 31)
    dst_end = oct31 - timedelta(days=(oct31.weekday() + 1) % 7)
    dst_end = dst_end.replace(hour=3, minute=0, second=0)
    if dst_start <= dt.replace(tzinfo=None) < dst_end:
        return timezone(timedelta(hours=2))
    return timezone(timedelta(hours=1))


CALENDARS = {
    "Calendar": "~/.calendars/zimbra/Calendar/",
    "Tasks": "~/.calendars/zimbra/Tasks/",
    "ADE": "~/.calendars/zimbra/ADE/",
    "M1IPN": "~/.calendars/zimbra/M1IPN/",
    "M2IPN": "~/.calendars/zimbra/M2IPN/",
}


def parse_ics_date(dt_str):
    """Parse an ics date/datetime string, return datetime (tz-aware for display, naive for date-only)."""
    dt_str = dt_str.strip()
    if "TZID=" in dt_str:
        dt_str = dt_str.split(":", 1)[1]
    if "T" in dt_str:
        clean = dt_str.replace("Z", "")
        try:
            dt = datetime.strptime(clean[:15], "%Y%m%dT%H%M%S")
        except ValueError:
            return None
        if dt_str.endswith("Z"):
            dt = dt.replace(tzinfo=timezone.utc)
            local_tz = get_local_tz(dt)
            dt = dt.astimezone(local_tz)
        else:
            local_tz = get_local_tz(dt)
            dt = dt.replace(tzinfo=local_tz)
        return dt
    else:
        # Date-only (VALUE=DATE) — return naive datetime for safe comparison
        try:
            return datetime.strptime(dt_str[:8], "%Y%m%d")
        except ValueError:
            return None


def parse_vtodo(block):
    """Parse a VTODO block, return dict or None."""
    lines = block.strip().split("\n")
    summary = uid = description = status = location = categories = ""
    dtstart_str = due_str = completed_str = ""
    priority = 0
    percent = 0
    for line in lines:
        s = line.strip()
        if s.startswith("SUMMARY:"):
            summary = s[8:]
        elif s.startswith("UID:"):
            uid = s[4:]
        elif s.startswith("DESCRIPTION:"):
            description = s[12:]
        elif s.startswith("STATUS:"):
            status = s[7:]
        elif s.startswith("LOCATION:"):
            location = s[9:]
        elif s.startswith("CATEGORIES:"):
            categories = s[11:]
        elif s.startswith("DTSTART"):
            dtstart_str = s.split(":", 1)[1] if ":" in s else ""
        elif s.startswith("DUE"):
            due_str = s.split(":", 1)[1] if ":" in s else ""
        elif s.startswith("COMPLETED"):
            completed_str = s.split(":", 1)[1] if ":" in s else ""
        elif s.startswith("PRIORITY:"):
            try:
                priority = int(s[9:])
            except ValueError:
                priority = 0
        elif s.startswith("PERCENT-COMPLETE:"):
            try:
                percent = int(s[17:])
            except ValueError:
                percent = 0
    if not summary:
        return None
    dt = None
    for src in [dtstart_str, due_str, completed_str]:
        if src:
            dt = parse_ics_date(src)
            if dt:
                # Normalize to naive for safe comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                break
    return {
        "uid": uid, "summary": summary, "description": description,
        "status": status or "NEEDS-ACTION", "location": location,
        "categories": categories, "dt": dt, "due_str": due_str,
        "priority": priority, "percent": percent,
    }


def list_events(date_from, date_to, calendar_filter=None, include_tasks=True):
    all_events = []
    all_tasks = []
    for cal_name, cal_path in CALENDARS.items():
        if calendar_filter and cal_name != calendar_filter:
            continue
        base = os.path.expanduser(cal_path)
        for ics_file in glob.glob(f"{base}/**/*.ics", recursive=True):
            with open(ics_file, "r", errors="replace") as f:
                content = f.read()
            # Parse VEVENT
            for block in content.split("BEGIN:VEVENT")[1:]:
                lines = block.strip().split("\n")
                summary = dtstart_str = dtend_str = location = uid = ""
                for line in lines:
                    s = line.strip()
                    if s.startswith("SUMMARY:"):
                        summary = s[8:]
                    elif s.startswith("DTSTART"):
                        dtstart_str = s.split(":", 1)[1] if ":" in s else ""
                    elif s.startswith("DTEND"):
                        dtend_str = s.split(":", 1)[1] if ":" in s else ""
                    elif s.startswith("LOCATION:"):
                        location = s[9:]
                    elif s.startswith("UID:"):
                        uid = s[4:]
                if not dtstart_str:
                    continue
                dt = parse_ics_date(dtstart_str)
                if dt is None:
                    continue
                # Normalize to naive for safe comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                event_date = dt.replace(hour=0, minute=0, second=0)
                if date_from <= event_date <= date_to:
                    dtend = parse_ics_date(dtend_str) if dtend_str else None
                    if dtend and dtend.tzinfo is not None:
                        dtend = dtend.replace(tzinfo=None)
                    all_events.append({
                        "cal": cal_name, "dt": dt, "dtend": dtend,
                        "summary": summary, "location": location,
                        "uid": uid, "file": ics_file,
                    })
            # Parse VTODO
            if include_tasks:
                for block in content.split("BEGIN:VTODO")[1:]:
                    todo = parse_vtodo(block)
                    if todo is None:
                        continue
                    todo["cal"] = cal_name
                    todo["file"] = ics_file
                    # Filter by date: use dtstart, due, or completed date
                    if todo["dt"]:
                        td = todo["dt"]
                        if td.tzinfo is not None:
                            td = td.replace(tzinfo=None)
                        task_date = td.replace(hour=0, minute=0, second=0)
                        if date_from <= task_date <= date_to:
                            all_tasks.append(todo)
                    else:
                        # Tasks with no date always show
                        all_tasks.append(todo)
    all_events.sort(key=lambda x: x["dt"])
    all_tasks.sort(key=lambda x: (x["dt"] or datetime(2099, 12, 31), x["priority"]))
    return all_events, all_tasks


def format_events(events, tasks=None):
    output = []
    if events:
        current_date = None
        for ev in events:
            date_str = ev["dt"].strftime("%A %d/%m/%Y")
            if date_str != current_date:
                current_date = date_str
                output.append(f"\n{date_str}\n{'-'*50}")
            time_str = ev["dt"].strftime("%H:%M")
            end_str = f"-{ev['dtend'].strftime('%H:%M')}" if ev["dtend"] else ""
            loc = f" 📍{ev['location']}" if ev["location"] else ""
            output.append(f"  {time_str}{end_str} [{ev['cal']}] {ev['summary']}{loc}")
    if tasks:
        if output:
            output.append("")
        output.append("📋 TÂCHES")
        output.append("-" * 50)
        for t in tasks:
            status_icon = {"COMPLETED": "✅", "NEEDS-ACTION": "⬜", "IN-PROGRESS": "🔄", "CANCELLED": "❌"}.get(t["status"], "⬜")
            cat = f" [{t['categories']}]" if t["categories"] else ""
            due = f" (échéance: {t['dt'].strftime('%d/%m/%Y')})" if t["dt"] else ""
            pct = f" {t['percent']}%" if t.get("percent", 0) > 0 and t["status"] != "COMPLETED" else ""
            output.append(f"  {status_icon} {t['summary']}{cat}{due}{pct}")
            if t.get("description"):
                output.append(f"     📝 {t['description'][:80]}")
    total = len(events) + (len(tasks) if tasks else 0)
    output.append(f"\nTotal: {total} élément(s)")
    return "\n".join(output) if output else "Aucun élément trouvé."


def main():
    parser = argparse.ArgumentParser(description="List Zimbra calendar events and tasks")
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument("--calendar", default=None)
    parser.add_argument("--no-tasks", action="store_true", help="Exclude tasks from output")
    args = parser.parse_args()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_from = today if args.date_from in (None, "today") else datetime.strptime(args.date_from, "%Y-%m-%d")
    date_to = today + timedelta(days=7) if args.date_to in (None, "today") else datetime.strptime(args.date_to, "%Y-%m-%d")
    events, tasks = list_events(date_from, date_to, args.calendar, include_tasks=not args.no_tasks)
    print(format_events(events, tasks if not args.no_tasks else None))

if __name__ == "__main__":
    main()
