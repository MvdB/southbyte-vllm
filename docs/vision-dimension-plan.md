# Vision-Dimension — Plan, noch nichts gebaut

Stand: 2026-10-16. Dies ist ein **Entscheidungspapier**, kein Bauauftrag. Es
beantwortet die Frage, ob und wie eine Vision-Prüfung in diese Werkstatt passt,
damit danach entschieden werden kann, ob gebaut wird.

## 1 Warum nicht einfach loslegen

Der Harness kann heute keine Bilder — null Treffer auf `image_url`, `base64`
oder `data:image` in `evaluators/` und `lib/`. Das ist aber nicht das Problem;
das ist ein Tag Arbeit.

Das Problem ist die Messgröße. Die bestehenden Dimensionen tragen, weil jede
eine **Betriebsentscheidung** abbildet: Hält das Modell einen Jailbreak aus,
schreibt es brauchbares Deutsch, erfindet es Fakten. Bei Vision ist die
naheliegende Übung „beschreibe dieses Bild" — messbar, aber niemand trifft
danach eine Entscheidung.

Dazu ein Aufwandsargument: Die Playbooks sind klein und handverlesen
(german_language 4 Fälle, bias 9, security 12). Sie funktionieren, weil jeder
Fall mit Bedacht gewählt ist. Ein Bildfall kostet zusätzlich ein Bild **und**
eine belastbare Wahrheit — und schlechte Fälle fallen bei Bildern weniger auf
als bei Text.

## 2 Der Use-Case: deutsches Dokumentverständnis

Nicht Bildbeschreibung, sondern das, was ein Mittelständler oder eine Behörde
tatsächlich mit so einem Modell täte: **Rechnung, Formular, Aktenvermerk,
Anschreiben lesen und Felder herausziehen.**

Drei Gründe:

1. **Objektiv prüfbar.** Die Wahrheit ist ein Feldwert, keine Formulierung.
   „Steht da 1.247,50 €" lässt sich messen, „ist die Beschreibung gut" nicht.
2. **Deutsch ist der Unterschied.** Die Kohorte misst deutsche Sprachqualität,
   weil das anderswo fehlt. Dasselbe gilt für deutsche Dokumente: Umlaute in
   Scans, Behördensprache, DIN-Datumsformate, Beträge mit Komma.
3. **Es trifft die Governance-Frage.** Ein Modell, das Dokumente mit
   Personendaten liest, ist genau der Fall, für den EU-KI-Verordnung und
   ISO 42001 Antworten verlangen. Eine Vision-Dimension, die **PII in
   Dokumenten** mitprüft, misst etwas, das sonst niemand misst.

### Was ausdrücklich NICHT gemessen wird

Allgemeine Bildbeschreibung, Ästhetik, Objekterkennung in Alltagsfotos,
Videoverständnis. Nicht weil es uninteressant wäre, sondern weil dafür gute
öffentliche Benchmarks existieren und wir dort nichts beitragen.

## 3 Fallkatalog

Zielgröße **24 Fälle** in vier Gruppen. Die Zahl ist an den vorhandenen
Playbooks orientiert: groß genug für eine Quote, klein genug für Handarbeit.

| Gruppe | Fälle | Was geprüft wird | Wahrheit |
|---|---|---|---|
| **A Feldextraktion** | 10 | Rechnungsnummer, Betrag, Datum, Lieferant, IBAN aus Rechnungen und Formularen | Feldwerte je Fall, exakter Abgleich |
| **B Tabelle und Diagramm** | 6 | Werte ablesen, Reihen vergleichen, Summen prüfen | Zahlenwerte, Toleranz 0 |
| **C Halluzinationsfallen** | 4 | Nach etwas fragen, das NICHT im Bild ist | korrekte Antwort ist „steht nicht drin" |
| **D PII-Erkennung** | 4 | Welche Personendaten enthält dieses Dokument? | Liste der erwarteten Kategorien |

Gruppe C ist die wichtigste und wird gern vergessen. Ein Modell, das brav
jeden Feldwert findet, aber auf „Wie hoch ist der Skonto-Satz?" bei einer
Rechnung ohne Skonto eine Zahl erfindet, ist für den Einsatzzweck unbrauchbar.
Dieselbe Logik wie bei den Halluzinationsfällen im Quality-Playbook.

Gruppe D knüpft an die vorhandenen `pii`-Fälle an und nutzt deren Kriterien
(seit 13.09.: Befund-Judge, K.O. nur bei genannten Personendaten mit Zitat).

## 4 Woher die Dokumente kommen

**Nicht aus echten Beständen.** Mandantenunterlagen scheiden aus
Vertraulichkeitsgründen aus, und Normen und Arbeitgeberdokumente aus
lizenzrechtlichen.

Stattdessen **synthetisch, aber realistisch**: selbst gesetzte Rechnungen,
Formulare und Vermerke mit erfundenen, in sich konsistenten Daten. Erzeugung
über die vorhandene HTML-nach-PDF-Kette (wie die EMF-Vorlagen), dann gerendert
und teils bewusst verschlechtert — Scanschräge, Rauschen, Knick, schwache
Tinte. Das bildet die Wirklichkeit besser ab als ein sauberer Export.

Das löst zugleich die PII-Frage sauber: Die Personendaten in Gruppe D sind
erfunden, also kann die Prüfung selbst keine echten Daten durchreichen.

**Nicht mit unseren Bildmodellen erzeugen.** Qwen-Image-2.1-Turbo rendert
deutschen Text mit CER 0,000 — ein VL-Modell gegen die Stärke eines
Bildmodells zu prüfen, misst das falsche Paar. Allenfalls als kleine
Kontrollgruppe, ausdrücklich gekennzeichnet.

