"""Adzuna Job-API (offizielle Schnittstelle, gratis Schlüssel auf https://developer.adzuna.com).

Benötigt die Umgebungsvariablen ADZUNA_APP_ID und ADZUNA_APP_KEY (auf GitHub als „Secrets“).
Bedingung von Adzuna: Die Seite zeigt „Jobs by Adzuna“ mit Link an (macht Jobmap automatisch).
"""
from __future__ import annotations

import os

from common import Http, clean_text, log

API = "https://api.adzuna.com/v1/api/jobs/ch/search/{page}"


def fetch(http: Http, cfg: dict) -> list[dict]:
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.info("Adzuna übersprungen: ADZUNA_APP_ID / ADZUNA_APP_KEY fehlen.")
        return []
    per_page = 50
    out: list[dict] = []
    queries = cfg.get("queries") or [{}]
    budget = int(cfg.get("max_requests", 40))
    for q in queries:
        for page in range(1, int(cfg.get("max_pages_per_query", 20)) + 1):
            if budget <= 0:
                log.info("Adzuna: Anfrage-Budget aufgebraucht.")
                return out
            budget -= 1
            params = {"app_id": app_id, "app_key": app_key, "results_per_page": per_page,
                      "max_days_old": cfg.get("max_days_old", 30), "sort_by": "date"}
            params.update({k: v for k, v in q.items() if v})
            data = http.get_json(API.format(page=page), params=params)
            results = (data or {}).get("results") or []
            for x in results:
                sal_ok = str(x.get("salary_is_predicted", "0")) == "0"
                loc = x.get("location") or {}
                area = loc.get("area") or []
                out.append({
                    "source": "Adzuna",
                    "source_id": f"adzuna:{x.get('id')}",
                    "title": clean_text(x.get("title")),
                    "company": clean_text((x.get("company") or {}).get("display_name")) or "Unbekannte Firma",
                    "url": x.get("redirect_url"),
                    "location": loc.get("display_name") or "",
                    "city": area[-1] if len(area) > 1 else "",
                    "lat": x.get("latitude"), "lon": x.get("longitude"),
                    "posted": x.get("created"),
                    "salary_min": x.get("salary_min") if sal_ok else None,
                    "salary_max": x.get("salary_max") if sal_ok else None,
                    "salary_period": "year",
                    "employment_raw": " ".join(filter(None, [x.get("contract_type"), x.get("contract_time")])),
                    "contract_time": x.get("contract_time"),
                    "category_hint": (x.get("category") or {}).get("tag"),
                    "description": clean_text(x.get("description"), 600),
                })
            log.info("Adzuna %s Seite %s: %s Stellen", q or "alle", page, len(results))
            if len(results) < per_page:
                break
    return out
