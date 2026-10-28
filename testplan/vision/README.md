# Vision: Testbilder

Echte Scans und Grafiken für die Vision-Dimension (Plan: `docs/vision-dimension-plan.md`).
Der **Katalog** hat derzeit **31 von 44 geplanten Fällen** (Stand 25.10.2026, siehe unten
„Was noch fehlt“). Die Wahrheit der Transkriptionen stammt von den Editoren der
Datensätze, nicht von uns; die Antworten zum Bildverständnis sind an der Textschicht der
Seite geprüft.

## Was wo liegt

| Pfad | Inhalt | im Repo |
|---|---|---|
| `vision/bauen.py` | lädt die Quellen, schneidet die Ausschnitte, prüft die Schnittregel, schreibt Manifest und Testfälle | ja |
| `vision/sources.jsonl` | Manifest: je Fall Quelle (DOI/URL), Version, Urheber, Lizenz, Zeilen-IDs, Box, Schnittverfahren, Prüfsummen | ja |
| `testdata/vision/katalog.jsonl` | Testfälle für den Harness (`category: vision`) | ja |
| `vision/quellen/` | Downloads | nein |
| `vision/ausschnitte/` | die Bilder der Fälle | nein, sie kommen in den Datensatz auf Hugging Face |

## Katalog

| Gruppe | Fälle | Quelle | Lizenz |
|---|---:|---|---|
| T2 Fraktur | 5 | Reichsanzeiger-GT, UB Mannheim, Zenodo 10144428 (Ausgaben 1834, 1841, 1877, 1893, 1910) | CC BY 4.0; Scans Public Domain Mark |
| T3 Kurrent | 5 | Kurrent 19. Jh., Teil Senatsprotokolle Tübingen, Zenodo 17252677 | CC BY 4.0; Scans gemeinfrei (UB Tübingen) |
| T4 Frühneuhochdeutsch | 2 | Formelbuch BayHStA, Zenodo 21257167 (f. 365r) und 21438740 (f. 183r) | CC BY 4.0 |
| T5 Latein | 5 | e-NDP, Register von Notre-Dame, Zenodo 7575693 | CC BY 4.0 |
| V Bildverständnis | 8 | Destatis, Statistisches Jahrbuch 2019, Kap. 1 (S. 4–7 und 9 des PDFs, 7 Fragen); DWD-Bodenanalyse 24.10.2026 (1 Frage) | Destatis: Verbreitung mit Quellenangabe, Seiten unverändert; DWD: CC BY 4.0 |
| H Halluzinationsfallen | 6 | Bilder aus V, T2 und T3, Frage nach etwas, das nicht im Bild steht | wie das Bild |
| T1 Modern | 0 von 6 | — | — |
| T6 Englisch | 0 von 4 | — | — |

Lizenzen am 25.10.2026 geprüft, die fünf Zenodo-Datensätze über die API
(`metadata.license.id = cc-by-4.0`). Nicht verwendet: aus Zenodo 17252677 die Teile
„Digitale Schriftkunde“ (Transkription CC BY-NC-SA) und Deutsches Textarchiv; Destatis-Seiten
mit Fremdkarten (© EuroGeographics).

Fallen antworten nach Vorgabe mit „nicht im Bild“, wenn die Angabe fehlt; `forbidden`
enthält nur Werte, die allein beim Erfinden auftauchen (der Evaluator prüft sie als
Teilzeichenkette — eine Einheit oder eine Zahl, die im Bild steht, würde eine korrekte
Absage als K.O. werten).

## Ausschnitte: reines Rechteck

**Nutzerentscheid 25.10.2026: reine Rechtecke, nichts gefüllt oder maskiert.** Gewählt sind
deshalb nur Blöcke von 6 bis 15 Zeilen, in deren Rechteck keine fremde Zeile steht — sonst
läse ein Modell Zeilen mit, die nicht zur Wahrheit gehören, und seine Fehlerrate stiege ohne
eigenen Fehler. `bauen.py` prüft das bei jedem Lauf und bricht sonst ab:

- **`polygon`** (Fraktur, Kurrent, Latein): kein Polygon einer anderen Zeile ragt ins
  Rechteck; Rand bis 0,35 Zeilenhöhen, so groß wie ohne Überschneidung möglich. Gefunden mit
  einer Suche über alle Seiten der Quellen; bevorzugt Blöcke mit großem Rand, Druck mit
  wenig Ziffern.
