#!/usr/bin/env python3
"""
Create a Zimbra task from an email using LLM-based task detection.
Usage:
  himalaya message read <id> -o json | python3 email_to_task.py
  himalaya message read <id> -o json | python3 email_to_task.py --auto
  python3 email_to_task.py --subject "..." --body "..." [--auto]

With --auto, creates the task directly if detected.
Without --auto, shows the detection result for confirmation.
"""

import sys
import json
import argparse
import subprocess
import re
from datetime import datetime, timedelta

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manage_task import create_task, _parse_date_input
from llm_detect import detect_task_with_llm


def read_email_from_himalaya(message_id):
    """Read email via himalaya and return (subject, body, sender)."""
    try:
        result = subprocess.run(
            ["himalaya", "message", "read", message_id, "-o", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"❌ Erreur himalaya: {result.stderr[:200]}", file=sys.stderr)
            return None, None, None

        raw = result.stdout.strip()

        # Try parsing as JSON first (newer himalaya versions)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                subject = data.get("subject", "")
                body = data.get("body", data.get("plain", data.get("html", "")))
                sender = ""
                if "from" in data:
                    f = data["from"]
                    if isinstance(f, dict):
                        sender = f.get("name", f.get("email", ""))
                    elif isinstance(f, list) and f:
                        sender = f[0].get("name", f[0].get("email", ""))
                return subject, body, sender
        except json.JSONDecodeError:
            pass

        # Fallback: parse raw email text format
        subject = ""
        sender = ""
        body_lines = []
        in_body = False
        for line in raw.split("\n"):
            if line.startswith("From:"):
                sender = line[5:].strip()
                # Extract name from "Name <email>"
                match = re.match(r'"?([^"<]+)"?\s*<', sender)
                if match:
                    sender = match.group(1).strip()
            elif line.startswith("Subject:"):
                subject = line[8:].strip()
            elif line.strip() == "" and not in_body:
                in_body = True
            elif in_body:
                body_lines.append(line)

        body = "\n".join(body_lines).strip()
        return subject, body, sender

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return None, None, None


def main():
    parser = argparse.ArgumentParser(description="Create a Zimbra task from an email (LLM-based detection)")
    parser.add_argument("--message-id", default=None, help="Himalaya message ID to read")
    parser.add_argument("--subject", default=None, help="Email subject (manual input)")
    parser.add_argument("--body", default="", help="Email body (manual input)")
    parser.add_argument("--sender", default="", help="Email sender (manual input)")
    parser.add_argument("--auto", action="store_true", help="Auto-create without confirmation")
    parser.add_argument("--due", default=None, help="Override due date (YYYY-MM-DD, +Nd)")
    parser.add_argument("--categories", nargs="+", default=None, help="Override categories")
    parser.add_argument("--priority", type=int, default=None, help="Override priority (1-9)")
    args = parser.parse_args()

    subject = args.subject
    body = args.body
    sender = args.sender

    if args.message_id and not args.subject:
        subject, body, sender = read_email_from_himalaya(args.message_id)
        if not subject:
            print("❌ Impossible de lire l'email.")
            sys.exit(1)

    if not subject:
        if not sys.stdin.isatty():
            try:
                data = json.load(sys.stdin)
                subject = data.get("subject", "")
                body = data.get("body", data.get("plain", data.get("html", "")))
                if "from" in data:
                    f = data["from"]
                    if isinstance(f, dict):
                        sender = f.get("name", f.get("email", ""))
                    elif isinstance(f, list) and f:
                        sender = f[0].get("name", f[0].get("email", ""))
            except json.JSONDecodeError:
                print("❌ Impossible de parser l'entrée JSON.", file=sys.stderr)
                sys.exit(1)

    if not subject:
        print("❌ Aucun sujet fourni.", file=sys.stderr)
        sys.exit(1)

    # LLM-based detection
    print(f"🔍 Analyse LLM de l'email : \"{subject[:60]}...\"", file=sys.stderr)
    result = detect_task_with_llm(subject, body, sender)

    if not result:
        print("❌ Erreur lors de l'analyse LLM.", file=sys.stderr)
        sys.exit(1)

    if not result.get("is_task", False):
        print(f"ℹ️ Pas de tâche détectée : {result.get('reason', '')} (confiance: {result.get('confiance', 0):.0%})")
        sys.exit(0)

    # Determine due date
    if args.due:
        due = _parse_date_input(args.due)
    elif result.get("due_date"):
        due = result["due_date"]
    else:
        due = datetime.now() + timedelta(days=3)  # défaut J+3 (décision Xavier 04/09/2026)

    categories = args.categories or result.get("categories", ["Perso"])
    priority = args.priority or result.get("priority", 5)
    confiance = result.get("confiance", 0)

    # Build summary from subject
    summary = f"[Mail] {subject[:80]}"

    # Build description
    desc_parts = [f"De: {sender}"] if sender else []
    desc_parts.append(f"Sujet: {subject}")
    if body:
        clean_body = body[:500].replace("\n", " ").strip()
        desc_parts.append(f"Extrait: {clean_body}")
    desc_parts.append(f"\nAnalyse LLM: {result.get('reason', '')} (confiance: {confiance:.0%})")
    description = "\n".join(desc_parts)

    print(f"📋 TÂCHE DÉTECTÉE")
    print(f"   Sujet: {subject[:80]}")
    print(f"   De: {sender}")
    print(f"   Raison: {result.get('reason', '')}")
    print(f"   Confiance: {confiance:.0%}")
    print(f"   Échéance: {due.strftime('%Y-%m-%d') if hasattr(due, 'strftime') else due}")
    print(f"   Catégories: {', '.join(categories)}")
    print(f"   Priorité: {priority}")

    if args.auto:
        create_task(summary, description, due, priority=priority, categories=categories)
    else:
        print(f"\n   Titre: {summary}")
        print(f"\n   Pour créer : ajouter --auto")
        print(f"   Pour ajouter une échéance : --due YYYY-MM-DD")
        print(f"   Pour changer les catégories : --categories SAÉ Admin Pédagogie")


if __name__ == "__main__":
    main()
