"""Ortssuche über geo.admin.ch (gratis, nur Schweiz) mit Zwischenspeicher."""
from __future__ import annotations

import json
import re
from pathlib import Path

from common import Http, clean_text, log

URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
COUNTRY_WORDS = re.compile(r"\b(schweiz|switzerland|suisse|svizzera|svizra|ch)\b", re.I)


class Geocoder:
    def __init__(self, http: Http, cache_path: Path):
        self.http = http
        self.path = cache_path
        try:
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        self.new = 0

    def lookup(self, *, postal_code: str = "", city: str = "", text: str = "") -> dict | None:
        """Gibt {lat, lon, plz, place} zurück oder None, wenn der Ort nicht in der Schweiz gefunden wird."""
        queries = []
        if postal_code and city:
            queries.append(f"{postal_code} {city}")
        if postal_code:
            queries.append(str(postal_code))
        if city:
            queries.append(city)
        if text:
            t = COUNTRY_WORDS.sub(" ", text)
            t = re.sub(r"[,;/|()]+", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                queries.append(t)
                first = re.split(r"[,;/|]", text)[0].strip()
                if first and first != t:
                    queries.append(first)
        for q in queries:
            hit = self._query(q)
            if hit:
                return hit
        return None

    def _query(self, q: str) -> dict | None:
        key = q.lower().strip()
        if not key or len(key) < 2:
            return None
        if key in self.cache:
            return self.cache[key]
        data = self.http.get_json(URL, params={
            "type": "locations", "origins": "zipcode,gg25", "sr": 4326, "limit": 1, "searchText": q,
        })
        hit = None
        try:
            res = (data or {}).get("results") or []
            if res:
                a = res[0]["attrs"]
                label = clean_text(a.get("label", ""))
                plz_m = re.search(r"\b(\d{4})\b", label)
                place = re.sub(r"\b\d{4}\b", "", label)
                place = re.sub(r"\([A-Z]{2}\)", "", place).replace(" - ", " ").strip(" -")
                hit = {"lat": round(float(a["lat"]), 5), "lon": round(float(a["lon"]), 5),
                       "plz": plz_m.group(1) if plz_m else "", "place": re.sub(r"\s+", " ", place).strip()}
        except (KeyError, ValueError, TypeError) as e:
            log.warning("Geocoding-Antwort unklar für %r: %s", q, e)
        self.cache[key] = hit
        self.new += 1
        return hit

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
