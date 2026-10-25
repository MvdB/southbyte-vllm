# Vision-Dimension — Plan

Stand: 2026-10-25. Entscheidungspapier: Es beschreibt, was gemessen wird,
woher die Bilder kommen, unter welchen Lizenzen, wie bewertet wird und was
Bau und Läufe kosten. Gebaut wird erst nach Freigabe, und zuerst als Vorstufe
(Abschnitt 8).

## 1 Was gemessen wird

Ob ein Modell **liest und versteht, was auf einem echten Bild steht** — in
Schriften und Sprachen, die in deutschen Archiven, Ämtern und Betrieben
vorkommen:

| Gruppe | Inhalt | Wahrheit |
|---|---|---|
| **T Transkription** | gedruckter und handschriftlicher Text in sechs Schriftlagen (Abschnitt 3) | vorhandene Transkription der Editoren |
| **V Bildverständnis** | Fragen zu Fotos, Diagrammen, Tabellen und Karten | kurze, prüfbare Antwort je Fall |
| **H Halluzinationsfallen** | Fragen nach etwas, das nicht im Bild steht | „steht nicht drin“ |

Nicht gemessen: Bildbeschreibung und Ästhetik (dafür gibt es öffentliche
Benchmarks), Video. Personendaten in Dokumenten (die frühere Gruppe D) sind
zurückgestellt: Echte Dokumente mit Personendaten lebender Menschen dürfen
nicht in einen öffentlichen Testsatz.

**Nur echte Bilder.** Keine selbst gesetzten oder künstlich verschlechterten
Dokumente: Echte Scans tragen echte Schwierigkeiten — Tinte, Durchschlag,
Stempel, Falz, Abkürzungen, gemischte Schriften —, und die Wahrheit stammt
von Editoren statt von uns.

## 2 Fallkatalog

Zielgröße **44 Fälle**:

| Gruppe | Fälle | Quelle (Abschnitt 3) |
|---|---:|---|
| T1 Modernes Deutsch, gedruckt (Schilder, Aushänge, Formulare, Fahrpläne) | 6 | Wikimedia Commons, amtliche Werke |
| T2 Fraktur, Zeitungen 1820–1939 | 5 | Reichsanzeiger-GT, Austrian Newspapers |
| T3 Kurrent, Akten 19. Jh. | 5 | Kurrent-GT (Zenodo 17252677) |
| T4 Frühneuhochdeutsch, Handschriften 15. Jh. | 5 | Formelbuch und Wasserschaden-GT (Zenodo 21257167, 21438740) |
| T5 Latein, Register 14./15. Jh. | 5 | e-NDP (Zenodo 7575693) |
| T6 Englisch, Druck und Handschrift | 4 | Library of Congress, US-Nationalarchiv |
| V Bildverständnis (Diagramm, Tabelle, Karte, Foto) | 8 | Destatis, DWD, Commons |
| H Halluzinationsfallen (über alle Gruppen) | 6 | Bilder aus T und V, Frage nach Fehlendem |

Ein Transkriptionsfall ist ein **Ausschnitt von 6 bis 15 Zeilen**, keine ganze
Seite: Die Ausgabe bleibt kurz, die Fehlerrate ist pro Fall belastbar, und
der Bildanteil am Kontext bleibt klein. Die Ausschnitte lassen sich aus den
Zeilenkoordinaten der Transkriptionen (PAGE-XML) schneiden, die
Wahrheit ist dann genau der Text dieser Zeilen.

## 3 Woher die Bilder kommen

Alle Lizenzen am 22.10.2026 an der Quelle geprüft, die Zenodo-Lizenzfelder
zusätzlich über die API.

| Quelle | Bilder | Transkription | Umfang |
|---|---|---|---|
| Formelbuch BayHStA, Zenodo 21257167 (07/2026) | CC BY 4.0 | CC BY 4.0, zeichengetreu (ſ, ꝛ, Nasalstrich) | 0,15 GB |
| Wasserschaden-GT, Zenodo 21438740 (07/2026) | CC BY 4.0 | CC BY 4.0, zeichengetreu | 0,13 GB |
| Kurrent 19. Jh., Zenodo 17252677 | CC BY 4.0 | CC BY 4.0, zeichengetreu | 7,8 GB |
| Reichsanzeiger-GT, UB Mannheim, Zenodo 10144428 | Public Domain Mark | CC BY 4.0, zeichengetreu | 0,03 GB, Bilder per Skript |
| Austrian Newspapers, Zenodo 3387369 | CC BY 4.0 | CC BY 4.0 | 0,18 GB |
| e-NDP, Zenodo 7575693 | CC BY 4.0 | CC BY 4.0, Abkürzungen aufgelöst | 0,91 GB |
| Library of Congress, By the People | je Sammlung, nur Public Domain | gemeinfrei | einzelne Seiten |
| US-Nationalarchiv, Citizen Archivist | US-Regierungswerk, gemeinfrei | gemeinfrei | einzelne Seiten |
| Wikimedia Commons | je Datei; nur CC0, Public Domain, CC BY | selbst erstellt | einzelne Dateien |
| Destatis | Verbreitung mit Quellennachweis gestattet | Textschicht des PDFs | einzelne Seiten |
| Deutscher Wetterdienst | CC BY 4.0 | selbst erstellt | einzelne Grafiken |

