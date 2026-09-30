"""Gemeinsame Hilfsmittel: HTTP mit Pausen, robots.txt-Prüfung und Text-Bereinigung."""
from __future__ import annotations

import html
import logging
import re
import time
import unicodedata
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("jobmap")


class Http:
    """Höflicher HTTP-Client: eigener User-Agent, Pause pro Website, robots.txt für Webseiten."""

    def __init__(self, user_agent: str, delay: float = 2.0, timeout: float = 25.0):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent, "Accept-Language": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7"})
        self.ua = user_agent
        self.delay = delay
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}

    # -- robots.txt -------------------------------------------------------
    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    rp = None  # keine robots.txt = erlaubt
                else:
                    rp.parse(r.text.splitlines())
                    cd = rp.crawl_delay(self.ua) or rp.crawl_delay("*")
                    if cd:
                        self._last.setdefault(p.netloc + ":delay", float(cd))
            except requests.RequestException:
                rp = None
            self._robots[base] = rp
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(self.ua, url)

    # -- Anfragen ---------------------------------------------------------
    def _wait(self, url: str):
        host = urlparse(url).netloc
        delay = max(self.delay, self._last.get(host + ":delay", 0))
        since = time.time() - self._last.get(host, 0)
        if since < delay:
            time.sleep(delay - since)
        self._last[host] = time.time()

    def get(self, url: str, *, params=None, robots: bool = False, retries: int = 2, method="GET", json_body=None):
        if robots and not self.allowed(url):
            log.info("robots.txt verbietet: %s", url)
            return None
        for attempt in range(retries + 1):
            self._wait(url)
            try:
                r = self.s.request(method, url, params=params, json=json_body, timeout=self.timeout)
            except requests.RequestException as e:
                log.warning("Fehler bei %s: %s", url, e)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                log.warning("HTTP %s bei %s", r.status_code, url)
                return None
            return r
        return None

    def get_json(self, url, **kw):
        r = self.get(url, **kw)
        if r is None:
            return None
        try:
            return r.json()
        except ValueError:
            log.warning("Keine gültige JSON-Antwort: %s", url)
            return None

    def get_text(self, url, **kw):
        r = self.get(url, **kw)
        return None if r is None else r.text


# -- Text -------------------------------------------------------------------
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value, limit: int | None = None) -> str:
    """HTML entfernen, Entities auflösen, Leerraum zusammenfassen."""
    if not value:
        return ""
    t = html.unescape(str(value))
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", t)
    t = TAG_RE.sub(" ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    if limit and len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0]
        t = cut + " …"
    return t


def norm(value: str) -> str:
    """Kleinschreibung, ohne Akzente – für Stichwortsuche."""
    t = unicodedata.normalize("NFD", (value or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")
