"""Jooble Partner-API (Schlüssel gratis über https://jooble.org/api/about).

Benötigt die Umgebungsvariable JOOBLE_API_KEY (auf GitHub als „Secret“).
Anfrage: POST {base_url}/api/<Schlüssel> mit JSON {keywords, location, page, ResultOnPage}.
Antwort: {"totalCount": …, "jobs": [{title, location, snippet, salary, source, type, link, company, updated, id}]}
"""
from __future__ import annotations

import os
import re

from common import Http, clean_text, log

NUM = re.compile(r"\d[\d'’ .,]*\d|\d")


def _salary(text: str):
    """Liest „CHF 80'000 – 95'000 pro Jahr“ o. ä. aus. Gibt (min, max, Periode) oder (None, None, None)."""
    if not text:
        return None, None, None
    t = text.lower()
    if "€" in t or "eur" in t or "$" in t:
        return None, None, None
    vals = []
    for m in NUM.findall(text):
        digits = re.sub(r"[^\d]", "", m)
        if digits:
            vals.append(float(digits))
    vals = [v for v in vals if v >= 10]
    if not vals:
        return None, None, None
    if re.search(r"stunde|hour|/h\b|heure", t):
        return None, None, None
    period = "month" if re.search(r"monat|month|mois|/mt|mtl", t) else "year"
    if period == "year" and max(vals) < 15000:
        period = "month"
    return min(vals), max(vals), period


def fetch(http: Http, cfg: dict) -> list[dict]:
    key = os.environ.get("JOOBLE_API_KEY")
    if not key:
        log.info("Jooble übersprungen: JOOBLE_API_KEY fehlt.")
        return []
    base = (cfg.get("base_url") or "https://ch.jooble.org").rstrip("/")
    per_page = int(cfg.get("results_per_page", 50))
    budget = int(cfg.get("max_requests", 60))
    out: list[dict] = []
    for where in cfg.get("locations") or ["Schweiz"]:
        for page in range(1, int(cfg.get("max_pages_per_location", 5)) + 1):
            if budget <= 0:
                log.info("Jooble: Anfrage-Budget aufgebraucht.")
                return out
            budget -= 1
            body = {"keywords": cfg.get("keywords", ""), "location": where,
                    "page": str(page), "ResultOnPage": str(per_page)}
            r = http.get(f"{base}/api/{key}", method="POST", json_body=body)
            if r is None:
                break
            try:
                data = r.json()
            except ValueError:
                log.warning("Jooble: keine gültige Antwort für %s", where)
                break
            jobs = data.get("jobs") or []
            for x in jobs:
                lo, hi, per = _salary(x.get("salary") or "")
                loc = x.get("location") or ""
                out.append({
                    "source": "Jooble",
                    "source_id": f"jooble:{x.get('id') or x.get('link')}",
                    "title": clean_text(x.get("title")),
                    "company": clean_text(x.get("company")) or "Unbekannte Firma",
                    "url": x.get("link"),
                    "location": loc,
                    "city": loc.split(",")[0].strip(),
                    "posted": x.get("updated"),
                    "salary_min": lo, "salary_max": hi, "salary_period": per,
                    "employment_raw": x.get("type") or "",
                    "contract_time": x.get("type") or "",
                    "description": clean_text(x.get("snippet"), 600),
                })
            log.info("Jooble %s Seite %s: %s Stellen", where, page, len(jobs))
            if len(jobs) < per_page:
                break
    return out
