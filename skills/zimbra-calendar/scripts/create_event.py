#!/usr/bin/env python3
"""
Create a .ics event file in the local Zimbra Calendar directory.
After creation, run: vdirsyncer sync zimbra_cal
"""

import os
import sys
import uuid
import argparse
from datetime import datetime


CALENDAR_DIR = os.path.expanduser("~/.calendars/zimbra/Calendar/Calendar/")


def create_event(date_str, start_time, end_time, summary, description="", location=""):
    os.makedirs(CALENDAR_DIR, exist_ok=True)
    event_uid = str(uuid.uuid4())
    try:
        dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        dtend = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        print(f"❌ Date invalide : «{date_str} {start_time}» — format attendu : YYYY-MM-DD HH:MM")
        return None
    dtstart_ics = dt.strftime("%Y%m%dT%H%M%S")
    dtend_ics = dtend.strftime("%Y%m%dT%H%M%S")
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Hermes//Zimbra//FR
BEGIN:VEVENT
UID:{event_uid}
DTSTAMP:{dtstamp}
DTSTART;TZID="Europe/Brussels":{dtstart_ics}
DTEND;TZID="Europe/Brussels":{dtend_ics}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
END:VCALENDAR
"""
    ics_path = os.path.join(CALENDAR_DIR, f"{event_uid}.ics")
    with open(ics_path, "w") as f:
        f.write(ics_content)
    print(f"✅ Événement créé : {ics_path}")
    print(f"   UID: {event_uid}")
    print(f"   Date: {date_str} {start_time}-{end_time}")
    print(f"   Titre: {summary}")
    print(f"\n📌 Pour synchroniser avec Zimbra, lancer :")
    print(f"   vdirsyncer sync zimbra_cal")
    return ics_path


def main():
    parser = argparse.ArgumentParser(description="Create a Zimbra calendar event")
    parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
    parser.add_argument("--start", required=True, help="Start time (HH:MM)")
    parser.add_argument("--end", required=True, help="End time (HH:MM)")
    parser.add_argument("--summary", required=True, help="Event title")
    parser.add_argument("--description", default="", help="Event description")
    parser.add_argument("--location", default="", help="Event location")
    args = parser.parse_args()
    result = create_event(args.date, args.start, args.end, args.summary, args.description, args.location)
    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
