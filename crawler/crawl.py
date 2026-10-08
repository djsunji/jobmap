#!/usr/bin/env python3
"""Jobmap-Crawler: holt Stellen aus erlaubten Quellen und schreibt data/jobs.json für die Website.

Aufruf:  python crawler/crawl.py            (Einstellungen in crawler/sources.yaml)
         python crawler/crawl.py --dry-run  (nur zählen, nichts speichern)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from classify import classify, employment_type, level, pensum, work_mode  # noqa: E402
from common import ROOT, Http, log, norm  # noqa: E402
from geocode import Geocoder  # noqa: E402
from sources import adzuna, ats, careerjet, jooble, jsonld  # noqa: E402

CH_BOX = (45.8, 47.9, 5.9, 10.6)  # lat min/max, lon min/max


def in_ch(lat, lon) -> bool:
    try:
        return CH_BOX[0] <= float(lat) <= CH_BOX[1] and CH_BOX[2] <= float(lon) <= CH_BOX[3]
    except (TypeError, ValueError):
        return False


def parse_date(v):
    if not v:
        return None
    try:
        s = str(v).strip().replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(s) if "T" in s or len(s) > 10 else dt.datetime.fromisoformat(s[:10])
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d
    except ValueError:
        return None


def salary(r: dict, type_: str):
    lo, hi, per = r.get("salary_min"), r.get("salary_max"), r.get("salary_period") or "year"
    vals = [v for v in (lo, hi) if isinstance(v, (int, float)) and v > 0]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if per == "month":
        if type_ == "Lehrstelle" or hi < 2500:
            return {"monthly": int(round(hi, -1))}
        lo, hi = lo * 12, hi * 12
    elif per != "year":
        return None
    if not (20000 <= hi <= 400000):
        return None
    return {"min": int(round(lo, -3)), "max": int(round(hi, -3))}


def build(r: dict, geo: Geocoder, now: dt.datetime, max_age: int):
    title = re.sub(r"\s*[\(\[]?\b[mwfdhx]\s*/\s*[mwfdhx](\s*/\s*[mwfdhx])?\b[\)\]]?", "", (r.get("title") or "")).strip(" -–|,")
    title = re.sub(r"\s{2,}", " ", title)
    if not title or not r.get("url"):
        return None
    posted = parse_date(r.get("posted"))
    if posted and (now - posted).days > max_age:
        return None
    valid = parse_date(r.get("valid_through"))
    if valid and valid < now:
        return None

    lat, lon = r.get("lat"), r.get("lon")
    plz, place = str(r.get("postal_code") or ""), r.get("city") or ""
    if not in_ch(lat, lon) or not place:
        hit = geo.lookup(postal_code=plz, city=place, text=r.get("location") or "")
        if hit:
            if not in_ch(lat, lon):
                lat, lon = hit["lat"], hit["lon"]
            plz = plz or hit["plz"]
            place = place or hit["place"]
    if not in_ch(lat, lon):
        return None  # nicht in der Schweiz oder Ort unbekannt
    place = place or (r.get("location") or "").split(",")[0].strip() or "Schweiz"

    text = f"{title} {r.get('description') or ''}"
    type_ = employment_type(title, r.get("employment_raw"))
    cat, sub = classify(title, r.get("category_hint"))
    return {
        "uid": hashlib.sha1((r.get("source_id") or r["url"]).encode()).hexdigest()[:12],
        "title": title[:140],
        "company": (r.get("company") or "Unbekannte Firma").strip()[:80],
        "cat": cat, "sub": sub,
        "place": place, "plz": plz,
        "lat": round(float(lat), 5), "lon": round(float(lon), 5),
        "type": type_,
        "pensum": pensum(title, r.get("contract_time")) or pensum(r.get("description") or ""),
        "level": level(title, type_),
        "sal": salary(r, type_),
        "mode": work_mode(text, r.get("remote")),
        "posted": (posted or now).date().isoformat(),
        "url": r["url"],
        "source": r.get("source") or "",
        "logo": r.get("logo") or None,
        "desc": r.get("description") or "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "crawler" / "sources.yaml"))
    ap.add_argument("--out", default=str(ROOT / "data" / "jobs.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    http = Http(cfg.get("user_agent", "JobmapBot/0.1"), float(cfg.get("delay_seconds", 2)))
    geo = Geocoder(http, ROOT / "crawler" / "cache" / "geocache.json")
    now = dt.datetime.now(dt.timezone.utc)

    raw: list[dict] = []
    if (cfg.get("adzuna") or {}).get("enabled", True):
        raw += adzuna.fetch(http, cfg.get("adzuna") or {})
    if (cfg.get("jooble") or {}).get("enabled", True):
        raw += jooble.fetch(http, cfg.get("jooble") or {})
    if (cfg.get("careerjet") or {}).get("enabled", False):
        raw += careerjet.fetch(http, cfg.get("careerjet") or {})
    else:
        log.info("Careerjet ist in sources.yaml ausgeschaltet.")
    raw += ats.fetch(http, cfg.get("ats_companies") or [])
    raw += jsonld.fetch(http, cfg.get("career_sites") or [])
    log.info("Rohdaten: %s Stellen", len(raw))

    jobs, seen = [], set()
    for r in raw:
        j = build(r, geo, now, int(cfg.get("max_age_days", 45)))
        if not j:
            continue
        key = re.sub(r"\W+", " ", norm(f"{j['title']}|{j['company']}|{j['place']}")).strip()
        if key in seen:
            continue
        seen.add(key)
        jobs.append(j)
    jobs.sort(key=lambda j: j["posted"], reverse=True)

    by_source: dict[str, int] = {}
    for j in jobs:
        by_source[j["source"]] = by_source.get(j["source"], 0) + 1
    log.info("Fertig: %s Stellen nach Bereinigung %s", len(jobs), by_source)

    geo.save()
    if args.dry_run:
        return
    if not jobs:
        log.warning("Keine Stellen gefunden – bestehende jobs.json bleibt unverändert.")
        return
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": now.isoformat(timespec="seconds"), "count": len(jobs),
                               "sources": by_source, "jobs": jobs}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    log.info("Gespeichert: %s", out)


if __name__ == "__main__":
    main()
