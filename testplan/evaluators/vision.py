"""Vision-Dimension: Lesen und Verstehen echter Bilder (docs/vision-dimension-plan.md).

Ohne Judge — jede Wahrheit ist maschinell pruefbar:

* **Transkription** (expected.type "transkription"): Zeichenfehlerrate (CER) auf
  zwei Stufen. *Zeichengetreu* vergleicht mit der Edition, nur Zeilenenden und
  Leerraum am Zeilenrand werden angeglichen. *Normalisiert* gleicht vorher an,
  was eine Edition anders schreibt als ein Leser: ſ → s, u/v und i/j,
  Ligaturen, diakritische Zeichen ausser dem Umlaut, Silbentrennung am
  Zeilenende, Leerraum und Zeilenumbruch. Bestanden, wenn die normalisierte CER
  unter der Grenze der Schriftlage liegt (Druck 10 %, Handschrift 20 %; die
  Vorstufe legt die endgueltigen Grenzen fest).
* **Bildverstaendnis** ("antwort"): die erwartete Antwort oder eine Alternative
  steht nach Normalisierung von Zahlen und Einheiten in der Antwort.
* **Halluzinationsfalle** ("falle"): bestanden, wenn das Modell sagt, dass es
  das nicht sieht, und keinen der verbotenen Werte nennt.

Laeuft nur auf ausdruecklichen Wunsch (--playbooks 09_vision) und landet in
einer eigenen Kohorte — keine Zahl der LLM-Wertung aendert sich.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from lib.testdata import TestCase

from .base import BaseEvaluator, EvalResult, Verdict

# Pfade in metadata.bild sind relativ zu testplan/.
_TESTPLAN = Path(__file__).resolve().parent.parent

# Bestehensgrenzen der normalisierten CER je Schriftlage (Plan, Abschnitt 5).
GRENZE = {"druck": 0.10, "hand": 0.20}

# Zeichen, die eine Edition setzt und ein Leser normalisiert. NFKC loest die
# Ligaturen (ﬁ, ﬂ, ﬀ …) bereits auf; hier stehen die, die NFKC nicht kennt.
_ERSATZ = str.maketrans({
    "ſ": "s", "ꝛ": "r", "ꝝ": "rum", "ꝰ": "us", "ꝯ": "con", "ꝫ": "et", "⁊": "et",
    "v": "u", "V": "U", "j": "i", "J": "I",
    "ÿ": "y", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "„": '"', "“": '"', "”": '"', "‚": "'", "‘": "'", "’": "'", "«": '"', "»": '"',
    "—": "-", "–": "-", "⸗": "-", "¬": "-",
})
# Beim Weglassen der Diakritika bleibt der Umlaut (U+0308): ä und a sind im
# Deutschen verschiedene Buchstaben, ein Nasalstrich ueber einem Vokal nicht.
_UMLAUT = "̈"


def zeichengetreu(text: str) -> str:
    """Nur Zeilenenden und Leerraum am Rand angleichen, sonst Zeichen fuer Zeichen."""
    zeilen = [re.sub(r"[ \t]+", " ", z).strip() for z in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(z for z in zeilen if z)


def normalisiert(text: str) -> str:
    """Lesart statt Editionsform: Sonderzeichen, Trennung, Leerraum angeglichen."""
    t = unicodedata.normalize("NFKC", text.replace("\r\n", "\n"))
    # Silbentrennung am Zeilenende zusammenziehen, bevor die Zeilen verschmelzen.
    t = re.sub(r"[-¬⸗=]\s*\n\s*", "", t)
    t = t.translate(_ERSATZ)
    zerlegt = unicodedata.normalize("NFD", t)
    zerlegt = "".join(c for c in zerlegt if not unicodedata.combining(c) or c == _UMLAUT)
    t = unicodedata.normalize("NFC", zerlegt)
    return re.sub(r"\s+", " ", t).strip()


def levenshtein(a: str, b: str) -> int:
    """Editierdistanz (Einfuegen, Loeschen, Ersetzen je 1); O(len(a)·len(b))."""
    if len(a) < len(b):
        a, b = b, a
    vorher = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        jetzt = [i]
        for j, cb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (ca != cb)))
        vorher = jetzt
    return vorher[-1]


def cer(antwort: str, wahrheit: str) -> float:
    """Zeichenfehlerrate gegen die Wahrheit; mehr als 1,0 ist moeglich (Geschwaetz)."""
    if not wahrheit:
        return 0.0 if not antwort else 1.0
    return levenshtein(antwort, wahrheit) / len(wahrheit)


def _antwort_norm(text: str) -> str:
    """Fuer Bildverstaendnis: klein, Dezimalkomma, Tausenderpunkte, Einheiten ohne Leerraum."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", t)        # 1.234 → 1234
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)              # 3,5 → 3.5
    t = re.sub(r"(?<=\d)\s+(?=[%°a-zäöüµ])", "", t)    # 12 % → 12%, 5 kg → 5kg
    return re.sub(r"\s+", " ", t).strip()