- **`grundlinie`** (Frühneuhochdeutsch): In den beiden Formelbuch-Datensätzen überlappen sich
  die Zeilenpolygone durchgehend (Zeilenabstand ~110 px, Polygone ~210 px hoch); die
  Polygonregel findet in 106 Seiten keinen einzigen Block. Die Kanten liegen deshalb an den
  Grundlinien: unten höchstens 0,42 Zeilenabstände unter der letzten eigenen Grundlinie und
  so weit über der folgenden, dass deren Oberlängen draußen bleiben; keine fremde Grundlinie
  und keine Randzeile im Rechteck. Gewählt sind nur ganze Einträge, die am Seitenende bzw.
  an einer Überschrift enden; die Überschrift gehört zur Wahrheit.

Jeder Ausschnitt ist angesehen. Durchscheinende Schrift der Rückseite bleibt (echtes Bild),
fremde Zeilenteile nicht. Die längste Seite wird auf höchstens 1600 px verkleinert, nie
vergrößert. Destatis-Seiten werden nur gerendert (159 dpi), nicht bearbeitet.

Die Zeilenkoordinaten stehen im Pixelraum der Bilddatei; bei einigen Kurrent-Seiten weicht das
Attribut `imageWidth` der PAGE-XML davon ab (halbe Auflösung), maßgeblich sind die
Koordinaten — `bauen.py` prüft, dass alle Zeilen im Bild liegen.

Die gefüllten Ausschnitte der Vorstufe (25.10., Lauf `reports/2026-10-25_2119`) sind
ausgemustert; ihr Bau steht in der Git-Geschichte (Commit a0d3878).

## Was noch fehlt (13 von 44)

- **T1 Modern (6)** und **T6 Englisch (4):** brauchen eine selbst erstellte bzw. zeilengenau
  zugeordnete Wahrheit (Commons-Fotos mit Revisions-ID; Library of Congress / US-Nationalarchiv
  ohne PAGE-Koordinaten) — Handarbeit je Fall.
- **T4 Frühneuhochdeutsch (3):** in den beiden Formelbuch-Datensätzen gibt es außer den zwei
  gewählten Einträgen keinen Block, der die Rechteckregel erfüllt (kein Absatzabstand,
  Überschriften zu dicht an der Vorzeile, Wasserschaden-Zeilen mit `#`). Eine weitere Quelle
  frühneuhochdeutscher Handschrift mit PAGE-GT und CC-BY-Lizenz wäre nötig.

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

## Erster voller Lauf (Nachtlauf 25./26.10.2026, Katalog 31)

Kohorte `reports/vision-2026-katalog-31/` (lokal; Läufe 2026-10-25_2226 und 2026-10-26_0350).
Median der normalisierten CER je Schriftlage, kleiner ist besser:

| Modell | Fraktur | Kurrent | Frühnhd. | Latein | Bildfragen | Fallen |
|---|---|---|---|---|---|---|
| Muse-Glimmer-30B-NVFP4 | 0,013 | 0,78 | 0,47 | 0,78 | 8/8 | 6/6 |
| Qwen3.8-27B (RadixArk) | 0,011 | 0,50 | 0,22 | 0,55 | 8/8 | 6/6 |
| Nemotron-3.5-Super-VL-120B | 0,035 | 0,66 | 0,34 | 0,85 | 8/8 | 6/6 |
| Ornith-1.5-122B | 0,008 | 0,55 | 0,51 | 0,62 | 8/8 | 5/6, 1 K.O. |
| Nemotron-3.5-Bolt-E4B | 0,025 | 0,59 | 0,52 | 0,52 | 2/8 | 6/6 |
| Gemma-4-E4B | 0,026 | 0,56 | 0,51 | 0,54 | 2/8 | 4/6 |
| Nemotron-3.5-Parse (OCR) | 0,086 | 0,52 | 0,28 | 0,60 | — | — |
| granite-docling-258M (OCR) | 0,33 | ≥ 1 | ≥ 1 | ≥ 1 | — | — |

- **Wertung (Entscheidung 26.10.):** Handschrift nur als CER, ohne Bestehensgrenze;
  bestanden zählen Druck (CER unter 10 %), Bildfragen und Fallen.
- **Nicht in der Kohorte:** Unlimited-OCR (leere Antworten und Schleifen — die Einrichtung
  ist noch nicht tragfähig), Qwen3.8-27B-Uncensored (der Bildprozessor scheitert an Bildern
  über ~2 MP, reproduzierbar auch mit GPU-Anteil 0,70; das Repo führt den Vision-Teil als
  `qwen3_5_vision`, mit transformers 5.15 neu verpackt), Muse-Glimmer-30B in BF16 (4,3 tok/s,
  ein Handschriftfall bis zu einer Stunde — gemessen wird die NVFP4-Fassung).
- **GPU-Anteil:** Vision-Zeilen mit dem Text-Profilwert 0,85 liefen in den Speicherwächter
  (Muse-Glimmer beim Laden bei 11 GB frei); die Vision-Zeilen setzen 0,70.

