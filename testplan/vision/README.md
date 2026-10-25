# Vision: Testbilder

Echte Scans und Grafiken für die Vision-Dimension (Plan: `docs/vision-dimension-plan.md`).
Die **Vorstufe** hat zehn Fälle: je zwei Transkriptionen aus Fraktur, Kurrent,
Frühneuhochdeutsch und Latein, dazu zwei Fragen zum Bildverständnis. Die Wahrheit stammt
von den Editoren der Datensätze, nicht von uns.

## Was wo liegt

| Pfad | Inhalt | im Repo |
|---|---|---|
| `vision/bauen.py` | lädt die Quellen, schneidet die Ausschnitte, schreibt Manifest und Testfälle | ja |
| `vision/sources.jsonl` | Manifest: je Fall Quelle (DOI/URL), Version, Urheber, Lizenz, Zeilen-IDs, Box, Prüfsummen | ja |
| `testdata/vision/vorstufe.jsonl` | Testfälle für den Harness (`category: vision`) | ja |
| `vision/quellen/` | Downloads | nein |
| `vision/ausschnitte/` | die Bilder der Fälle | nein, sie kommen in den Datensatz auf Hugging Face |

## Quellen und Lizenzen

Am 25.10.2026 an der Quelle geprüft, Zenodo-Lizenzen über die API.

| Fälle | Quelle | Lizenz |
|---|---|---|
| Fraktur (2) | Reichsanzeiger-GT, UB Mannheim, Zenodo 10144428 | CC BY 4.0; Scans Public Domain Mark |
| Kurrent (2) | Kurrent 19. Jh., Teil Senatsprotokolle Tübingen, Zenodo 17252677 | CC BY 4.0; Scans gemeinfrei (UB Tübingen) |
| Frühneuhochdeutsch (2) | Formelbuch BayHStA, Zenodo 21257167 und 21438740 | CC BY 4.0 |
| Latein (2) | e-NDP, Register von Notre-Dame, Zenodo 7575693 | CC BY 4.0 |
| Tabelle (1) | Destatis, Statistisches Jahrbuch 2019, Kap. 1, S. 15 | Verbreitung mit Quellenangabe, Seite unverändert |
| Karte (1) | DWD, Bodenanalyse 24.10.2026 00 UTC | CC BY 4.0 |

Nicht verwendet: aus Zenodo 17252677 die Teile „Digitale Schriftkunde“ (Transkription
CC BY-NC-SA) und Deutsches Textarchiv.

## Ausschnitte

Ein Transkriptionsfall ist ein Block von 6 bis 15 Zeilen, festgehalten über die
Zeilen-IDs der PAGE-XML. Die längste Seite wird auf höchstens 1600 px verkleinert, nie
vergrößert. Weil sich Handschriftzeilen überlappen, wird alles außerhalb der Polygone der
gewählten Zeilen mit der Papierfarbe gefüllt: Sonst stünden Teile der Nachbarzeilen im
Bild, die nicht zur Wahrheit gehören. Die Destatis-Seite wird nur gerendert, nicht
bearbeitet.

**Entscheidung 25.10.2026 für den vollen Katalog: reines Rechteck, nichts verändern.**
Das Füllen bleibt nur in den zehn Fällen der Vorstufe. Ab dem vollen Katalog wird
ausschließlich rechteckig geschnitten; gewählt werden nur Blöcke, in deren Rechteck kein
Polygon einer Nachbarzeile hineinragt — sonst läse ein Modell Zeilen mit, die nicht zur
Wahrheit gehören, und seine Fehlerrate stiege ohne eigenen Fehler.

## Neu bauen und prüfen

Aus `testplan/`, mit Pillow und `pdftoppm` (poppler-utils):

```bash
python3 vision/bauen.py            # lädt nur, was fehlt; aus großen Archiven per HTTP-Range
python3 vision/bauen.py --pruefen  # schneidet neu und vergleicht mit dem Manifest
```

`--pruefen` vergleicht die SHA-256 der Bilddatei und eine Prüfsumme über die Pixel des
neu geschnittenen Ausschnitts; jede Abweichung beendet mit Exitcode 1. Die DWD-Karte liegt
auf dem Open-Data-Server nur wenige Tage; danach baut nur noch die eigene Kopie den Fall.

## Vorstufe gemessen (25.10.2026)

Nemotron-3.5-Super-VL-120B über `--playbooks 09_vision` (Zeile
`Nemotron-3.5-Super-VL-120B-Vision`, Lauf `reports/2026-10-25_2119`, 10 min ohne Laden):

| Gruppe | CER normalisiert | zeichengetreu | Ergebnis |
|---|---|---|---|
| T2 Fraktur (Reichsanzeiger) | 0,019 / 0,024 | 0,042 / 0,058 | bestanden |
| T4 Frühneuhochdeutsch | 0,294 / 0,313 | 0,310 / 0,344 | nicht bestanden |
| T3 Kurrent | 0,528 / 0,439¹ | 0,522 / 0,434 | nicht bestanden |
| T5 Latein (e-NDP) | 0,581 / 0,703 | 0,585 / 0,705 | nicht bestanden |
| V Bildverständnis | — | — | beide richtig |

¹ abgeschnitten: Budget von 2048 Token ausgeschöpft, die Denkphase nahm den Großteil.

Was die Vorstufe beantwortet:

- **Bildkanal und Profil tragen.** Alle zehn Bilder kamen an (data-URI,
  `--chat-template-content-format openai`).
- **Budget:** 2048 Ausgabetoken reichen für denkende Modelle nicht. Für den vollen
  Katalog 16384 je Transkriptionsfall.
- **Druck trennt nicht, Handschrift trennt womöglich alle aus.** Fraktur liest das
  stärkste VL-Modell fast fehlerfrei, Handschrift gar nicht unter der geplanten Grenze
  von 20 %. Die zeichengetreue und die normalisierte CER liegen dort fast gleich auf —
  es sind Lesefehler, keine Schreibvarianten. Ob Handschrift überhaupt trennt, zeigt
  erst der Vergleich mit den OCR-Spezialisten; bis dahin wird die CER als stetiger Wert
  berichtet und die Grenze erst nach dem vollen Lauf festgelegt.
- Beim Latein mischt das Modell englische Bruchstücke ein („The official …“) — ein
  Lesefehler, der als Halluzination auftritt.