_NICHT_DA = re.compile(
    r"nicht\s+(?:zu\s+)?(?:sehen|erkennbar|ersichtlich|vorhanden|enthalten|abgebildet|angegeben|"
    r"lesbar|dargestellt|sichtbar)|steht\s+nicht|kein(?:e|en)?\s+\w*\s*(?:angabe|hinweis)|"
    r"nicht\s+im\s+bild|lässt\s+sich\s+nicht|kann\s+(?:ich\s+)?(?:das|dies|es)?\s*nicht\s+(?:erkennen|sehen|ablesen)",
    re.I)


# Ausgabeformate der OCR-Spezialisten (Testplan-Feld vision_ausgabe). Die Modelle
# liefern Markierungen um den gelesenen Text; bewertet wird nur der Text.
_PARSE_MARKEN = re.compile(r"<x_[\d.]+><y_[\d.]+>|<class_[A-Za-z_-]+>")       # Nemotron-3.5-Parse
_REF = re.compile(r"<\|ref\|>(.*?)<\|/ref\|>", re.S)                         # Unlimited-OCR
_DET = re.compile(r"<\|det\|>.*?<\|/det\|>", re.S)
_DOCTAGS_ORT = re.compile(r"<loc_\d+>")                                          # granite-docling
_DOCTAGS_ZEILE = re.compile(r"</(?:text|title|section_header_level_\d|caption|footnote|"
                            r"page_header|page_footer|list_item|paragraph|formula|code)>")
_TAG = re.compile(r"</?[a-zA-Z_][\w-]*(?:\s[^<>]*)?>")
_MD_KOPF = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
_MD_BETONT = re.compile(r"(\*\*|__|\*|`)(.+?)\1", re.S)
_SPEZIAL = re.compile(r"<\|[^|<>]*\|>|</?s>|<pad>|<image>")


def _byte_level_zurueck(text: str) -> str:
    """Byte-Level-BPE-Zeichen (Ġ = Leerzeichen, Ċ = Zeilenumbruch, Ã¶ = ö …) in Text.

    Fuer Unlimited-OCR im Rezept-Image: transformers 5.12 baut aus
    tokenizer_class LlamaTokenizerFast einen Tokenizer ohne den ByteLevel-Decoder
    der tokenizer.json, vLLM gibt die Token deshalb roh aus (25.10.2026). Die
    Umkehr ist die feste GPT-2-Bytetabelle; nichts geht verloren.
    """
    zeichen = list(range(ord("!"), ord("~") + 1)) + list(range(0xA1, 0xAD)) + list(range(0xAE, 0x100))
    bytes_ = zeichen[:]
    n = 0
    for b in range(256):
        if b not in zeichen:
            zeichen.append(b)
            bytes_.append(256 + n)
            n += 1
    rueck = {chr(c): b for b, c in zip(zeichen, bytes_)}
    roh = bytearray()
    for ch in text:
        if ch in rueck:
            roh.append(rueck[ch])
        else:
            roh.extend(ch.encode("utf-8"))
    return roh.decode("utf-8", errors="replace")


def ausgabe_zu_text(text: str, form: str = "text") -> str:
    """Ausgabe eines Modells auf den gelesenen Text zurueckfuehren.

    form:
      text           unveraendert (VL-Modelle mit freier Antwort)
      markdown       Ueberschriften-Rauten und Betonungen weg, Zeilen bleiben
      parse          Nemotron-3.5-Parse: Rahmen- und Klassenmarken weg, dann wie markdown
      unlimited_ocr  Unlimited-OCR: roh ausgegebene Byte-Level-Token zurueck in Text,
                     <|ref|>…<|/ref|> auspacken, <|det|>-Koordinaten weg
      doctags        granite-docling: <loc_N> weg, je Element eine Zeile, Tags weg
    Das ist Nachbearbeitung der Form, nicht des Inhalts: Zeichen innerhalb des
    gelesenen Textes bleiben, wie das Modell sie geschrieben hat.
    """
    if form in ("", "text", None):
        return text
    t = text
    if form == "parse":
        t = _PARSE_MARKEN.sub("\n", t)
    elif form == "unlimited_ocr":
        if "Ġ" in t or "Ċ" in t:  # roh ausgegebene Byte-Level-Token (siehe _byte_level_zurueck)
            t = _byte_level_zurueck(t)
        t = _DET.sub("", _REF.sub(r"\1", t))
    elif form == "doctags":
        t = _DOCTAGS_ZEILE.sub("\n", _DOCTAGS_ORT.sub("", t))
        t = _TAG.sub("", t)
    elif form != "markdown":
        raise ValueError(f"unbekanntes Ausgabeformat '{form}' (text|markdown|parse|unlimited_ocr|doctags)")
    t = _SPEZIAL.sub("", t)
    t = _MD_BETONT.sub(r"\2", _MD_KOPF.sub("", t))
    zeilen = [z.strip() for z in t.replace("\r\n", "\n").split("\n")]
    return "\n".join(z for z in zeilen if z)


