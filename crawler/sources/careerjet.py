"""Careerjet Job-API (Publisher-Schnittstelle, Schlüssel unter https://www.careerjet.com/partners).

Benötigt die Umgebungsvariable CAREERJET_API_KEY (auf GitHub als „Secret“).

Wichtig: Careerjet verlangt bei jeder Anfrage die IP-Adresse und den Browser (User-Agent) des
Besuchers, der die Suche auslöst. Die API ist für Live-Suchen gedacht, nicht für nächtliches
Sammeln. Deshalb ist diese Quelle in sources.yaml standardmässig AUS. Einschalten erst, wenn
Careerjet bestätigt hat, dass Jobmap die Resultate so abholen und zwischenspeichern darf.
"""
from __future__ import annotations

import email.utils
import os

from common import Http, clean_text, log

API = "https://search.api.careerjet.net/v4/query"
PERIOD = {"Y": "year", "M": "month", "W": "week", "D": "day", "H": "hour"}


def _date(v):
    if not v:
        return None
    s = str(v)
    if s[:4].isdigit():
        return s  # bereits ISO
    try:
        return email.utils.parsedate_to_datetime(s).isoformat()
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        f = float(str(v).replace("'", "").replace(",", ""))
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def fetch(http: Http, cfg: dict) -> list[dict]:
    key = os.environ.get("CAREERJET_API_KEY")
    if not key:
        log.info("Careerjet übersprungen: CAREERJET_API_KEY fehlt.")
        return []
    page_size = min(int(cfg.get("page_size", 100)), 100)
    budget = int(cfg.get("max_requests", 60))
    user_ip = cfg.get("user_ip", "")          # IP, die bei Careerjet angegeben wird
    user_agent = cfg.get("user_agent_visitor", "Mozilla/5.0 (JobmapBot nightly update)")
    out: list[dict] = []
    for locale in cfg.get("locales") or ["de_CH"]:
        for where in cfg.get("locations") or [""]:
            offset = 0
            while offset <= 900 and budget > 0:
                budget -= 1
                params = {"locale_code": locale, "location": where, "keywords": cfg.get("keywords", ""),
                          "sort": "date", "page_size": page_size, "offset": offset,
                          "user_ip": user_ip, "user_agent": user_agent}
                data = http.get_json(API, params=params, auth=(key, ""), headers={"Referer": cfg.get("referer", "")})
                if not data:
                    break
                if data.get("type") and str(data["type"]).upper() != "JOBS":
                    log.info("Careerjet: Ort %r mehrdeutig oder unbekannt – übersprungen.", where)
                    break
                jobs = data.get("jobs") or []
                for x in jobs:
                    loc = x.get("locations") or ""
                    if isinstance(loc, list):
                        loc = ", ".join(map(str, loc))
                    out.append({
                        "source": "Careerjet",
                        "source_id": f"careerjet:{x.get('url')}",
                        "title": clean_text(x.get("title")),
                        "company": clean_text(x.get("company")) or "Unbekannte Firma",
                        "url": x.get("url"),
                        "location": loc,
                        "city": loc.split(",")[0].strip() if loc else "",
                        "posted": _date(x.get("date")),
                        "salary_min": _num(x.get("salary_min")),
                        "salary_max": _num(x.get("salary_max")),
                        "salary_period": PERIOD.get(str(x.get("salary_type") or "Y").upper()[:1], "year")
                                         if (x.get("salary_currency_code") or "CHF") == "CHF" else "unknown",
                        "employment_raw": " ".join(filter(None, [x.get("contract_type"), x.get("contract_period")])),
                        "contract_time": x.get("contract_period") or x.get("work_hours") or "",
                        "description": clean_text(x.get("description"), 600),
                    })
                log.info("Careerjet %s %s ab %s: %s Stellen", locale, where or "Schweiz", offset, len(jobs))
                if len(jobs) < page_size:
                    break
                offset += page_size
    if budget <= 0:
        log.info("Careerjet: Anfrage-Budget aufgebraucht.")
    return out
