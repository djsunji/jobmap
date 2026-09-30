"""Öffentliche Stellen-Feeds von Bewerbungssystemen (ATS).

Viele Firmen nutzen ein Bewerbungssystem, das ihre offenen Stellen über eine öffentliche
Schnittstelle bereitstellt – genau dafür gedacht, dass die Stellen auf anderen Seiten erscheinen.
Unterstützt: Greenhouse, Lever, SmartRecruiters, Personio, Recruitee.

Den „slug“ einer Firma findest du in der Adresse ihrer Stellenseite, z. B.
  boards.greenhouse.io/<slug>        jobs.lever.co/<slug>        careers.smartrecruiters.com/<slug>
  <slug>.jobs.personio.de            <slug>.recruitee.com
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET

from common import Http, clean_text, log


def _iso_ms(ms):
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, tz=dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def greenhouse(http: Http, slug: str, name: str) -> list[dict]:
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    out = []
    for j in (data or {}).get("jobs", []):
        out.append({"source": name, "source_id": f"gh:{slug}:{j.get('id')}", "title": clean_text(j.get("title")),
                    "company": name, "url": j.get("absolute_url"), "location": (j.get("location") or {}).get("name", ""),
                    "posted": j.get("first_published") or j.get("updated_at"),
                    "description": clean_text(j.get("content"), 600)})
    return out


def lever(http: Http, slug: str, name: str) -> list[dict]:
    data = http.get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    out = []
    for j in data or []:
        c = j.get("categories") or {}
        out.append({"source": name, "source_id": f"lever:{slug}:{j.get('id')}", "title": clean_text(j.get("text")),
                    "company": name, "url": j.get("hostedUrl"), "location": c.get("location", ""),
                    "posted": _iso_ms(j.get("createdAt")), "employment_raw": c.get("commitment", ""),
                    "contract_time": c.get("commitment", ""), "remote": (j.get("workplaceType") == "remote") or None,
                    "description": clean_text(j.get("descriptionPlain"), 600)})
    return out


def smartrecruiters(http: Http, slug: str, name: str) -> list[dict]:
    out, offset = [], 0
    while True:
        data = http.get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                             params={"limit": 100, "offset": offset, "country": "ch"})
        items = (data or {}).get("content", [])
        for j in items:
            loc = j.get("location") or {}
            out.append({"source": name, "source_id": f"sr:{slug}:{j.get('id')}", "title": clean_text(j.get("name")),
                        "company": (j.get("company") or {}).get("name") or name,
                        "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                        "city": loc.get("city", ""), "postal_code": loc.get("postalCode", ""),
                        "location": ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")])),
                        "posted": j.get("releasedDate"),
                        "employment_raw": (j.get("typeOfEmployment") or {}).get("label", ""),
                        "contract_time": (j.get("typeOfEmployment") or {}).get("label", ""),
                        "remote": loc.get("remote") or None})
        offset += 100
        if len(items) < 100 or offset > 2000:
            break
    return out


def personio(http: Http, slug: str, name: str) -> list[dict]:
    out = []
    for tld in ("de", "com"):
        text = http.get_text(f"https://{slug}.jobs.personio.{tld}/xml", params={"language": "de"})
        if not text:
            continue
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            continue
        for p in root.iter("position"):
            g = lambda k: (p.findtext(k) or "").strip()  # noqa: E731
            desc = " ".join(clean_text(d.findtext("value")) for d in p.iter("jobDescription"))
            out.append({"source": name, "source_id": f"personio:{slug}:{g('id')}", "title": clean_text(g("name")),
                        "company": g("subcompany") or name, "url": f"https://{slug}.jobs.personio.{tld}/job/{g('id')}",
                        "location": g("office"), "city": g("office"), "posted": g("createdAt"),
                        "employment_raw": f"{g('employmentType')} {g('schedule')}", "contract_time": g("schedule"),
                        "description": clean_text(desc, 600)})
        break
    return out


def recruitee(http: Http, slug: str, name: str) -> list[dict]:
    data = http.get_json(f"https://{slug}.recruitee.com/api/offers/")
    out = []
    for j in (data or {}).get("offers", []):
        if j.get("country_code") and j.get("country_code") != "CH":
            continue
        out.append({"source": name, "source_id": f"recruitee:{slug}:{j.get('id')}", "title": clean_text(j.get("title")),
                    "company": j.get("company_name") or name, "url": j.get("careers_url"),
                    "city": j.get("city", ""), "postal_code": j.get("postal_code", ""), "location": j.get("location", ""),
                    "posted": j.get("published_at") or j.get("created_at"),
                    "employment_raw": j.get("employment_type_code", ""), "remote": j.get("remote") or None,
                    "description": clean_text(j.get("description"), 600)})
    return out


HANDLERS = {"greenhouse": greenhouse, "lever": lever, "smartrecruiters": smartrecruiters,
            "personio": personio, "recruitee": recruitee}


def fetch(http: Http, companies: list[dict]) -> list[dict]:
    out = []
    for c in companies or []:
        h = HANDLERS.get((c.get("ats") or "").lower())
        if not h or not c.get("slug"):
            log.warning("Unbekannter Eintrag in ats_companies: %s", c)
            continue
        try:
            jobs = h(http, c["slug"], c.get("name") or c["slug"])
            if c.get("logo"):
                for j in jobs:
                    j["logo"] = c["logo"]
            log.info("%s (%s): %s Stellen", c.get("name"), c["ats"], len(jobs))
            out += jobs
        except Exception as e:  # eine kaputte Quelle soll den Rest nicht stoppen
            log.warning("Fehler bei %s: %s", c.get("name"), e)
    return out