Gesamt rund 9 GB Download, alles Datensätze, keine Modelle.

**Ausgeschlossen, weil nicht-kommerziell oder nur für Forschung:** Bilder des
Deutschen Textarchivs, Transcribe Bentham, Parzival-Projekt, e-codices, IAM,
Old Bailey, der Teil „Digitale Schriftkunde“ in Zenodo 17252677, monasterium.net
(je Archiv unterschiedlich). Unsplash und Pexels verbieten die Nutzung für KI.

## 4 Urheberrecht und Veröffentlichung

- **CC BY 4.0** erlaubt Weitergabe und Bearbeitung, auch kommerziell, mit
  Namensnennung: Urheber, Titel, Quelle, Lizenz, und der Hinweis, dass ein
  Ausschnitt gezeigt wird. Das steht je Fall in `sources.jsonl` und auf der
  Ergebnisseite.
- **Gemeinfrei (Public Domain Mark, CC0, US-Regierungswerke)** braucht keine
  Nennung; die Quelle wird trotzdem angegeben.
- **CC BY-SA** wird nur genommen, wenn nichts anderes passt: Ein Ausschnitt ist
  eine Bearbeitung und stünde dann selbst unter CC BY-SA.
- **Destatis** erlaubt Verbreitung mit Quellennachweis, aber keine Bearbeitung
  ausdrücklich. Deshalb nur ganze, unveränderte Seiten.
- **Amtliche Werke** (§ 5 UrhG) sind als Text frei, Logos und Wappen nicht.
  Bilder mit Hoheitszeichen werden ausgelassen.
- **Personen:** Die historischen Akten betreffen Verstorbene; die DSGVO gilt
  für sie nicht. Bei Fotos von Commons werden keine Bilder mit erkennbaren
  Menschen genommen, um das Recht am eigenen Bild nicht zu berühren.
- **Veröffentlicht** werden die Ergebnisse, die Fälle mit Quelle und Lizenz und
  die Ausschnitte selbst — als eigener Teil des öffentlichen Datensatzes auf
  Hugging Face, Lizenzfeld je Datei. Ob die Ausschnitte mit hinaus oder nur
  die Quellverweise, entscheidet der Nutzer (Abschnitt 10).

## 5 Bewertung

Ohne Judge. Jede Wahrheit ist ein Text oder eine kurze Antwort, die sich
maschinell prüfen lässt:

- **Transkription:** Zeichenfehlerrate (CER) auf zwei Stufen.
  *Zeichengetreu* vergleicht Zeichen für Zeichen mit der Edition.
  *Normalisiert* gleicht vorher an: ſ → s, u/v und i/j, Ligaturen, Leerraum,
  Zeilenumbruch, bei Latein aufgelöste Abkürzungen. Bestanden ab einer
  normalisierten CER unter 10 % (Druck) bzw. 20 % (Handschrift); die Grenzen
  legt die Vorstufe fest.
- **Bildverständnis:** Antwort mit Normalisierung für Zahlen, Daten und
  Einheiten gegen die hinterlegte Wahrheit, wie bei den `exact`- und
  `contains`-Fällen des Testplans.
- **Halluzinationsfallen:** bestanden, wenn das Modell sagt, dass es das nicht
  sieht; durchgefallen, wenn es etwas nennt. Schon ein erfundener Wert ist
  ein K.O.-Kandidat, wie bei den Halluzinationsfällen im Qualitäts-Playbook.

**Auswendig Gelerntes:** Ein Modell könnte bekannte Texte aufsagen statt
lesen. Dagegen hilft zweierlei: Die frühneuhochdeutschen Datensätze stammen
vom Juli 2026 und liegen wahrscheinlich nach dem Trainingsstichtag. Und die
zeichengetreue Wahrheit weicht von jeder normalisierten Ausgabe ab; liegt
eine Antwort näher an der Normalform als am Bild, fällt das im Vergleich der
beiden Stufen auf. Bekannte Werke (Nibelungenlied, Walther, Gartenlaube)
kommen nicht in den Katalog.

