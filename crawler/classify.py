"""Ordnet Stellen Branche + Berufsgruppe zu und liest Pensum, Anstellungsart, Erfahrung und Arbeitsort aus dem Text.

Die Regeln arbeiten mit Stichwörtern im Stellentitel (Deutsch, Französisch, Italienisch, Englisch).
Reihenfolge ist wichtig: Die erste passende Regel gewinnt. Regeln hier ergänzen, wenn Stellen falsch landen.
"""
from __future__ import annotations

import re

from common import norm

# (Branche, Berufsgruppe, Stichwörter als Regex auf den normalisierten Titel)
RULES = [
    ("Gesundheit & Pflege", "Apotheke", r"apothek|pharma.?assist|pharmacien|drogist"),
    ("Gesundheit & Pflege", "Therapie", r"physio|ergothera|logopad|psychotherap|therapeut"),
    ("Gesundheit & Pflege", "Arzt- & Zahnarztpraxis", r"\bmpa\b|praxisassist|dentalassist|assistant.? dentaire|assistante? medical|zahnarzt|arzt|arztin|medecin|oberarzt|assistenzarzt"),
    ("Gesundheit & Pflege", "Pflege", r"pflege|\bfage\b|fachfrau gesundheit|fachmann gesundheit|infirmi|\bassc\b|spitex|hebamme|sage.?femme|betagtenbetreu"),
    ("Bildung & Soziales", "Kinderbetreuung", r"\bfabe\b|kita|kinderbetreu|fachperson betreuung|educat.*enfance|creche|hort\b|spielgruppe"),
    ("Bildung & Soziales", "Schule", r"lehrperson|lehrer|lehrerin|enseignant|docente|heilpadagog|schulisch|klassenassist|dozent"),
    ("Bildung & Soziales", "Soziale Arbeit", r"sozialpadagog|sozialarbeit|travailleu.*social|educateur social|sozialbegleit|agogi"),
    ("Informatik", "Daten & Analyse", r"\bdata\b|daten|analyst|business intelligence|\bbi[- ]|machine learning|\bml\b|\bai\b"),
    ("Informatik", "Systemtechnik & Cloud", r"system ?engineer|systemtechnik|cloud|devops|netzwerk|network|linux|azure|\baws\b|sre\b|security engineer|cyber"),
    ("Informatik", "ICT-Support", r"support|helpdesk|service ?desk|ict.?fach|ict.?techn|workplace"),
    ("Informatik", "Softwareentwicklung", r"software|developer|entwickler|programm|frontend|backend|full.?stack|applikationsentw|informatiker|\bjava\b|python|\.net\b|ingenieur logiciel"),
    ("Finanzen & Versicherung", "Compliance & Recht", r"compliance|jurist|legal|anwalt|avocat|\brecht|paralegal"),
    ("Finanzen & Versicherung", "Rechnungswesen & Treuhand", r"buchhalt|controll|treuhand|fiduciair|comptab|accountant|accounting|finanzbuch|revisor|audit|steuer"),
    ("Finanzen & Versicherung", "Versicherung", r"versicherung|assurance|underwriter|schaden|sinistre|broker"),
    ("Finanzen & Versicherung", "Bank", r"bank|kundenberat.*(privat|hypothek|firmen)|relationship manager|wealth|anlage|portfolio|private banking|hypothek"),
    ("Gastronomie & Hotellerie", "Küche", r"koch\b|kochin|koche\b|cuisinier|cuoco|chef de partie|sous.?chef|kuche|kuchen(hilfe|chef)|patissier|commis"),
    ("Gastronomie & Hotellerie", "Service & Bar", r"service(mitarb|fach|angest)|servicefachangest|serveu|kellner|barista|barkeeper|\bbar\b|restauration"),
    ("Gastronomie & Hotellerie", "Hotel & Empfang", r"hotel|rezeption|reception|housekeeping|zimmer(frau|mann)|concierge|gouvernante"),
    ("Bau & Handwerk", "Elektro", r"elektroinst|elektriker|electricien|montage.?elektr|elektroplan|telematik"),
    ("Bau & Handwerk", "Sanitär & Heizung", r"sanitar|heizung|chauffag|haustechn|gebaudetechn|lufttechn|klima|hlks|installateur sanit"),
    ("Bau & Handwerk", "Holz & Innenausbau", r"schreiner|zimmerm|menuisier|charpent|maler\b|malerin|gipser|plattenleger|bodenleger|innenausbau|peintre"),
    ("Bau & Handwerk", "Hochbau", r"maurer|macon|bauleit|polier|bauarbeit|strassenbau|tiefbau|hochbau|baufuhrer|chef de chantier|bauzeichn|architekt|bauingenieur"),
    ("Logistik & Transport", "Fahrdienst", r"chauffeu|fahrer|lenker|kurier|coursier|buschauff|lokfuhr|zugbegleit|driver"),
    ("Logistik & Transport", "Disposition & Planung", r"disponent|dispatch|supply chain|einkauf|procurement|beschaffung|logistikplan|spedition"),
    ("Logistik & Transport", "Lager", r"logistiker|lager|magazin|stapler|kommission|logisticien|warehouse|entrepot"),
    ("Detailhandel", "Filialleitung", r"filialleit|store manager|gerant|marktleit|shop manager|stv\.? filial"),
    ("Detailhandel", "Lebensmittel", r"fleisch|metzg|backer|bouch|boulang|frische|lebensmittel|detailhandel.*lebensm"),
    ("Detailhandel", "Verkauf & Beratung", r"detailhandel|verkauf|vendeu|verkaufer|kassier|caissi|sales assistant|verkaufsberat|kundenberat"),
    ("Industrie & Technik", "Qualität", r"qualitat|qualite|quality|\bqs\b|\bqa\b|prufer|controleur"),
    ("Industrie & Technik", "Konstruktion", r"konstrukt|zeichner|designer ingen|cad\b|entwicklungsingen|ingenieur|engineer"),
    ("Industrie & Technik", "Mechanik & Automation", r"polymech|automatik|mechaniker|mecanicien|servicetechn|elektronik|techniker|anlagenbau|instandhalt|unterhalt|maintenance"),
    ("Industrie & Technik", "Produktion", r"produktion|production|anlagenfuhr|maschinenfuhr|operator|fertigung|montage"),
    ("Verwaltung & Büro", "Personal (HR)", r"\bhr\b|personal|human resources|recruit|ressources humaines|payroll|lohnbuch"),
    ("Verwaltung & Büro", "Assistenz & Empfang", r"assistent|assistant|empfang|office manag|sekretar|secretaire|receptionist"),
    ("Verwaltung & Büro", "Sachbearbeitung", r"sachbearbeit|kaufm|kauffrau|kaufmann|employe de commerce|administrat|verwaltung|backoffice|back office"),
]
RULES_RE = [(c, s, re.compile(p)) for c, s, p in RULES]

