#!/usr/bin/env python3
"""Vision-Vorstufe: Quellen laden, Ausschnitte schneiden, Manifest und Testfaelle schreiben.

Baut die zehn Faelle der Vorstufe (docs/vision-dimension-plan.md, Abschnitt 8)
aus echten Scans mit Editoren-Transkription. Geladen wird nur, was die Faelle
brauchen: aus grossen Zenodo-Archiven (Kurrent 7,8 GB, e-NDP 0,9 GB) holt das
Skript einzelne Dateien per HTTP-Range, ohne das Archiv ganz zu laden.

Aufruf aus testplan/:
    python3 vision/bauen.py            # laden (falls noetig), schneiden, schreiben
    python3 vision/bauen.py --pruefen  # neu schneiden und gegen das Manifest pruefen

Schreibt:
    vision/quellen/                  Downloads (nicht im Repo)
    vision/ausschnitte/<id>.png      Ausschnitte (nicht im Repo, kommen in den HF-Datensatz)
    vision/sources.jsonl             Manifest: Quelle, Lizenz, Zeilen, Box, Pruefsummen
    testdata/vision/vorstufe.jsonl   Testfaelle fuer den Harness

Braucht Pillow und fuer die Destatis-Seite pdftoppm (poppler-utils).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import statistics
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageStat

TESTPLAN = Path(__file__).resolve().parent.parent
VISION = TESTPLAN / "vision"
QUELLEN_DIR = VISION / "quellen"
AUSSCHNITTE = VISION / "ausschnitte"
MANIFEST = VISION / "sources.jsonl"
TESTDATEN = TESTPLAN / "testdata" / "vision" / "vorstufe.jsonl"

MAX_SEITE = 1600          # laengste Seite eines Ausschnitts in Pixeln (nur verkleinern)
RAND_FAKTOR = 0.35        # Rand um den Zeilenblock, als Anteil der mittleren Zeilenhoehe
MASKE_PX = 7              # Polygone der gewaehlten Zeilen im verkleinerten Bild um so viel weiten
UA = "Wget/1.21.4 (southbyte-vllm vision/bauen.py)"  # UB Mannheim lehnt urllib-Kennung ab
LIZENZ_GEPRUEFT = "2026-10-25"

# --------------------------------------------------------------------------- Quellen
# Lizenz je Datensatz am 25.10.2026 ueber die Zenodo-API (metadata.license) bzw. an der
# Quelle geprueft. "lizenz" ist die Lizenz, unter der wir den Ausschnitt weitergeben.
QUELLEN = {
    "reichsanzeiger": {
        "quelle": "https://doi.org/10.5281/zenodo.10144428",
        "version": "1.0.0",
        "titel": "UB-Mannheim/reichsanzeiger-gt: 1.0.0 (Ground Truth Deutscher Reichsanzeiger und "
                 "Preussischer Staatsanzeiger, 1820-1939)",
        "urheber": "Schmidt, Thomas; Kamlah, Jan; Weil, Stefan; Shigapov, Renat (UB Mannheim)",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "Zenodo-Record CC BY 4.0 (Repo-LICENSE CC0 1.0); Scans der UB Mannheim, "
                          "Public Domain Mark",
        "zip": "https://zenodo.org/records/10144428/files/UB-Mannheim/reichsanzeiger-gt-1.0.0.zip?download=1",
        "zip_lokal": "reichsanzeiger-gt-1.0.0.zip",
        "xml_pfad": "UB-Mannheim-reichsanzeiger-gt-44f2cd8/data/reichsanzeiger-1820-1939/GT-PAGE/{seite}.xml",
        "bild_url": "https://digi.bib.uni-mannheim.de/reichsanzeiger.fcgi?FIF=/reichsanzeiger/film/{film}",
    },
    "kurrent": {
        "quelle": "https://doi.org/10.5281/zenodo.17252677",
        "version": "1.0.0",
        "titel": "Handwritten Text Recognition Training and Test Set for German Kurrent of the "
                 "19th century (Teil Senatsprotokolle, Universitaet Tuebingen)",
        "urheber": "Gantner, Myriam; Vorlage: Universitaetsarchiv Tuebingen, Protokolle des "
                   "Akademischen Senats (ubtue/Ground-Truth)",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "Zenodo-Record CC BY 4.0; Scans laut UB Tuebingen (OpenDigi) gemeinfrei; "
                          "das Ursprungsrepo ubtue/Ground-Truth nennt keine eigene Lizenz. NICHT "
                          "verwendet: Teil 'Digitale Schriftkunde' (CC BY-NC-SA) und die DTA-Teile.",
        "zip": "https://zenodo.org/records/17252677/files/data.zip?download=1",
        "glied": "data/pages/Senatsprotokolle/pageAndXml/{seite}{endung}",
    },
    "formelbuch": {
        "quelle": "https://doi.org/10.5281/zenodo.21257167",
        "version": "2",
        "titel": "Diplomatic HTR ground truth dataset for an Early New High German transcription "
                 "model (15th century), Formelbuch BayHStA Ausw. Staaten, Lit. Oesterreich 463",
        "urheber": "Juszczak, Adam Piotr; Skidzun, Frederik",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "Zenodo-Record und LICENSE.md: CC BY 4.0",
        "zip_bilder": "https://zenodo.org/records/21257167/files/images.zip?download=1",
        "zip_xml": "https://zenodo.org/records/21257167/files/transcriptions.zip?download=1",
        "zip_xml_lokal": "fnhd/formelbuch_transcriptions.zip",
    },
    "wasserschaden": {
        "quelle": "https://doi.org/10.5281/zenodo.21438740",
        "version": "2026-07-19",
        "titel": "Diplomatic HTR ground truth dataset for water damaged text lines (ENHG, 15th "
                 "century), Formelbuch BayHStA Ausw. Staaten, Lit. Oesterreich 463",
        "urheber": "Flohr, Henriette; Kunzek, Jan",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "Zenodo-Record und LICENSE.md: CC BY 4.0",
        "zip_bilder": "https://zenodo.org/records/21438740/files/images.zip?download=1",
        "zip_xml": "https://zenodo.org/records/21438740/files/transcriptions.zip?download=1",
        "zip_xml_lokal": "fnhd/wasserschaden_transcriptions.zip",
    },
    "endp": {
        "quelle": "https://doi.org/10.5281/zenodo.7575693",
        "version": "1.0",
        "titel": "The e-NDP project: collaborative digital edition of the Chapter registers of "
                 "Notre-Dame of Paris (1326-1504), HTR Ground Truth",
        "urheber": "Claustre, Julie; Smith, Darwin; Torres Aguilar, Sergio; Bretthauer, Isabelle u. a.",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "Zenodo-Record CC BY 4.0; Edition mit aufgeloesten Abkuerzungen, "
                          "gestrichene Woerter in $...$",
        "zip": "https://zenodo.org/records/7575693/files/e-NDP_dataset.zip?download=1",
        "glied": "HTR_Ground-Truth/{ordner}/{datei}",
    },
    "destatis": {
        "quelle": "https://www.destatis.de/DE/Themen/Querschnitt/Jahrbuch/jb-geo-klima.pdf?__blob=publicationFile&v=7",
        "version": "Statistisches Jahrbuch 2019, Kapitel 1",
        "titel": "Statistisches Jahrbuch 2019, Kapitel 1 Geografie und Klima, S. 15",
        "urheber": "Statistisches Bundesamt (Destatis)",
        "lizenz": "Destatis: Verbreitung mit Quellenangabe gestattet",
        "lizenz_hinweis": "Ganze Seite unveraendert (nur gerendert), keine Bearbeitung; "
                          "Datenquelle der Tabelle: Bundesamt fuer Kartographie und Geodaesie",
    },
    "dwd": {
        "quelle": "https://opendata.dwd.de/weather/charts/analysis/Z__C_EDZW_20261024085029_tka01%2Cana_bwkman_dwdc_O_000000_000000_202610240000_WV12.png",
        "version": "Bodenanalyse 24.10.2026 00 UTC (korrigierte Fassung, erzeugt 08:50 UTC)",
        "titel": "Bodenwetterkarte Analyse Europa/Nordatlantik, 24.10.2026 00 UTC",
        "urheber": "Deutscher Wetterdienst",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "DWD-Rechtshinweis: Inhalte unter CC BY 4.0 mit Quellenangabe; "
                          "Open-Data-Server haelt Karten nur wenige Tage vor",
    },
}

T_AUFGABE = ("Transkribiere den Text im Bild genau so, wie er dasteht, Zeile für Zeile. "
             "Nicht übersetzen, nicht modernisieren, Abkürzungen nicht auflösen. "
             "Gib nur den Text aus.")
T_AUFGABE_LATEIN = ("Transkribiere den lateinischen Text im Bild Zeile für Zeile. Löse die "
                    "Abkürzungen dabei auf (zum Beispiel dñs → dominus), übersetze nicht. "
                    "Gib nur den Text aus.")

# --------------------------------------------------------------------------- Faelle
# Zeilen werden ueber ihre PAGE-IDs festgehalten, in Lesereihenfolge.
FAELLE = [
    {"id": "vis-fraktur-001", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger",
     "seite": "1857_132_0507", "film": "059-9940/0507.jp2&CVT=jpeg",
     "zeilen": [f"r5l{i}" for i in range(1, 11)], "schrift": "druck", "normalisierung": "fraktur"},
    {"id": "vis-fraktur-002", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger",
     "seite": "1910_299_0335", "film": "103-9511/0335.jp2&CVT=jpeg",
     "zeilen": "region:r22", "schrift": "druck", "normalisierung": "fraktur"},
    {"id": "vis-kurrent-001", "subcategory": "T3_kurrent", "quelle": "kurrent",
     "seite": "UAT_047_15_133", "zeilen": "bereich:1:10", "schrift": "hand", "normalisierung": "kurrent"},
    {"id": "vis-kurrent-002", "subcategory": "T3_kurrent", "quelle": "kurrent",
     "seite": "UAT_047_24_398", "zeilen": "erste:10", "schrift": "hand", "normalisierung": "kurrent"},
    {"id": "vis-fnhd-001", "subcategory": "T4_fnhd", "quelle": "formelbuch",
     "seite": "BayHStA_AS_Lit_Oe_463_303r", "zeilen": "bereich:1:10", "schrift": "hand",
     "normalisierung": "fnhd"},
    {"id": "vis-fnhd-002", "subcategory": "T4_fnhd", "quelle": "wasserschaden",
     "seite": "BayHStA_AS_Lit_Oe_463_210v", "zeilen": "ohne_raute:10", "schrift": "hand",
     "normalisierung": "fnhd"},
    {"id": "vis-latein-001", "subcategory": "T5_latein", "quelle": "endp",
     "seite": "FRAN_0393_00310_L", "zeilen": "erste:8", "schrift": "hand", "normalisierung": "latein"},
    {"id": "vis-latein-002", "subcategory": "T5_latein", "quelle": "endp",
     # rechte Spalte (Haupttext); links stehen die Namen der Anwesenden
     "seite": "FRAN_0393_00130_L",
     "zeilen": ["eSc_line_c114c9a2", "eSc_line_b4eb38e9", "eSc_line_5c886945", "eSc_line_503b8596",
                "eSc_line_de9b7208", "eSc_line_38effcd2", "eSc_line_b9e1d958", "eSc_line_f0beb71d"],
     "schrift": "hand",
     "normalisierung": "latein"},
    {"id": "vis-bild-001", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 5,
     "frage": "Wie hoch liegt Bad Tölz laut der Tabelle „Ausgewählte Ortshöhenlagen“? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "670 m", "alternativen": ["670", "670 m über NN", "670 Meter"],
     "schrift": "druck", "normalisierung": "modern"},
    {"id": "vis-bild-002", "subcategory": "V_karte", "quelle": "dwd",
     "frage": "Welches Tiefdruckgebiet ist in dieser Wetterkarte mit einem Namen beschriftet? "
              "Antworte nur mit dem Namen.",
     "antwort": "Ex-Josephine", "alternativen": ["Josephine", "EX-JOSEPHINE"],
     "schrift": "druck", "normalisierung": "modern"},
]


# --------------------------------------------------------------------------- Laden
class FernDatei(io.RawIOBase):
    """Datei hinter einer URL, gelesen per HTTP-Range: zipfile holt nur das Inhaltsverzeichnis
    und die gewuenschten Glieder, nicht das ganze Archiv."""

    def __init__(self, url: str):
        self.url, self.pos, self.geladen = url, 0, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=120) as r:
            self.groesse = int(r.headers["Content-Length"])

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, off: int, whence: int = 0) -> int:
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.groesse + off
        return self.pos

    def readinto(self, b) -> int:
        if self.pos >= self.groesse or not len(b):
            return 0
        ende = min(self.pos + len(b), self.groesse) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{ende}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            daten = r.read()
        b[:len(daten)] = daten
        self.pos += len(daten)
        self.geladen += len(daten)
        return len(daten)


_ZIPS: dict[str, tuple[zipfile.ZipFile, FernDatei | None]] = {}
GELADEN = {"bytes": 0}


def _zip(url: str, lokal: str | None = None) -> zipfile.ZipFile:
    if url not in _ZIPS:
        if lokal and (QUELLEN_DIR / lokal).exists():
            _ZIPS[url] = (zipfile.ZipFile(QUELLEN_DIR / lokal), None)
        else:
            fd = FernDatei(url)
            _ZIPS[url] = (zipfile.ZipFile(io.BufferedReader(fd, buffer_size=1 << 20)), fd)
    return _ZIPS[url][0]


def glied(url: str, name: str, ziel: Path, lokal: str | None = None) -> Path:
    """Ein Glied eines (fernen) Zip-Archivs nach ziel, falls noch nicht vorhanden."""
    if not ziel.exists():
        ziel.parent.mkdir(parents=True, exist_ok=True)
        daten = _zip(url, lokal).read(name)
        ziel.write_bytes(daten)
        GELADEN["bytes"] += len(daten)
        print(f"  geladen {ziel.relative_to(TESTPLAN)} ({len(daten) / 1e6:.1f} MB)")
    return ziel


def http(url: str, ziel: Path) -> Path:
    if not ziel.exists():
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                    timeout=300) as r:
            daten = r.read()
        ziel.write_bytes(daten)
        GELADEN["bytes"] += len(daten)
        print(f"  geladen {ziel.relative_to(TESTPLAN)} ({len(daten) / 1e6:.1f} MB)")
    return ziel


def quelldateien(f: dict) -> tuple[Path | None, Path]:
    """(PAGE-XML, Bild) eines Falls laden; bei V-Faellen kein XML."""
    q, s, Q = f["quelle"], f.get("seite", ""), QUELLEN[f["quelle"]]
    if q == "reichsanzeiger":
        xml = glied(Q["zip"], Q["xml_pfad"].format(seite=s), QUELLEN_DIR / "reichsanzeiger" / f"{s}.xml",
                    Q["zip_lokal"])
        bild = http(Q["bild_url"].format(film=f["film"]), QUELLEN_DIR / "reichsanzeiger" / f"{s}.jpg")
    elif q == "kurrent":
        xml = glied(Q["zip"], Q["glied"].format(seite=s, endung=".xml"), QUELLEN_DIR / "kurrent" / f"{s}.xml")
        bild = glied(Q["zip"], Q["glied"].format(seite=s, endung=".png"), QUELLEN_DIR / "kurrent" / f"{s}.png")
    elif q in ("formelbuch", "wasserschaden"):
        xml = glied(Q["zip_xml"], f"transcriptions/{s}.xml", QUELLEN_DIR / "fnhd" / f"{q}_{s}.xml",
                    Q["zip_xml_lokal"])
        bild = glied(Q["zip_bilder"], f"images/{s}.jpg", QUELLEN_DIR / "fnhd" / f"{q}_{s}.jpg")
    elif q == "endp":
        xml = glied(Q["zip"], Q["glied"].format(ordner="page_xml", datei=f"{s}.xml"),
                    QUELLEN_DIR / "endp" / f"{s}.xml")
        bild = glied(Q["zip"], Q["glied"].format(ordner="images", datei=f"{s}.jpg"),
                     QUELLEN_DIR / "endp" / f"{s}.jpg")
    elif q == "destatis":
        return None, http(Q["quelle"], QUELLEN_DIR / "destatis" / "jb-geo-klima.pdf")
    elif q == "dwd":
        return None, http(Q["quelle"], QUELLEN_DIR / "dwd" / "bwk_20261024_00.png")
    else:
        raise ValueError(q)
    return xml, bild


# --------------------------------------------------------------------------- PAGE-XML
def _lokal(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def page_zeilen(xml: Path) -> list[dict]:
    """Alle TextLines in Dokumentreihenfolge: id, region, Polygon, Text (erstes TextEquiv der Zeile)."""
    root = ET.parse(xml).getroot()
    out = []
    for reg in root.iter():
        if _lokal(reg.tag) != "TextRegion":
            continue
        for ln in reg:
            if _lokal(ln.tag) != "TextLine":
                continue
            pts, text = None, None
            for k in ln:
                if _lokal(k.tag) == "Coords" and pts is None:
                    pts = [tuple(int(float(v)) for v in p.split(",")) for p in k.get("points", "").split()]
                if _lokal(k.tag) == "TextEquiv" and text is None:
                    u = next((u for u in k if _lokal(u.tag) == "Unicode"), None)
                    text = (u.text or "") if u is not None else ""
            if pts and text is not None:
                out.append({"id": ln.get("id"), "region": reg.get("id"), "punkte": pts, "text": text})
    return out


def zeilen_waehlen(f: dict, alle: list[dict]) -> list[dict]:
    spez = f["zeilen"]
    nichtleer = [z for z in alle if z["text"].strip()]
    if isinstance(spez, list):
        nach_id = {z["id"]: z for z in alle}
        return [nach_id[i] for i in spez]
    art, wert = spez.split(":", 1)
    if art == "region":
        return [z for z in nichtleer if z["region"] == wert]
    n = int(wert.split(":")[-1])
    if art == "erste":
        return nichtleer[:n]
    if art == "bereich":                       # bereich:<erste Zeile, ab 0>:<Anzahl>
        start, n = (int(x) for x in wert.split(":"))
        return nichtleer[start:start + n]
    if art in ("ohne_raute", "ohne_dollar"):
        zeichen = "#" if art == "ohne_raute" else "$"
        for start in range(len(nichtleer) - n + 1):
            block = nichtleer[start:start + n]
            if not any(zeichen in z["text"] for z in block):
                return block
        raise ValueError(f"{f['id']}: kein Block mit {n} Zeilen ohne {zeichen}")
    raise ValueError(spez)


# --------------------------------------------------------------------------- Ausschnitte
def _verkleinern(im: Image.Image) -> tuple[Image.Image, float]:
    faktor = min(1.0, MAX_SEITE / max(im.size))
    if faktor < 1.0:
        im = im.resize((round(im.width * faktor), round(im.height * faktor)), Image.Resampling.LANCZOS)
    return im, faktor


def _modus(im: Image.Image) -> Image.Image:
    return im if im.mode in ("L", "RGB") else im.convert("RGB")


def ausschnitt(f: dict) -> tuple[Image.Image, dict]:
    """Bild und Manifest-Angaben eines Falls (ohne Pruefsummen)."""
    xml, bildpfad = quelldateien(f)
    if f["quelle"] == "destatis":
        dpi = int(MAX_SEITE / (722.835 / 72))          # Seitenhoehe 722,835 pt → ≤ 1600 px
        stamm = QUELLEN_DIR / "destatis" / f"seite{f['pdf_seite']}_{dpi}dpi"
        if not Path(f"{stamm}.png").exists():
            subprocess.run(["pdftoppm", "-f", str(f["pdf_seite"]), "-l", str(f["pdf_seite"]), "-r", str(dpi),
                            "-png", "-singlefile", str(bildpfad), str(stamm)], check=True)
        im = _modus(Image.open(f"{stamm}.png"))
        return im, {"datei_im_datensatz": bildpfad.name, "seite": f["pdf_seite"], "render_dpi": dpi,
                    "box": None, "skalierung": None, "zeilen_ids": None}
    if f["quelle"] == "dwd":
        im = Image.open(bildpfad).convert("RGB")
        im, faktor = _verkleinern(im)
        return im, {"datei_im_datensatz": bildpfad.name, "seite": None, "box": None,
                    "skalierung": round(faktor, 6), "zeilen_ids": None}
    zeilen = zeilen_waehlen(f, page_zeilen(xml))
    if not 6 <= len(zeilen) <= 15:
        raise ValueError(f"{f['id']}: {len(zeilen)} Zeilen, erwartet 6 bis 15")
    with Image.open(bildpfad) as orig:
        orig.load()
        xs = [x for z in zeilen for x, _ in z["punkte"]]
        ys = [y for z in zeilen for _, y in z["punkte"]]
        hoehe = statistics.median(max(p[1] for p in z["punkte"]) - min(p[1] for p in z["punkte"]) for z in zeilen)
        rand = round(RAND_FAKTOR * hoehe)
        box = (max(0, min(xs) - rand), max(0, min(ys) - rand),
               min(orig.width, max(xs) + rand), min(orig.height, max(ys) + rand))
        im = _modus(orig.crop(box))
    im, faktor = _verkleinern(im)
    # Handschriftzeilen ueberlappen; ein Rechteck zeigt deshalb Teile der Nachbarzeilen, die
    # nicht zur Wahrheit gehoeren. Ausserhalb der (leicht geweiteten) Polygone der gewaehlten
    # Zeilen wird die Flaeche mit der Papierfarbe des Ausschnitts gefuellt.
    maske = Image.new("L", im.size, 0)
    zeichnen = ImageDraw.Draw(maske)
    for z in zeilen:
        zeichnen.polygon([((x - box[0]) * faktor, (y - box[1]) * faktor) for x, y in z["punkte"]], fill=255)
    maske = maske.filter(ImageFilter.MaxFilter(MASKE_PX))
    papier = ImageStat.Stat(im, mask=Image.eval(maske, lambda v: 255 - v)).median
    grund = Image.new(im.mode, im.size, tuple(papier) if im.mode == "RGB" else papier[0])
    im = Image.composite(im, grund, maske)
    f["_wahrheit"] = "\n".join(z["text"] for z in zeilen)
    return im, {"datei_im_datensatz": bildpfad.name, "seite": f.get("seite"), "box": list(box),
                "skalierung": round(faktor, 6), "zeilen_ids": [z["id"] for z in zeilen],
                "xml": xml.name}


def png_bytes(im: Image.Image) -> bytes:
    puffer = io.BytesIO()
    im.save(puffer, "PNG", optimize=False)
    return puffer.getvalue()


def pixel_sha(im: Image.Image) -> str:
    h = hashlib.sha256(f"{im.mode}:{im.width}x{im.height}:".encode())
    h.update(im.tobytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- Ausgabe
def testfall(f: dict, meta: dict, sha: str, im: Image.Image) -> dict:
    transkription = "frage" not in f
    if transkription:
        aufgabe = T_AUFGABE_LATEIN if f["normalisierung"] == "latein" else T_AUFGABE
        erwartet = {"type": "transkription", "value": f["_wahrheit"]}
    else:
        aufgabe = f["frage"]
        erwartet = {"type": "antwort", "value": f["antwort"], "alternatives": f.get("alternativen", [])}
    return {
        "id": f["id"], "category": "vision", "subcategory": f["subcategory"],
        "language": "la" if f["normalisierung"] == "latein" else "de",
        "difficulty": "hard" if f["schrift"] == "hand" else "medium",
        "prompt": aufgabe, "expected": erwartet,
        "max_tokens": 2048 if transkription else 256,
        "metadata": {
            "bild": f"vision/ausschnitte/{f['id']}.png", "sha256": sha, "breite": im.width, "hoehe": im.height,
            "schrift": f["schrift"], "normalisierung": f["normalisierung"], "quelle": f["quelle"],
            "lizenz": QUELLEN[f["quelle"]]["lizenz"],
            "zeilen": len(meta["zeilen_ids"]) if meta.get("zeilen_ids") else None,
        },
    }


def manifestzeile(f: dict, meta: dict, sha: str, psha: str) -> dict:
    Q = QUELLEN[f["quelle"]]
    return {
        "fall": f["id"], "quelle_schluessel": f["quelle"], "quelle": Q["quelle"], "version": Q["version"],
        "datensatz_titel": Q["titel"], "urheber": Q["urheber"], "lizenz": Q["lizenz"],
        "lizenz_hinweis": Q["lizenz_hinweis"], "lizenz_geprueft_am": LIZENZ_GEPRUEFT,
        **meta, "ausschnitt": f"{f['id']}.png", "sha256": sha, "pixel_sha256": psha,
        "bearbeitung": ("Ausschnitt der genannten Zeilen, verkleinert auf hoechstens "
                        f"{MAX_SEITE} px; ausserhalb der Zeilenpolygone mit der Papierfarbe "
                        "gefuellt, damit keine Nachbarzeilen mitgelesen werden"
                        if meta.get("zeilen_ids") else
                        "ganze Seite, unveraendert gerendert" if f["quelle"] == "destatis" else
                        f"ganze Grafik, verkleinert auf hoechstens {MAX_SEITE} px"),
    }


def bauen() -> int:
    AUSSCHNITTE.mkdir(parents=True, exist_ok=True)
    TESTDATEN.parent.mkdir(parents=True, exist_ok=True)
    faelle, manifest = [], []
    for f in FAELLE:
        f = dict(f)
        im, meta = ausschnitt(f)
        daten = png_bytes(im)
        (AUSSCHNITTE / f"{f['id']}.png").write_bytes(daten)
        sha = hashlib.sha256(daten).hexdigest()
        faelle.append(testfall(f, meta, sha, im))
        manifest.append(manifestzeile(f, meta, sha, pixel_sha(im)))
        print(f"✓ {f['id']:16} {im.width}x{im.height}  {faelle[-1]['metadata']['zeilen'] or '-'} Zeilen")
    TESTDATEN.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in faelle), encoding="utf-8")
    MANIFEST.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in manifest), encoding="utf-8")
    print(f"{len(faelle)} Faelle → {TESTDATEN.relative_to(TESTPLAN)}, Manifest → {MANIFEST.relative_to(TESTPLAN)}")
    print(f"Neu geladen: {GELADEN['bytes'] / 1e6:.1f} MB")
    return 0


def pruefen() -> int:
    """Ausschnitte neu schneiden und gegen Manifest und Testfaelle pruefen."""
    manifest = {m["fall"]: m for m in map(json.loads, MANIFEST.read_text(encoding="utf-8").splitlines())}
    faelle = {t["id"]: t for t in map(json.loads, TESTDATEN.read_text(encoding="utf-8").splitlines())}
    fehler = 0
    for f in FAELLE:
        f = dict(f)
        m, t = manifest.get(f["id"]), faelle.get(f["id"])
        probleme = []
        if not m or not t:
            probleme.append("fehlt in Manifest oder Testfaellen")
        else:
            im, _ = ausschnitt(f)
            datei = TESTPLAN / t["metadata"]["bild"]
            if not datei.exists():
                probleme.append("Bilddatei fehlt")
            elif hashlib.sha256(datei.read_bytes()).hexdigest() != m["sha256"]:
                probleme.append("SHA-256 der Datei weicht ab")
            if pixel_sha(im) != m["pixel_sha256"]:
                probleme.append("Neu geschnittener Ausschnitt weicht ab (Pixel)")
            if t["metadata"]["sha256"] != m["sha256"]:
                probleme.append("Testfall und Manifest nennen verschiedene SHA-256")
            if not t["expected"]["value"].strip() or not m["lizenz"] or not m["quelle"]:
                probleme.append("Wahrheit, Lizenz oder Quelle leer")
            if "frage" not in f and t["expected"]["value"] != f.get("_wahrheit"):
                probleme.append("Wahrheit weicht von der Edition ab")
        fehler += bool(probleme)
        print(f"{'ok ' if not probleme else 'ABW'} {f['id']:16} {'; '.join(probleme)}")
    print(f"{len(FAELLE) - fehler}/{len(FAELLE)} ok")
    return 1 if fehler else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pruefen", action="store_true", help="neu schneiden und gegen das Manifest pruefen")
    args = ap.parse_args()
    return pruefen() if args.pruefen else bauen()


if __name__ == "__main__":
    sys.exit(main())