## 6 Wie es im Testplan läuft

- **Eigene Dimension** auf der Ergebnisseite, kein siebtes Playbook in der
  LLM-Wertung: Keine der bestehenden Zahlen ändert sich.
- **Bildkanal im Harness:** `image_url` als data-URI. Profile mit
  `--chat-template-content-format string` brauchen für Bilder eine Variante
  mit `openai`, dazu `--limit-mm-per-prompt '{"image":1}'`. Das Clamping des
  Token-Budgets rechnet Bildtoken bisher nicht mit.
- **Modelle mit Bildeingang, lokal vorhanden** (sieben): Nemotron-3.5-Super-VL-120B,
  Ornith-1.5-122B, Muse-Glimmer-30B, Qwen3.8-27B-Uncensored,
  RadixArk/Qwen3.8-27B-NVFP4 (bisher ungetestet, braucht ein Profil), Gemma-4-E4B,
  Bolt-E4B (Vision-Encoder vorhanden, die Karte nennt aber nur Text). Alle
  liefen im LLM-Testplan bisher nur mit Text.
- **OCR-Spezialisten** als Bezugsgrößen für die Transkription (drei):
  Nemotron-3.5-Parse, baidu/Unlimited-OCR (MIT), ibm-granite/granite-docling-258M
  (Apache-2.0).
- **Nicht dabei: tencent/HunyuanOCR.** Seine Lizenz gilt ausdrücklich nicht in
  der EU („does not apply in the European Union“).
- **Denkmodus:** Werkseinstellung je Modell wie im Testplan; Budget wie dort.

## 7 Aufwand

| Posten | Arbeitszeit |
|---|---|
| Bildkanal, Profilvarianten, Budget mit Bildtoken | 0,5 Tage |
| Datensatz-Bau: Quellen holen, Ausschnitte aus PAGE-XML schneiden, Quellen- und Lizenzangaben je Fall | 1,5 Tage |
| Moderne Fälle (Commons, Destatis, DWD) aussuchen, Fragen und Antworten schreiben, gegenlesen | 1 Tag |
| Bewertung: CER auf zwei Stufen, Normalisierung je Schriftlage, Fallen | 0,5 Tage |
| Playbook, eigene Dimension auf beiden Seiten, Datensatzteil auf Hugging Face | 1 Tag |
| **Summe** | **4,5 Tage** |

Der größte Posten ist die Auswahl und Prüfung der Fälle, nicht der Code:
Jeder Ausschnitt wird angesehen, bevor er in den Katalog kommt.

## 8 Laufzeiten

| | Schätzung |
|---|---|
| Ein Modell ohne Denkmodus, 44 Fälle | 15–25 min plus Laden |
| Ein Modell mit Denkmodus (Super-VL, Ornith) | 60–90 min plus Laden |
| Alle zehn Zeilen | **5–8 h**, als Nachtlauf |

Grundlage: 20 Tokens/s, ~300 Ausgabetoken je Fall ohne und ~1500 mit
Denkmodus. Die Vorstufe misst das nach.

**Vorstufe zuerst:** 10 Fälle (je 2 aus T2–T5, dazu 2 aus V) gegen
Super-VL. Bau 0,5 Tage, Lauf 30 min. Sie beantwortet vor dem vollen Katalog:
Tragen Bildkanal und Profile? Was kostet ein Ausschnitt an Token? Trennt die
CER sauber, und wo liegen sinnvolle Grenzen?

## 9 Risiken

- **Schwer lesbare Handschrift** kann alle Modelle gleich scheitern lassen;
  dann misst der Fall nichts. Die Vorstufe zeigt, welche Schriftlagen
  trennen.
- **Bildtoken** sprengen bei großen Ausschnitten das Budget. Gegenmittel:
  kleinere Ausschnitte, feste Auflösung je Fall.
- **Lizenzangaben** müssen je Datei stimmen. Der Seitenbau bricht ab, wenn
  einem Fall Quelle oder Lizenz fehlt, wie bei der Bildseite.

## 10 Offene Entscheidungen

1. Umfang so (Transkription, Bildverständnis, Fallen; Personendaten später)?
2. Ausschnitte mit veröffentlichen (Datensatz auf Hugging Face) oder nur
   Quellverweise und Ergebnisse?
3. Modellauswahl wie in Abschnitt 6, inklusive der drei OCR-Spezialisten?