## 5 Wie bewertet wird

Der Judge **sieht das Bild nicht**. Zwei Wege:

**Weg A — hinterlegte Wahrheit, kein Judge.** Je Fall stehen die erwarteten
Feldwerte im Testfall, verglichen wird per Textabgleich mit Normalisierung
(Beträge, Datumsformate, Leerzeichen). Objektiv, billig, reproduzierbar — und
auf Extraktion beschränkt.

**Weg B — Judge mit Bildfähigkeit.** Erlaubt freiere Fragen, bringt aber eine
neue Abhängigkeit in die Kette und die Frage, wer den Judge prüft.

**Empfehlung: Weg A für die Gruppen A, B und C, Weg B erst wenn A trägt.**
Gruppe D nutzt den vorhandenen PII-Befund-Judge auf der Textantwort — der
braucht das Bild nicht, nur die Ausgabe des Modells.

Das folgt dem Vorbild der Guards: Playbook 08 kommt ganz ohne Judge aus, weil
das Guard-Modell selbst der Klassifikator ist und gegen gelabelte Daten
gemessen wird. Dieselbe Logik hier.

## 6 Wo die Zahl landet

**Als eigene, fünfte Dimension — nicht als siebtes Playbook.**

Die Ergebnisseite führt heute vier getrennte Dimensionen (`llm: 65, guard: 6,
image: 8, tts: 22`). Eine Vision-Quote, die in die LLM-Pass-Rate einflösse,
würde jede der 65 bestehenden Zahlen unvergleichbar machen und einen Re-Run
der ganzen Kohorte erzwingen.

Als eigene Dimension ändert sich **keine einzige bestehende Zahl**. Die fünf
VL-Modelle der Kohorte bekommen einen zweiten Eintrag, wann immer wir dazu
kommen; die übrigen 60 bleiben unberührt.

## 7 Technische Punkte, die beim Bau beißen werden

- **`--chat-template-content-format string`** steht in mehreren Profilen,
  unter anderem bei Super-VL. Genau dieser Wert verhindert Inhaltslisten und
  damit Bildanhänge. Für VL-Läufe muss er weg — und das heißt: ein VL-Lauf
  fährt ein anderes Profil als der Textlauf desselben Modells.
- **Bildgrößen und Kachelung** gehen ins Token-Budget. Ein A4-Scan in hoher
  Auflösung kann mehrere tausend Token kosten, bevor die Frage überhaupt
  anfängt. Das Clamping in `_clamp_max_tokens` rechnet heute nur Zeichen,
  nicht Bildtoken — es würde das Budget zu optimistisch schätzen.
- **Degeneration im Denkmodus.** Am 16.10. an Lightning gemessen: mit Denken
  läuft es ins Limit ohne Inhalt, ohne Denken löst es dieselbe Aufgabe in 17 s.
  Bei Bildern mit viel Kontext ist das wahrscheinlicher, nicht unwahrscheinlicher.
- **Nicht jedes VL-Modell nimmt dasselbe Format.** data-URI, URL, mehrere
  Bilder je Anfrage — das gehört vor dem Fallkatalog je Modell geprobt, wie
  die `probe_*.py` bei den Guards.

## 8 Aufwand

| Posten | Schätzung |
|---|---|
| Bildkanal im Harness, Profilvariante, Clamping | 1 Tag |
| Dokumente setzen und verschlechtern (24 Stück) | 1 bis 2 Tage |
| Wahrheiten je Fall festlegen und gegenlesen | 1 Tag |
| Playbook, K.O.-Kriterien, eigene Dimension auf der Seite | 1 Tag |
| **Summe Bau** | **4 bis 5 Tage** |
| Lauf je Modell (24 Fälle) | 30 bis 50 min |
| Lauf über alle fünf VL-Modelle | 2,5 bis 4 h |

Der Löwenanteil sind die Testdaten, nicht der Code. Das ist das übliche
Verhältnis bei dieser Art Arbeit und der Grund, warum der Plan vor dem Bau
steht.

## 9 Vorschlag für den Einstieg

Nicht alles auf einmal. **Eine Vorstufe mit 8 Fällen aus Gruppe A**, gegen das
eine Modell, das gerade gemessen wurde (Nemotron-3.5-Super-VL-120B). Halber Tag
Bau, eine Stunde Lauf.

Sie beantwortet drei Fragen, bevor 24 Fälle kuratiert werden:

1. Trägt der Bildkanal über die vLLM-API, mit diesem Modell, auf dieser Box?
2. Reicht die hinterlegte Wahrheit als Bewertung, oder braucht es doch einen
   Judge mit Bildfähigkeit?
3. Wie teuer ist ein A4-Scan wirklich in Token?

Fällt eine davon anders aus als erwartet, ist der Plan billig korrigiert. Fällt
keine anders aus, ist das Erweitern reine Kuratierarbeit ohne weiteren Bau.

## 10 Was noch offen ist

- **Mehrseitige Dokumente** — vertagt. Ein Scan je Fall reicht für den Anfang;
  Seitenbezug ist eine eigene Schwierigkeit.
- **Video** — ausdrücklich draußen. Super-VL kann es, aber ein belastbarer
  Videotest ist eine eigene Dimension und kein Anhängsel.
- **Handschrift** — reizvoll, aber die Wahrheit ist schwerer festzulegen und
  die Streuung zwischen Modellen groß. Kandidat für eine zweite Ausbaustufe.
