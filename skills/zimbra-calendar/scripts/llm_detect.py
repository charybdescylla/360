#!/usr/bin/env python3
"""
LLM-based task detection for emails.
Par défaut utilise AJEAN (OpenAI-compatible) sur la machine locale.
Repli automatique sur Ollama réseau si AJEAN est injoignable.
"""

import json
import os
import urllib.request
import urllib.error
import re
from datetime import datetime, timedelta

# ── Backend LLM (défaut : AJEAN OpenAI-compatible, depuis 2026-08-31) ───────
# Surchargeable via env : LLM_ENDPOINT, LLM_MODEL, LLM_PROTOCOL, OLLAMA_FALLBACK_URL.
OLLAMA_URL = os.environ.get("LLM_ENDPOINT", "http://172.22.242.84:8080/v1").rstrip("/")
OLLAMA_MODEL = os.environ.get("LLM_MODEL", "qwen3.8")
LLM_PROTOCOL = os.environ.get("LLM_PROTOCOL", "auto").strip().lower()
if LLM_PROTOCOL == "auto":
    LLM_PROTOCOL = "openai" if OLLAMA_URL.endswith("/v1") else "ollama"
FALLBACK_URL = os.environ.get("OLLAMA_FALLBACK_URL", "http://172.22.242.12:11435").rstrip("/")
FALLBACK_MODEL = os.environ.get("OLLAMA_FALLBACK_MODEL", "qwen3.8_256k:latest")
VALID_CATEGORIES = ["SAÉ", "Admin", "Pédagogie", "Recherche", "Perso"]

TASK_DETECTION_PROMPT = """Classifie cet email: est-ce une tâche à traiter ou pas?

Une tâche = action concrète de production, modification, validation ou suivi d'un document/livrable.
Pas une tâche = simple info, réponse courte oui/non, invitation réunion, spam, notification automatique.

Réponds UNIQUEMENT avec un objet JSON valide (sans markdown, sans commentaires, sans texte autour):
{{"is_task":true, "reason":"explication courte", "due_date":"YYYY-MM-DD ou null", "categories":["SAÉ ou Admin ou Pédagogie ou Recherche ou Perso"], "priority":5, "confiance":0.9}}

Email:
- De: {sender}
- Sujet: {subject}
- Corps: {body}"""


def call_ollama(prompt, timeout=120):
    """Call the configured LLM backend (AJEAN OpenAI / Ollama natif).
    Acec repli automatique : if AJEAN down -> Ollama réseau (OLLAMA_FALLBACK_URL)."""
    import urllib.request
    import urllib.error

    def _post(url, payload, timeout):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _openai_url(base):
        b = base.rstrip("/")
        return f"{b}/v1/chat/completions" if not b.endswith("/v1") else f"{b}/chat/completions"

    # Backend principal (AJEAN).
    try:
        if LLM_PROTOCOL == "ollama":
            payload = {
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 4096},
            }
            data = _post(f"{OLLAMA_URL}/api/generate", payload, timeout)
            return data.get("response", "").strip()
        else:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096, "temperature": 0.1, "stream": False,
            }
            data = _post(_openai_url(OLLAMA_URL), payload, timeout)
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # Repli : Ollama réseau.
        try:
            payload = {
                "model": FALLBACK_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 4096},
            }
            data = _post(f"{FALLBACK_URL}/api/generate", payload, timeout)
            return data.get("response", "").strip()
        except Exception as e2:
            return None


def parse_llm_response(raw):
    """Parse LLM JSON response, handling various formats."""
    if not raw:
        return None
    text = raw.strip()

    # Remove markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
        else:
            text = parts[-1].strip()

    # Remove // comments that Llama sometimes adds
    text = re.sub(r'//[^\n]*', '', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


def detect_task_with_llm(subject, body, sender=""):
    """Use LLM to detect if an email implies a task. Returns dict or None."""
    body_truncated = body[:1200] if body else "(pas de corps)"
    sender_str = sender or "(inconnu)"

    prompt = TASK_DETECTION_PROMPT.format(
        sender=sender_str,
        subject=subject,
        body=body_truncated
    )

    raw = call_ollama(prompt)
    if not raw:
        return None

    result = parse_llm_response(raw)
    if not result:
        return None

    # Validate and normalize
    if not result.get("is_task", False):
        return {"is_task": False, "reason": result.get("reason", ""), "confiance": result.get("confiance", 0)}

    # Parse due date
    due_date = None
    due_str = result.get("due_date")
    if due_str and due_str != "null" and due_str.lower() != "none":
        try:
            due_date = datetime.strptime(due_str[:10], "%Y-%m-%d")
        except ValueError:
            pass

    # Validate categories
    cats = result.get("categories", [])
    if isinstance(cats, str):
        cats = [cats]
    valid_cats = [c for c in cats if c in VALID_CATEGORIES]
    if not valid_cats:
        valid_cats = ["Perso"]

    # Validate priority
    try:
        priority = int(result.get("priority", 5))
        priority = max(1, min(9, priority))
    except (ValueError, TypeError):
        priority = 5

    return {
        "is_task": True,
        "reason": result.get("reason", ""),
        "due_date": due_date,
        "categories": valid_cats,
        "priority": priority,
        "confiance": float(result.get("confiance", 0.5)),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--sender", default="")
    args = parser.parse_args()

    result = detect_task_with_llm(args.subject, args.body, args.sender)
    if result:
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    else:
        print("❌ Erreur LLM")
