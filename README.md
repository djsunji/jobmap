# jobmap

Jobs in deiner Nähe finden: Adresse eingeben, Umkreis wählen, Stellen auf der Karte sehen und filtern.

- **Website:** `index.html` (eine Datei, läuft auf GitHub Pages)
- **Crawler:** `crawler/` holt jede Nacht Stellen aus erlaubten Quellen und speichert sie in `data/jobs.json`
- **Automatik:** `.github/workflows/` startet den Crawler jede Nacht und veröffentlicht die Website neu

Solange noch keine echten Stellen geladen sind, zeigt die Website Beispieldaten.

---

## Einrichtung Schritt für Schritt

### 1. Dateien hochladen
1. Auf github.com ein neues Repository **jobmap** anlegen (öffentlich, sonst kostet GitHub Pages).
2. Den Inhalt dieses Ordners hochladen: im Repository auf **Add file → Upload files**, alles hineinziehen
   (auch den versteckten Ordner `.github`), dann **Commit changes**.
   Tipp: Wenn der Ordner `.github` beim Hineinziehen fehlt, die zwei Dateien darin einzeln über
   **Add file → Create new file** mit dem Namen `.github/workflows/crawl.yml` bzw. `pages.yml` anlegen.

### 2. Website einschalten
1. **Settings → Pages** öffnen.
2. Bei **Source** „**GitHub Actions**“ wählen.
3. Unter **Actions** läuft jetzt „Website veröffentlichen“. Nach 1–2 Minuten ist die Seite erreichbar unter
   `https://<dein-name>.github.io/jobmap/`

### 3. Adzuna-Schlüssel holen (gratis, ca. 10 Minuten)
1. Auf <https://developer.adzuna.com> registrieren.
2. Im Dashboard stehen **Application ID** und **Application Key**.
3. Im Repository: **Settings → Secrets and variables → Actions → New repository secret**
   - Name `ADZUNA_APP_ID`, Wert = Application ID
   - Name `ADZUNA_APP_KEY`, Wert = Application Key

### 3a. Jooble-Schlüssel (optional, empfohlen)
1. <https://jooble.org/api/about> öffnen und das Formular ausfüllen (Website, Zweck). Den Schlüssel schickt Jooble per E-Mail.
2. Als Secret `JOOBLE_API_KEY` speichern. Jooble ist in `crawler/sources.yaml` bereits eingeschaltet.

### 3b. Careerjet-Schlüssel (optional)
Als Secret `CAREERJET_API_KEY` speichern. Careerjet ist in `crawler/sources.yaml` zuerst **aus**:
Die API verlangt bei jeder Anfrage IP und Browser des suchenden Besuchers und ist für Live-Suchen
gedacht. Frag Careerjet per Mail, ob Jobmap die Resultate nachts abholen und zwischenspeichern darf.
Wenn ja: bei `careerjet:` `enabled: true` setzen.

### 4. In `crawler/sources.yaml` deinen Namen eintragen
Bei `user_agent` und `referer` `<DEIN-NAME>` durch deinen GitHub-Namen ersetzen. So wissen Websites, wer abfragt.

### 5. Ersten Lauf starten
**Actions → Stellen aktualisieren → Run workflow**. Nach ein paar Minuten ist `data/jobs.json` gefüllt
und die Website zeigt oben grün „… echte Stellen · Stand …“.
Danach läuft das jede Nacht automatisch.

---

## Weitere Quellen hinzufügen

Alles in `crawler/sources.yaml`. Nur Quellen eintragen, die das Abholen erlauben.

**Firmen mit Bewerbungssystem (am einfachsten):** Viele Firmen nutzen Personio, Recruitee,
SmartRecruiters, Greenhouse oder Lever. Diese Systeme stellen die Stellen öffentlich bereit.
Den „slug“ findest du in der Adresse der Stellenseite:

| System | Adresse der Stellenseite | Eintrag |
|---|---|---|
| Personio | `firma.jobs.personio.de` | `{ name: "Firma AG", ats: personio, slug: "firma" }` |
| Recruitee | `firma.recruitee.com` | `{ name: "Firma AG", ats: recruitee, slug: "firma" }` |
| SmartRecruiters | `careers.smartrecruiters.com/Firma` | `{ name: "Firma AG", ats: smartrecruiters, slug: "Firma" }` |
| Greenhouse | `boards.greenhouse.io/firma` | `{ name: "Firma AG", ats: greenhouse, slug: "firma" }` |
| Lever | `jobs.lever.co/firma` | `{ name: "Firma AG", ats: lever, slug: "firma" }` |

**Karriereseiten mit JobPosting-Daten:** Viele Firmen kennzeichnen ihre Inserate für Google for Jobs.
Prüfen: Stelleninserat öffnen → Rechtsklick → Seitenquelltext → nach `JobPosting` suchen.
Wenn vorhanden, die Sitemap der Firma eintragen (steht meist in `https://firma.ch/robots.txt`).

## Regeln, an die sich der Crawler hält
- nur offizielle Schnittstellen, öffentliche Feeds und Seiten, die laut `robots.txt` erlaubt sind
- mindestens 2 Sekunden Pause pro Website, eigener Name im User-Agent
- keine Personendaten (keine Namen von Ansprechpersonen)
- **keine** grossen Jobportale (jobs.ch, jobup.ch, Indeed, LinkedIn …) – deren Bedingungen verbieten das

Rechtlicher Hinweis: Vor dem öffentlichen Start die Nutzung der Daten kurz rechtlich prüfen lassen.
Adzuna verlangt den Hinweis „Jobs by Adzuna“ mit Link – die Website zeigt ihn automatisch unter der Liste.

## Lokal testen (optional)
```bash
pip install -r crawler/requirements.txt
export ADZUNA_APP_ID=… ADZUNA_APP_KEY=…
python crawler/crawl.py
python -m http.server 8000     # dann http://localhost:8000 öffnen
```
Die Website muss über einen Webserver laufen, damit sie `data/jobs.json` laden kann. Direkt als Datei
geöffnet zeigt sie Beispieldaten.

## Branchen anpassen
Welche Stelle in welche Branche und Berufsgruppe kommt, steht in `crawler/classify.py` (Stichwortregeln).
Landet etwas falsch, dort ein Stichwort ergänzen. Nicht zuordenbare Stellen erscheinen unter „Weitere Berufe“.
