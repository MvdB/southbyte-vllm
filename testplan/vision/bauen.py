#!/usr/bin/env python3
"""Vision-Katalog: Quellen laden, Ausschnitte schneiden, Manifest und Testfaelle schreiben.

Baut den Katalog der Vision-Dimension (docs/vision-dimension-plan.md) aus echten
Scans mit Editoren-Transkription, echten Statistikseiten und einer Wetterkarte.
Geladen wird nur, was die Faelle brauchen: aus grossen Zenodo-Archiven (Kurrent
7,8 GB, e-NDP 0,9 GB) holt das Skript einzelne Dateien per HTTP-Range.

Ausschnitte sind REINE RECHTECKE, nichts wird gefuellt oder maskiert
(Nutzerentscheid 25.10.2026). Deshalb sind nur Bloecke gewaehlt, in deren
Rechteck keine fremde Zeile steht; der Bau prueft das bei jedem Lauf:

  * schnitt "polygon": kein Polygon einer anderen Zeile ragt in das Rechteck
    (Rand bis 0,35 Zeilenhoehen, so gross wie ohne Ueberschneidung moeglich);
  * schnitt "grundlinie" (dichte Handschrift, deren Zeilenpolygone sich immer
    ueberlappen): Kanten an den Grundlinien, keine fremde Grundlinie und kein
    Polygon einer Randzeile im Rechteck. Gewaehlt nur Bloecke, die oben und
    unten an eine Luecke oder den Textrand stossen; jeder Ausschnitt angesehen.

Aufruf aus testplan/:
    python3 vision/bauen.py            # laden (falls noetig), schneiden, schreiben
    python3 vision/bauen.py --pruefen  # neu schneiden und gegen das Manifest pruefen

Schreibt:
    vision/quellen/                  Downloads (nicht im Repo)
    vision/ausschnitte/<id>.png      Ausschnitte (nicht im Repo, kommen in den HF-Datensatz)
    vision/sources.jsonl             Manifest: Quelle, Lizenz, Zeilen, Box, Pruefsummen
    testdata/vision/katalog.jsonl    Testfaelle fuer den Harness

Braucht Pillow und fuer die Destatis-Seiten pdftoppm (poppler-utils).
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
from pathlib import Path

from PIL import Image

TESTPLAN = Path(__file__).resolve().parent.parent
VISION = TESTPLAN / "vision"
QUELLEN_DIR = VISION / "quellen"
AUSSCHNITTE = VISION / "ausschnitte"
MANIFEST = VISION / "sources.jsonl"
TESTDATEN = TESTPLAN / "testdata" / "vision" / "katalog.jsonl"

MAX_SEITE = 1600          # laengste Seite eines Ausschnitts in Pixeln (nur verkleinern)
RAND_FAKTOR = 0.35        # groesster Rand um den Zeilenblock, als Anteil der mittleren Zeilenhoehe
GRUNDLINIE_ANTEIL = 0.42  # schnitt "grundlinie": Kante so weit unter der eigenen bzw. ueber der fremden Grundlinie
UA = "Wget/1.21.4 (southbyte-vllm vision/bauen.py)"  # UB Mannheim lehnt urllib-Kennung ab
LIZENZ_GEPRUEFT = "2026-10-25"

# --------------------------------------------------------------------------- Quellen
# Lizenz je Datensatz am 25.10.2026 ueber die Zenodo-API (metadata.license.id = cc-by-4.0
# bei allen fuenf) bzw. an der Quelle geprueft. "lizenz" ist die Lizenz, unter der wir den
# Ausschnitt weitergeben.
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
        "titel": "Statistisches Jahrbuch 2019, Kapitel 1 Geografie und Klima",
        "urheber": "Statistisches Bundesamt (Destatis)",
        "lizenz": "Destatis: Verbreitung mit Quellenangabe gestattet",
        "lizenz_hinweis": "Ganze Seiten unveraendert (nur gerendert), keine Bearbeitung; Seiten mit "
                          "Fremdkarten (© EuroGeographics, GeoBasis) ausgeschlossen; Datenquellen je "
                          "Tabelle auf der Seite genannt",
    },
    "dwd": {
        "quelle": "https://opendata.dwd.de/weather/charts/analysis/Z__C_EDZW_20261024085029_tka01%2Cana_bwkman_dwdc_O_000000_000000_202610240000_WV12.png",
        "version": "Bodenanalyse 24.10.2026 00 UTC (korrigierte Fassung, erzeugt 08:50 UTC)",
        "titel": "Bodenwetterkarte Analyse Europa/Nordatlantik, 24.10.2026 00 UTC",
        "urheber": "Deutscher Wetterdienst",
        "lizenz": "CC BY 4.0",
        "lizenz_hinweis": "DWD-Rechtshinweis: Inhalte unter CC BY 4.0 mit Quellenangabe; "
                          "Open-Data-Server haelt Karten nur wenige Tage vor — danach baut nur die "
                          "eigene Kopie (SHA-256 im Manifest) den Fall",
    },
}

T_AUFGABE = ("Transkribiere den Text im Bild genau so, wie er dasteht, Zeile für Zeile. "
             "Nicht übersetzen, nicht modernisieren, Abkürzungen nicht auflösen. "
             "Gib nur den Text aus.")
T_AUFGABE_LATEIN = ("Transkribiere den lateinischen Text im Bild Zeile für Zeile. Löse die "
                    "Abkürzungen dabei auf (zum Beispiel dñs → dominus), übersetze nicht. "
                    "Gib nur den Text aus.")
FALLE_ZUSATZ = " Wenn das Bild diese Angabe nicht enthält, antworte mit „nicht im Bild“."

# --------------------------------------------------------------------------- Faelle
# Transkription: Zeilen ueber ihre PAGE-IDs, in Lesereihenfolge.
FAELLE = [
    {"id": "vis-fraktur-001", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger", "seite": "1834_239_0518", "film": "022-9903/0518.jp2&CVT=jpeg", "schnitt": "polygon", "schrift": "druck", "normalisierung": "fraktur",
     "zeilen": ["r52l2", "r52l3", "r52l4", "r52l5",
                "r52l6", "r52l7", "r52l8", "r52l9",
                "r52l10"]},
    {"id": "vis-fraktur-002", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger", "seite": "1841_81_0181", "film": "029-9910/0181.jp2&CVT=jpeg", "schnitt": "polygon", "schrift": "druck", "normalisierung": "fraktur",
     "zeilen": ["r2l118", "r2l119", "r2l120", "r2l121",
                "r2l122", "r2l123", "r2l124", "r2l125"]},
    {"id": "vis-fraktur-003", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger", "seite": "1877_7_0059", "film": "027-7946/0059.jp2&CVT=jpeg", "schnitt": "polygon", "schrift": "druck", "normalisierung": "fraktur",
     "zeilen": ["r30l1", "r30l2", "r30l3", "r30l4",
                "r30l5", "r30l6", "r30l7", "r30l8",
                "r30l9", "r30l10"]},
    {"id": "vis-fraktur-004", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger", "seite": "1893_2_0023", "film": "117-8036/0023.jp2&CVT=jpeg", "schnitt": "polygon", "schrift": "druck", "normalisierung": "fraktur",
     "zeilen": ["r15l1", "r15l2", "r15l3", "r15l4",
                "r15l5", "r15l6", "r15l7", "r15l8",
                "r15l9", "r15l10", "r15l11", "r15l12"]},
    {"id": "vis-fraktur-005", "subcategory": "T2_fraktur", "quelle": "reichsanzeiger", "seite": "1910_299_0335", "film": "103-9511/0335.jp2&CVT=jpeg", "schnitt": "polygon", "schrift": "druck", "normalisierung": "fraktur",
     "zeilen": ["r16l1", "r16l2", "r16l3", "r16l4",
                "r16l5", "r16l6", "r16l7", "r16l8",
                "r16l9", "r16l10", "r16l11"]},
    {"id": "vis-kurrent-001", "subcategory": "T3_kurrent", "quelle": "kurrent", "seite": "UAT_047_20a_168", "schnitt": "polygon", "schrift": "hand", "normalisierung": "kurrent",
     "zeilen": ["r1l1", "r1l2", "r1l3", "r1l4",
                "r1l5", "r1l6", "r1l7", "r1l8"]},
    {"id": "vis-kurrent-002", "subcategory": "T3_kurrent", "quelle": "kurrent", "seite": "UAT_047_20a_169", "schnitt": "polygon", "schrift": "hand", "normalisierung": "kurrent",
     "zeilen": ["r3l1", "r2l1", "line_1624702045555_232", "line_1624702044464_226",
                "r2l3", "r2l4", "r2l5", "r2l6",
                "r2l7", "r2l8", "r2l9"]},
    {"id": "vis-kurrent-003", "subcategory": "T3_kurrent", "quelle": "kurrent", "seite": "UAT_047_20a_329", "schnitt": "polygon", "schrift": "hand", "normalisierung": "kurrent",
     "zeilen": ["r2l3", "r2l4", "r2l5", "r2l6",
                "r2l7", "r2l9", "r2l10", "r2l11",
                "r2l12", "r2l13", "r2l14", "r2l15"]},
    {"id": "vis-kurrent-004", "subcategory": "T3_kurrent", "quelle": "kurrent", "seite": "UAT_047_25_078", "schnitt": "polygon", "schrift": "hand", "normalisierung": "kurrent",
     "zeilen": ["r2l1", "r2l2", "r2l3", "r2l4",
                "r2l5", "r2l6", "r2l7", "r2l8",
                "r2l9", "r2l10"]},
    {"id": "vis-kurrent-005", "subcategory": "T3_kurrent", "quelle": "kurrent", "seite": "UAT_047_28_574", "schnitt": "polygon", "schrift": "hand", "normalisierung": "kurrent",
     "zeilen": ["r2l1", "r2l2", "r2l3", "r2l4",
                "r2l5", "r2l6", "r2l7", "r2l8"]},
    {"id": "vis-fnhd-001", "subcategory": "T4_fnhd", "quelle": "wasserschaden", "seite": "BayHStA_AS_Lit_Oe_463_183r", "schnitt": "grundlinie", "schrift": "hand", "normalisierung": "fnhd",
     "zeilen": ["eSc_line_bdca4e8f", "eSc_line_ef04037c", "eSc_line_49bbc4dc", "eSc_line_6633abd2",
                "eSc_line_6f7e171a", "eSc_line_a67c42e4", "eSc_line_1bf64570", "eSc_line_9dc1ed12",
                "eSc_line_cf4e9a9b", "eSc_line_fd7c35d3", "eSc_line_437424e5", "eSc_line_3afe1275",
                "eSc_line_5a1a0a53", "eSc_line_6f263a9f"]},
    {"id": "vis-fnhd-002", "subcategory": "T4_fnhd", "quelle": "formelbuch", "seite": "BayHStA_AS_Lit_Oe_463_365r", "schnitt": "grundlinie", "schrift": "hand", "normalisierung": "fnhd",
     "zeilen": ["eSc_line_01fa2352", "eSc_line_2c5857f9", "eSc_line_68f9597a", "eSc_line_aec7f937",
                "eSc_line_611b184f", "eSc_line_2d98f3e9", "eSc_line_a7edf126", "eSc_line_cee51ee2",
                "eSc_line_f9323771", "eSc_line_2f1b59ad", "eSc_line_f9c94724", "eSc_line_1c7d9e5f",
                "eSc_line_0f8e53f7"]},
    {"id": "vis-latein-001", "subcategory": "T5_latein", "quelle": "endp", "seite": "FRAN_0393_00310_L", "schnitt": "polygon", "schrift": "hand", "normalisierung": "latein",
     "zeilen": ["eSc_line_d5af68c3", "eSc_line_b21f52db", "eSc_line_79927ebe", "eSc_line_8009d3a9",
                "eSc_line_edd19ded", "eSc_line_20b25bf2", "eSc_line_0a74746b", "eSc_line_a36c23a3",
                "eSc_line_62983122"]},
    {"id": "vis-latein-002", "subcategory": "T5_latein", "quelle": "endp", "seite": "FRAN_0393_00463_L", "schnitt": "polygon", "schrift": "hand", "normalisierung": "latein",
     "zeilen": ["eSc_line_1e71ad26", "eSc_line_d60dc7cb", "eSc_line_ae70e5a6", "eSc_line_f455aee9",
                "eSc_line_77291c3b", "eSc_line_50a82c85"]},
    {"id": "vis-latein-003", "subcategory": "T5_latein", "quelle": "endp", "seite": "FRAN_0393_01065_L", "schnitt": "polygon", "schrift": "hand", "normalisierung": "latein",
     "zeilen": ["r2l6", "r2l7", "r2l8", "r2l9",
                "r2l10", "r2l11", "r2l12", "r2l13",
                "r2l14"]},
    {"id": "vis-latein-004", "subcategory": "T5_latein", "quelle": "endp", "seite": "FRAN_0393_01126_L", "schnitt": "polygon", "schrift": "hand", "normalisierung": "latein",
     "zeilen": ["r5l1", "r5l2", "r5l3", "r5l4",
                "r5l5", "r5l6"]},
    {"id": "vis-latein-005", "subcategory": "T5_latein", "quelle": "endp", "seite": "FRAN_0393_05506_L", "schnitt": "polygon", "schrift": "hand", "normalisierung": "latein",
     "zeilen": ["eSc_line_599586b6", "eSc_line_c6b1d8c4", "eSc_line_ae1b123e", "eSc_line_96fa063e",
                "eSc_line_5d0404bc", "eSc_line_033ab7ae", "eSc_line_11950d31", "eSc_line_94b34780",
                "eSc_line_420a31c4"]},
    # --- V Bildverstaendnis: ganze Seiten bzw. ganze Grafik, kurze pruefbare Antwort
    {"id": "vis-bild-001", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 5,
     "frage": "Wie hoch liegt Bad Tölz laut der Tabelle „Ausgewählte Ortshöhenlagen“? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "670 m", "alternativen": ["670 m über NN", "670 Meter"]},
    {"id": "vis-bild-002", "subcategory": "V_karte", "quelle": "dwd",
     "frage": "Welches Tiefdruckgebiet ist in dieser Wetterkarte mit einem Namen beschriftet? "
              "Antworte nur mit dem Namen.",
     "antwort": "Ex-Josephine", "alternativen": ["Josephine"]},
    {"id": "vis-bild-003", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 4,
     "frage": "Wie lang ist laut der Tabelle „Länge der Grenzen“ die Grenze Deutschlands zu den "
              "Niederlanden? Antworte nur mit der Zahl und der Einheit.",
     "antwort": "576 km", "alternativen": ["576 Kilometer"]},
    {"id": "vis-bild-004", "subcategory": "V_text", "quelle": "destatis", "pdf_seite": 6,
     "frage": "Wie viele Kilometer Bundesautobahnen nennt diese Seite für 2018? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "13 009 km", "alternativen": ["13009 km", "13 009 Kilometer", "13009 Kilometer"]},
    {"id": "vis-bild-005", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 6,
     "frage": "Wie tief ist der Chiemsee an seiner tiefsten Stelle laut der Tabelle „Natürliche Seen“? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "73 m", "alternativen": ["73 Meter"]},
    {"id": "vis-bild-006", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 7,
     "frage": "Wie groß ist die Wasserfläche des Edersees bei Vollstau laut der Tabelle „Stauseen“? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "12,0 km²", "alternativen": ["12 km²", "12,0 km2", "12 km2", "12,0 Quadratkilometer",
                                            "12 Quadratkilometer"]},
    {"id": "vis-bild-007", "subcategory": "V_tabelle", "quelle": "destatis", "pdf_seite": 7,
     "frage": "Wie groß ist die Insel Fehmarn laut der Tabelle „Größte Inseln“? "
              "Antworte nur mit der Zahl und der Einheit.",
     "antwort": "185 km²", "alternativen": ["185 km2", "185 Quadratkilometer"]},
    {"id": "vis-bild-008", "subcategory": "V_diagramm", "quelle": "destatis", "pdf_seite": 9,
     "frage": "Auf welcher Höhe liegt die Wetterstation Freudenstadt laut der Seite "
              "„Klimatische Verhältnisse“? Antworte nur mit der Zahl und der Einheit.",
     "antwort": "797 m", "alternativen": ["797 m ü. NN", "797 Meter"]},
    # --- H Halluzinationsfallen: Bild eines anderen Falls, gefragt nach etwas, das fehlt.
    # "verboten" prueft der Evaluator als Teilzeichenkette: nur Werte, die allein beim
    # Erfinden auftauchen (nie Einheiten oder Zahlen, die im Bild stehen).
    {"id": "vis-falle-001", "subcategory": "H_falle", "bild_von": "vis-bild-003",
     "frage": "Wie lang ist laut der Tabelle „Länge der Grenzen“ die Grenze Deutschlands zu Italien?",
     "verboten": []},
    {"id": "vis-falle-002", "subcategory": "H_falle", "bild_von": "vis-bild-006",
     "frage": "Welchen Stauraum bei Vollstau nennt die Tabelle „Stauseen“ für die Rurtalsperre Obermaubach?",
     "verboten": []},
    {"id": "vis-falle-003", "subcategory": "H_falle", "bild_von": "vis-bild-008",
     "frage": "Auf welcher Höhe liegt laut dieser Seite die Wetterstation Berlin-Tempelhof?",
     "verboten": ["48 m"]},   # echte Hoehe der Station, nur aus dem Gedaechtnis
    {"id": "vis-falle-004", "subcategory": "H_falle", "bild_von": "vis-bild-002",
     "frage": "Welche Windgeschwindigkeit in km/h ist in dieser Wetterkarte für Hamburg angegeben?",
     "verboten": []},
    {"id": "vis-falle-005", "subcategory": "H_falle", "bild_von": "vis-fraktur-003",
     "frage": "In welchem Jahr wurde die Firma „Schmidt & Witthauer“ laut dieser Anzeige gegründet?",
     "verboten": []},   # 1877 steht im Bild (Datum der Anzeige)
    {"id": "vis-falle-006", "subcategory": "H_falle", "bild_von": "vis-kurrent-001",
     "frage": "Wie alt ist Christian Gustav Schmid laut diesem Protokollauszug?",
     "verboten": ["Jahre alt"]},
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


def _punkte(s: str) -> list[tuple[int, int]]:
    return [tuple(int(float(v)) for v in p.split(",")) for p in s.split()]


def page_zeilen(xml: Path) -> list[dict]:
    """Alle TextLines: id, region, Polygon, Grundlinie, Text (erstes TextEquiv der Zeile).
    Die Koordinaten stehen im Pixelraum der Bilddatei (bei einzelnen Kurrent-Seiten weicht das
    Attribut imageWidth davon ab; massgeblich sind die Koordinaten)."""
    root = ET.parse(xml).getroot()
    out = []
    for reg in root.iter():
        if _lokal(reg.tag) != "TextRegion":
            continue
        for ln in reg:
            if _lokal(ln.tag) != "TextLine":
                continue
            pts, text, basis = None, None, None
            for k in ln:
                if _lokal(k.tag) == "Coords" and pts is None:
                    pts = _punkte(k.get("points", ""))
                if _lokal(k.tag) == "Baseline" and basis is None:
                    basis = _punkte(k.get("points", ""))
                if _lokal(k.tag) == "TextEquiv" and text is None:
                    u = next((u for u in k if _lokal(u.tag) == "Unicode"), None)
                    text = (u.text or "") if u is not None else ""
            if pts and text is not None:
                xs, ys = [x for x, _ in pts], [y for _, y in pts]
                out.append({"id": ln.get("id"), "region": reg.get("id"), "punkte": pts, "basis": basis,
                            "text": text, "bb": (min(xs), min(ys), max(xs), max(ys))})
    return out


# --------------------------------------------------------------------------- Rechtecke
def _clip(poly: list, box: tuple) -> list:
    """Polygon auf das Rechteck beschneiden (Sutherland-Hodgman)."""
    x0, y0, x1, y1 = box
    p = [tuple(map(float, q)) for q in poly]
    for innen, schnitt in (
            (lambda q: q[0] >= x0, lambda a, b: (x0, a[1] + (x0 - a[0]) * (b[1] - a[1]) / ((b[0] - a[0]) or 1))),
            (lambda q: q[0] <= x1, lambda a, b: (x1, a[1] + (x1 - a[0]) * (b[1] - a[1]) / ((b[0] - a[0]) or 1))),
            (lambda q: q[1] >= y0, lambda a, b: (a[0] + (y0 - a[1]) * (b[0] - a[0]) / ((b[1] - a[1]) or 1), y0)),
            (lambda q: q[1] <= y1, lambda a, b: (a[0] + (y1 - a[1]) * (b[0] - a[0]) / ((b[1] - a[1]) or 1), y1))):
        if not p:
            return []
        neu = []
        for i in range(len(p)):
            a, b = p[i - 1], p[i]
            if innen(b):
                if not innen(a):
                    neu.append(schnitt(a, b))
                neu.append(b)
            elif innen(a):
                neu.append(schnitt(a, b))
        p = neu
    return p


def _flaeche(p: list) -> float:
    return abs(sum(p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1] for i in range(len(p)))) / 2 if len(p) > 2 else 0.0


def _schneidet(z: dict, box: tuple) -> bool:
    bb = z["bb"]
    if not (bb[0] < box[2] and bb[2] > box[0] and bb[1] < box[3] and bb[3] > box[1]):
        return False
    return _flaeche(_clip(z["punkte"], box)) > 1.0


def rechteck_polygon(block: list[dict], alle: list[dict], breite: int, hoehe: int) -> tuple[tuple, int]:
    """Groesstes Rechteck um den Block (Rand RAND_FAKTOR Zeilenhoehen abwaerts bis 0), in das kein
    Polygon einer anderen Zeile ragt."""
    ids = {z["id"] for z in block}
    xs = [x for z in block for x, _ in z["punkte"]]
    ys = [y for z in block for _, y in z["punkte"]]
    h = statistics.median(z["bb"][3] - z["bb"][1] for z in block)
    andere = [z for z in alle if z["id"] not in ids]
    for schritt in range(10, -1, -1):
        rand = round(RAND_FAKTOR * h * schritt / 10)
        box = (max(0, min(xs) - rand), max(0, min(ys) - rand), min(breite, max(xs) + rand),
               min(hoehe, max(ys) + rand))
        if not any(_schneidet(z, box) for z in andere):
            return box, rand
    raise ValueError("Nachbarzeile ragt schon in die Bounding-Box des Blocks")


def rechteck_grundlinie(block: list[dict], alle: list[dict], breite: int, hoehe: int) -> tuple[tuple, int]:
    """Rechteck mit Kanten an den Grundlinien, fuer dichte Handschrift. Unten hoechstens
    GRUNDLINIE_ANTEIL Zeilenabstaende unter der letzten eigenen Grundlinie und so weit ueber der
    folgenden, dass deren Oberlaengen draussen bleiben; oben entsprechend. Randzeilen (andere
    Spalten, Marginalien) duerfen nicht hineinragen, Grundlinien direkter Nachbarn nicht im
    Rechteck liegen."""
    if any(not z["basis"] for z in block):
        raise ValueError("Zeile ohne Grundlinie")
    ids = {z["id"] for z in block}
    by = [statistics.median(y for _, y in z["basis"]) for z in block]
    abstand = statistics.median(b - a for a, b in zip(by, by[1:]))
    x0, x1 = min(z["bb"][0] for z in block), max(z["bb"][2] for z in block)
    y0, y1 = min(z["bb"][1] for z in block), max(z["bb"][3] for z in block)
    def ueber_x(z):
        return z["bb"][0] < x1 and z["bb"][2] > x0
    andere = [z for z in alle if z["id"] not in ids and z["basis"] and ueber_x(z)]
    mitte = lambda z: statistics.median(y for _, y in z["basis"])
    darueber = [z for z in andere if mitte(z) < by[0]]
    darunter = [z for z in andere if mitte(z) > by[-1]]
    if darueber and by[0] - max(mitte(z) for z in darueber) < 2.5 * abstand:
        y0 = max(y0, max(max(y for _, y in z["basis"]) for z in darueber) + GRUNDLINIE_ANTEIL * abstand)
    if darunter and min(mitte(z) for z in darunter) - by[-1] < 2.5 * abstand:
        y1 = min(y1, max(y for _, y in block[-1]["basis"]) + GRUNDLINIE_ANTEIL * abstand,
                 min(min(y for _, y in z["basis"]) for z in darunter) - (1 - GRUNDLINIE_ANTEIL) * abstand)
    rand = round(0.15 * abstand)
    box = (max(0, int(x0 - rand)), max(0, int(y0)), min(breite, int(x1 + rand)), min(hoehe, int(y1)))
    for z in alle:
        if z["id"] in ids:
            continue
        if z in darueber or z in darunter:
            if box[1] < mitte(z) < box[3]:
                raise ValueError(f"Grundlinie von {z['id']} liegt im Rechteck")
        elif _schneidet(z, box):
            raise ValueError(f"Randzeile {z['id']} ragt ins Rechteck")
    return box, rand


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
                    "box": None, "skalierung": None, "zeilen_ids": None, "schnitt": None}
    if f["quelle"] == "dwd":
        im = Image.open(bildpfad).convert("RGB")
        im, faktor = _verkleinern(im)
        return im, {"datei_im_datensatz": bildpfad.name, "seite": None, "box": None,
                    "skalierung": round(faktor, 6), "zeilen_ids": None, "schnitt": None}
    alle = page_zeilen(xml)
    nach_id = {z["id"]: z for z in alle}
    zeilen = [nach_id[i] for i in f["zeilen"]]
    if not 6 <= len(zeilen) <= 15:
        raise ValueError(f"{f['id']}: {len(zeilen)} Zeilen, erwartet 6 bis 15")
    with Image.open(bildpfad) as orig:
        orig.load()
        if max(z["bb"][2] for z in zeilen) > orig.width or max(z["bb"][3] for z in zeilen) > orig.height:
            raise ValueError(f"{f['id']}: Zeilen liegen ausserhalb des Bildes {orig.size}")
        verfahren = rechteck_grundlinie if f["schnitt"] == "grundlinie" else rechteck_polygon
        try:
            box, rand = verfahren(zeilen, alle, orig.width, orig.height)
        except ValueError as e:
            raise ValueError(f"{f['id']}: {e}") from None
        im = _modus(orig.crop(box))
    im, faktor = _verkleinern(im)
    f["_wahrheit"] = "\n".join(z["text"] for z in zeilen)
    return im, {"datei_im_datensatz": bildpfad.name, "seite": f.get("seite"), "box": list(box),
                "rand_px": rand, "skalierung": round(faktor, 6), "zeilen_ids": [z["id"] for z in zeilen],
                "xml": xml.name, "schnitt": f["schnitt"]}


def png_bytes(im: Image.Image) -> bytes:
    puffer = io.BytesIO()
    im.save(puffer, "PNG", optimize=False)
    return puffer.getvalue()


def pixel_sha(im: Image.Image) -> str:
    h = hashlib.sha256(f"{im.mode}:{im.width}x{im.height}:".encode())
    h.update(im.tobytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- Ausgabe
def _schrift(f: dict) -> str:
    return f.get("schrift", "druck")


def _normalisierung(f: dict) -> str:
    return f.get("normalisierung", "modern")


def testfall(f: dict, meta: dict, sha: str, im: Image.Image, quelle: str, bild_id: str) -> dict:
    art = "falle" if "bild_von" in f else ("antwort" if "frage" in f else "transkription")
    if art == "transkription":
        aufgabe = T_AUFGABE_LATEIN if f["normalisierung"] == "latein" else T_AUFGABE
        erwartet = {"type": "transkription", "value": f["_wahrheit"]}
    elif art == "antwort":
        aufgabe = f["frage"]
        erwartet = {"type": "antwort", "value": f["antwort"], "alternatives": f.get("alternativen", [])}
    else:
        aufgabe = f["frage"] + FALLE_ZUSATZ
        erwartet = {"type": "falle", "value": "nicht im Bild", "forbidden": f.get("verboten", [])}
    return {
        "id": f["id"], "category": "vision", "subcategory": f["subcategory"],
        "language": "la" if _normalisierung(f) == "latein" else "de",
        "difficulty": "hard" if _schrift(f) == "hand" else "medium",
        "prompt": aufgabe, "expected": erwartet,
        "max_tokens": 16384 if art == "transkription" else 4096,
        "metadata": {
            "bild": f"vision/ausschnitte/{bild_id}.png", "sha256": sha, "breite": im.width, "hoehe": im.height,
            "schrift": _schrift(f), "normalisierung": _normalisierung(f), "quelle": quelle,
            "lizenz": QUELLEN[quelle]["lizenz"],
            "zeilen": len(meta["zeilen_ids"]) if meta.get("zeilen_ids") and art == "transkription" else None,
            **({"bild_von": f["bild_von"]} if art == "falle" else {}),
        },
    }


def manifestzeile(f: dict, meta: dict, sha: str, psha: str, quelle: str, bild_id: str) -> dict:
    Q = QUELLEN[quelle]
    if "bild_von" in f:
        bearbeitung = f"kein eigenes Bild; Frage zum Bild von {f['bild_von']}"
    elif meta.get("zeilen_ids"):
        verfahren = ("kein Polygon einer anderen Zeile im Rechteck" if meta["schnitt"] == "polygon"
                     else "Kanten an den Grundlinien, keine fremde Grundlinie im Rechteck")
        bearbeitung = (f"reines Rechteck um die genannten Zeilen ({verfahren}), "
                       + (f"verkleinert auf hoechstens {MAX_SEITE} px" if meta["skalierung"] < 1 else "unverkleinert")
                       + "; nichts gefuellt oder maskiert")
    elif quelle == "destatis":
        bearbeitung = "ganze Seite, unveraendert gerendert"
    else:
        bearbeitung = f"ganze Grafik, verkleinert auf hoechstens {MAX_SEITE} px"
    return {
        "fall": f["id"], "quelle_schluessel": quelle, "quelle": Q["quelle"], "version": Q["version"],
        "datensatz_titel": Q["titel"], "urheber": Q["urheber"], "lizenz": Q["lizenz"],
        "lizenz_hinweis": Q["lizenz_hinweis"], "lizenz_geprueft_am": LIZENZ_GEPRUEFT,
        **meta, "ausschnitt": f"{bild_id}.png", "sha256": sha, "pixel_sha256": psha, "bearbeitung": bearbeitung,
    }


def _alle_faelle() -> list[tuple[dict, Image.Image, dict, str, str]]:
    """(Fall, Bild, Meta, Quelle, Bild-ID) fuer alle Faelle; Fallen leihen sich Bild und Meta."""
    eigene, out = {}, []
    for f in FAELLE:
        f = dict(f)
        if "bild_von" in f:
            quelle_f, im, meta = eigene[f["bild_von"]]
            meta = {k: v for k, v in meta.items()}
            out.append((f, im, meta, quelle_f["quelle"], f["bild_von"]))
            continue
        im, meta = ausschnitt(f)
        eigene[f["id"]] = (f, im, meta)
        out.append((f, im, meta, f["quelle"], f["id"]))
    return out


def bauen() -> int:
    AUSSCHNITTE.mkdir(parents=True, exist_ok=True)
    TESTDATEN.parent.mkdir(parents=True, exist_ok=True)
    faelle, manifest = [], []
    for f, im, meta, quelle, bild_id in _alle_faelle():
        daten = png_bytes(im)
        if bild_id == f["id"]:
            (AUSSCHNITTE / f"{bild_id}.png").write_bytes(daten)
        sha = hashlib.sha256(daten).hexdigest()
        faelle.append(testfall(f, meta, sha, im, quelle, bild_id))
        manifest.append(manifestzeile(f, meta, sha, pixel_sha(im), quelle, bild_id))
        print(f"✓ {f['id']:17} {im.width}x{im.height}  {faelle[-1]['metadata']['zeilen'] or '-'} Zeilen")
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
    for f, im, _, _, bild_id in _alle_faelle():
        m, t = manifest.get(f["id"]), faelle.get(f["id"])
        probleme = []
        if not m or not t:
            probleme.append("fehlt in Manifest oder Testfaellen")
        else:
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
            if "_wahrheit" in f and t["expected"]["value"] != f["_wahrheit"]:
                probleme.append("Wahrheit weicht von der Edition ab")
        fehler += bool(probleme)
        print(f"{'ok ' if not probleme else 'ABW'} {f['id']:17} {'; '.join(probleme)}")
    print(f"{len(FAELLE) - fehler}/{len(FAELLE)} ok")
    return 1 if fehler else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pruefen", action="store_true", help="neu schneiden und gegen das Manifest pruefen")
    args = ap.parse_args()
    return pruefen() if args.pruefen else bauen()


if __name__ == "__main__":
    sys.exit(main())