# Adzuna-Kategorie → Branche (Rückfallebene, wenn der Titel nichts hergibt)
ADZUNA_CATEGORY = {
    "it-jobs": ("Informatik", "Softwareentwicklung"),
    "healthcare-nursing-jobs": ("Gesundheit & Pflege", "Pflege"),
    "retail-jobs": ("Detailhandel", "Verkauf & Beratung"),
    "hospitality-catering-jobs": ("Gastronomie & Hotellerie", "Service & Bar"),
    "trade-construction-jobs": ("Bau & Handwerk", "Hochbau"),
    "logistics-warehouse-jobs": ("Logistik & Transport", "Lager"),
    "accounting-finance-jobs": ("Finanzen & Versicherung", "Rechnungswesen & Treuhand"),
    "admin-jobs": ("Verwaltung & Büro", "Sachbearbeitung"),
    "hr-jobs": ("Verwaltung & Büro", "Personal (HR)"),
    "teaching-jobs": ("Bildung & Soziales", "Schule"),
    "social-work-jobs": ("Bildung & Soziales", "Soziale Arbeit"),
    "engineering-jobs": ("Industrie & Technik", "Konstruktion"),
    "manufacturing-jobs": ("Industrie & Technik", "Produktion"),
    "maintenance-jobs": ("Industrie & Technik", "Mechanik & Automation"),
    "legal-jobs": ("Finanzen & Versicherung", "Compliance & Recht"),
}

PENSUM_RE = re.compile(r"(\d{2,3})\s*(?:%|prozent)?\s*(?:-|–|—|bis|a|à)\s*(\d{2,3})\s*%|(\d{2,3})\s*%")


def classify(title: str, hint: str | None = None) -> tuple[str, str]:
    t = norm(title)
    for cat, sub, rx in RULES_RE:
        if rx.search(t):
            return cat, sub
    if hint and hint in ADZUNA_CATEGORY:
        return ADZUNA_CATEGORY[hint]
    return "Weitere Berufe", "Andere"


def pensum(text: str, contract_time: str | None = None):
    m = PENSUM_RE.search(text or "")
    if m:
        if m.group(3):
            v = int(m.group(3))
            if 10 <= v <= 100:
                return [v, v]
        else:
            a, b = int(m.group(1)), int(m.group(2))
            if 10 <= a <= b <= 100:
                return [a, b]
    ct = norm(contract_time or "")
    if "full" in ct or "vollzeit" in ct or "plein" in ct:
        return [100, 100]
    if "part" in ct or "teilzeit" in ct or "partiel" in ct:
        return [40, 80]
    return None


def employment_type(title: str, raw: str | None = None) -> str:
    t = norm(f"{title} {raw or ''}")
    if re.search(r"lehrstelle|lernende|\blehre\b|apprenti|apprendist|ausbildung.*efz|efz.*lehr", t):
        return "Lehrstelle"
    if re.search(r"praktik|stagiai|\bstage\b|intern\b|internship|trainee", t):
        return "Praktikum"
    if re.search(r"temporar|temporaire|\btemp\b|aushilf|temporary", t):
        return "Temporär"
    if re.search(r"befristet|\bcdd\b|contract|contrat a duree|fixed.?term", t):
        return "Befristet"
    return "Festanstellung"


def level(title: str, type_: str) -> str:
    t = norm(title)
    if type_ in ("Lehrstelle", "Praktikum") or re.search(r"junior|einsteig|berufseinst|trainee|debutant", t):
        return "Einstieg"
    if re.search(r"leiter|leiterin|head of|\blead\b|director|direktor|manager|chef\b|cheffe|kader|responsable|gesch.ftsf", t):
        return "Kader"
    return "Berufserfahren"


def work_mode(text: str, remote_flag=None) -> str:
    t = norm(text)
    if remote_flag is True or re.search(r"full.?remote|100 ?% remote|remote only|vollstandig remote", t):
        return "Remote"
    if re.search(r"hybrid|homeoffice|home.?office|teletravail|remote", t):
        return "Hybrid"
    return "Vor Ort"
