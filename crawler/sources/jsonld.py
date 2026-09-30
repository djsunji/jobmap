"""Karriereseiten mit maschinenlesbaren Inseraten (schema.org „JobPosting“, für Google for Jobs gedacht).

Pro Website gibst du entweder eine Sitemap (plus Muster für Stellen-URLs) oder direkt Stellen-URLs an.
Der Crawler hält sich an robots.txt, fragt langsam ab und liest nur die JobPosting-Daten.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from common import Http, clean_text, log

LD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
CH_WORDS = {"ch", "che", "switzerland", "schweiz", "suisse", "svizzera"}


def _walk(obj):
    if isinstance(obj, list):
        for o in obj:
            yield from _walk(o)
    elif isinstance(obj, dict):
        t = obj.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            yield obj
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in obj:
                yield from _walk(obj[k])


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def parse_jobpostings(html_text: str, url: str, site_name: str) -> list[dict]:
    out = []
    for block in LD_RE.findall(html_text or ""):
        try:
            data = json.loads(block.strip())
        except ValueError:
            try:
                data = json.loads(re.sub(r"[\x00-\x1f]", " ", block.strip()))
            except ValueError:
                continue
        for jp in _walk(data):
            loc = _first(jp.get("jobLocation")) or {}
            addr = loc.get("address") or {}
            if isinstance(addr, str):
                addr = {"addressLocality": addr}
            country = addr.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            if country and str(country).strip().lower() not in CH_WORDS:
                continue
            geo = loc.get("geo") or {}
            org = jp.get("hiringOrganization") or {}
            if isinstance(org, str):
                org = {"name": org}
            sal = jp.get("baseSalary") or {}
            val = sal.get("value") if isinstance(sal, dict) else None
            unit = (val or {}).get("unitText", "") if isinstance(val, dict) else ""
            logo = org.get("logo")
            if isinstance(logo, dict):
                logo = logo.get("url")
            out.append({
                "source": site_name, "source_id": f"ld:{jp.get('identifier', {}).get('value') if isinstance(jp.get('identifier'), dict) else url}",
                "title": clean_text(jp.get("title")), "company": clean_text(org.get("name")) or site_name,
                "url": jp.get("url") or url, "logo": logo if isinstance(logo, str) else None,
                "postal_code": str(addr.get("postalCode") or ""), "city": addr.get("addressLocality") or "",
                "location": ", ".join(filter(None, [addr.get("streetAddress"), addr.get("postalCode"), addr.get("addressLocality")])),
                "lat": _num(geo.get("latitude")), "lon": _num(geo.get("longitude")),
                "posted": jp.get("datePosted"), "valid_through": jp.get("validThrough"),
                "salary_min": _num((val or {}).get("minValue")) if isinstance(val, dict) else None,
                "salary_max": _num((val or {}).get("maxValue") or (val or {}).get("value")) if isinstance(val, dict) else None,
                "salary_period": {"YEAR": "year", "MONTH": "month", "HOUR": "hour"}.get(str(unit).upper(), "year"),
                "employment_raw": " ".join(jp["employmentType"]) if isinstance(jp.get("employmentType"), list) else (jp.get("employmentType") or ""),
                "contract_time": str(jp.get("employmentType") or ""),
                "remote": True if jp.get("jobLocationType") == "TELECOMMUTE" else None,
                "description": clean_text(jp.get("description"), 600),
            })
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sitemap_urls(http: Http, sitemap: str, pattern: str | None, limit: int, depth: int = 0) -> list[str]:
    text = http.get_text(sitemap, robots=True)
    if not text:
        return []
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        return []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    rx = re.compile(pattern) if pattern else None
    urls = []
    for sm in root.findall("s:sitemap/s:loc", ns):
        if depth < 2 and len(urls) < limit:
            urls += _sitemap_urls(http, sm.text.strip(), pattern, limit - len(urls), depth + 1)
    for loc in root.findall("s:url/s:loc", ns):
        u = loc.text.strip()
        if not rx or rx.search(u):
            urls.append(u)
        if len(urls) >= limit:
            break
    return urls


def fetch(http: Http, sites: list[dict]) -> list[dict]:
    out = []
    for site in sites or []:
        name = site.get("name", "Karriereseite")
        limit = int(site.get("max_pages", 150))
        urls = list(site.get("urls") or [])
        if site.get("sitemap"):
            urls += _sitemap_urls(http, site["sitemap"], site.get("include"), limit)
        found = 0
        for u in urls[:limit]:
            html_text = http.get_text(u, robots=True)
            jobs = parse_jobpostings(html_text, u, name)
            if site.get("logo"):
                for j in jobs:
                    j["logo"] = j.get("logo") or site["logo"]
            found += len(jobs)
            out += jobs
        log.info("%s: %s Seiten geprüft, %s Stellen", name, min(len(urls), limit), found)
    return out