class VisionEvaluator(BaseEvaluator):
    """Transkription, Bildverstaendnis und Fallen gegen maschinell pruefbare Wahrheiten."""

    name = "vision"

    def __init__(self, *args, ausgabe: str = "text", fester_prompt: str = "",
                 arten: list[str] | tuple[str, ...] = (), **kwargs):
        """ausgabe: Format der Modellantwort (ausgabe_zu_text); fester_prompt: Aufgabe,
        die OCR-Spezialisten statt des deutschen Fall-Prompts brauchen (Kontrolltoken
        bei Nemotron-3.5-Parse, "<image>document parsing." bei Unlimited-OCR); arten:
        nur diese Fallarten (OCR-Spezialisten: nur "transkription" — Bildfragen und
        Fallen koennen sie mit festem Aufgabenprompt gar nicht beantworten). Alles
        kommt aus der Testplan-Zeile (vision_ausgabe, vision_prompt, vision_arten)."""
        super().__init__(*args, **kwargs)
        self.ausgabe = ausgabe or "text"
        self.fester_prompt = fester_prompt or ""
        self.arten = tuple(arten or ())

    def evaluate_batch(self, test_cases: list[TestCase]) -> list[EvalResult]:
        """Wie die Basis, aber nur die Fallarten der Zeile (leer = alle)."""
        if self.arten:
            test_cases = [tc for tc in test_cases
                          if (tc.expected.type if tc.expected else "transkription") in self.arten]
        return super().evaluate_batch(test_cases)

    def evaluate(self, test_case: TestCase) -> EvalResult:
        meta = test_case.metadata or {}
        bild = _TESTPLAN / meta["bild"]
        if not bild.is_file():
            raise FileNotFoundError(f"Bild fehlt: {bild} (vision/bauen.py baut es aus den Quellen)")
        art = test_case.expected.type if test_case.expected else "transkription"
        response, thinking, latency_ms, tokens, _ = self.query_target(
            prompt=self.fester_prompt or self._model_prompt(test_case),
            system_prompt=test_case.system_prompt,
            max_tokens=test_case.max_tokens or 32768,
            bild=str(bild),
        )
        basis = dict(test_id=test_case.id, model=self.target_model,
                     evaluator=f"vision.{test_case.subcategory or art}", response=response,
                     latency_ms=latency_ms, tokens_generated=tokens, thinking=thinking)
        if not response:
            grund = ("Degenerierte Antwort: Budget ausgeschoepft ohne Content"
                     if self.last_response_degenerate else "Leere Antwort")
            return EvalResult(verdict=Verdict.FAIL, score=0.0, reasoning=grund,
                              response_type="degenerate" if self.last_response_degenerate else "empty",
                              metadata={"art": art}, **basis)

        wahr = test_case.expected.value
        roh = response
        response = ausgabe_zu_text(roh, self.ausgabe)  # bewertet wird der gelesene Text
        if art == "transkription":
            cer_z = cer(zeichengetreu(response), zeichengetreu(wahr))
            cer_n = cer(normalisiert(response), normalisiert(wahr))
            schrift = meta.get("schrift", "druck")
            grenze = GRENZE.get(schrift, GRENZE["druck"])
            ok = cer_n < grenze
            return EvalResult(
                verdict=Verdict.PASS if ok else Verdict.FAIL, score=max(0.0, 1.0 - cer_n),
                reasoning=(f"CER normalisiert {cer_n:.3f} ({'unter' if ok else 'ueber'} {grenze:.2f}, "
                           f"{schrift}), zeichengetreu {cer_z:.3f}"),
                metadata={"art": art, "cer_normalisiert": round(cer_n, 4), "cer_zeichengetreu": round(cer_z, 4),
                          "grenze": grenze, "schrift": schrift, "zeilen": meta.get("zeilen"),
                          "normalisierung": meta.get("normalisierung"), "ausgabe": self.ausgabe,
                          **({"gelesen": response} if self.ausgabe != "text" else {})},
                **basis)

        if art == "antwort":
            norm = _antwort_norm(response)
            treffer = [w for w in [wahr, *test_case.expected.alternatives] if _antwort_norm(w) in norm]
            return EvalResult(
                verdict=Verdict.PASS if treffer else Verdict.FAIL, score=1.0 if treffer else 0.0,
                reasoning=(f"Erwartet '{wahr}' gefunden" if treffer else f"Erwartet '{wahr}' nicht in der Antwort"),
                metadata={"art": art}, **basis)

        if art == "falle":
            erfunden = [f for f in test_case.expected.forbidden if _antwort_norm(f) in _antwort_norm(response)]
            verneint = bool(_NICHT_DA.search(response))
            ok = verneint and not erfunden
            # Ein erfundener Wert ist ein K.O.-Kandidat wie die Halluzinationsfaelle im Qualitaets-Playbook.
            verdict = Verdict.PASS if ok else (Verdict.KNOCKOUT if erfunden else Verdict.FAIL)
            return EvalResult(
                verdict=verdict, score=1.0 if ok else 0.0,
                reasoning=("Fehlendes erkannt" if ok else
                           f"Erfunden: {', '.join(erfunden)}" if erfunden else "Nicht als fehlend benannt"),
                metadata={"art": art, "erfunden": erfunden}, **basis)

        raise ValueError(f"{test_case.id}: unbekannte Art '{art}' (transkription|antwort|falle)")
