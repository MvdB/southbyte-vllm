#!/usr/bin/env python3
"""Offline-Regression fuer evaluators/vision.py — ohne Modell, ohne GPU.

Prueft Normalisierung, CER, die drei Fallarten und den Bildkanal (der Fake-Client
kontrolliert, dass ein image_url-Teil als data-URI ankommt).

Aufruf aus testplan/:  .venv/bin/python vision/test_bewertung.py
"""
from __future__ import annotations

import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluators.base import Verdict  # noqa: E402
from evaluators.vision import VisionEvaluator, ausgabe_zu_text, cer, normalisiert, zeichengetreu  # noqa: E402
from lib.testdata import Expected, TestCase  # noqa: E402


def mini_png(pfad: Path, breite: int = 56, hoehe: int = 28) -> None:
    """Ein graues PNG ohne Pillow (die Testplan-Umgebung hat keins)."""
    def block(art: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten))
    zeilen = b"".join(b"\x00" + b"\x80" * breite for _ in range(hoehe))
    pfad.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 0, 0, 0, 0))
                     + block(b"IDAT", zlib.compress(zeilen)) + block(b"IEND", b""))


class _Msg:
    def __init__(self, text):
        self.content, self.reasoning_content, self.reasoning = text, None, None


class _Wahl:
    def __init__(self, text):
        self.message, self.finish_reason = _Msg(text), "stop"


class _Comp:
    def __init__(self, text):
        self.choices, self.usage = [_Wahl(text)], type("U", (), {"completion_tokens": len(text) // 3})()


class FakeClient:
    """Antwortet je Fall mit einem festen Text und merkt sich, ob ein Bild ankam."""

    def __init__(self, antworten: dict[str, str]):
        self.antworten, self.bild_gesehen = antworten, []
        self.chat = type("C", (), {"completions": self})()
        self.models = type("M", (), {"list": staticmethod(lambda: type("L", (), {"data": []})())})()

    def create(self, *, model, messages, **kw):
        teile = messages[-1]["content"]
        text = next(t["text"] for t in teile if t["type"] == "text")
        url = next(t["image_url"]["url"] for t in teile if t["type"] == "image_url")
        self.bild_gesehen.append(url.startswith("data" + ":image/png;base64,"))
        return _Comp(self.antworten[text])


def check(name: str, ok: bool) -> bool:
    print(("OK    " if ok else "FEHLER") + " " + name)
    return ok


def main() -> int:
    allok = True
    # Normalisierung und CER
    allok &= check("normalisiert: ſ→s, u/v, i/j, Trennung, Leerraum, Nasalstrich",
                   normalisiert("Daſ iſt vñ ein Ver-\nſuch  \n jn") == normalisiert("Das ist un ein Versuch in")
                   and normalisiert("Grüße") == "Grüße")
    allok &= check("zeichengetreu: nur Raender und Zeilenenden", zeichengetreu(" a  b \r\nc\n\n") == "a b\nc")
    allok &= check("CER: gleich 0, ein Fehler 1/len, leer 1",
                   cer("abc", "abc") == 0 and abs(cer("abd", "abc") - 1 / 3) < 1e-9 and cer("", "abc") == 1.0)

    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "t.png"
        mini_png(png)
        wahr = "Daß iſt der\nerſte Verſuch"
        faelle = [
            ("vis-fraktur-901", "transkription", wahr, "druck", "Daß ist der\nerste Versuch", [], []),
            ("vis-kurrent-901", "transkription", wahr, "hand", "Was ganz anderes steht hier", [], []),
            ("vis-bild-901", "antwort", "12,5 %", "druck", "Der Anteil betraegt 12.5% im Jahr 2024.", ["12,5 Prozent"], []),
            ("vis-falle-901", "falle", "nicht im Bild", "druck", "Diese Angabe ist im Bild nicht zu sehen.", [], ["4711"]),
            ("vis-falle-902", "falle", "nicht im Bild", "druck", "Die Nummer lautet 4711.", [], ["4711"]),
        ]
        antworten, cases = {}, []
        for fid, art, w, schrift, antwort, alt, verboten in faelle:
            prompt = f"Aufgabe {fid}"
            antworten[prompt] = antwort
            cases.append(TestCase(id=fid, category="vision", subcategory=fid.split("-")[1], language="de",
                                  difficulty="medium", prompt=prompt,
                                  expected=Expected(type=art, value=w, alternatives=alt, forbidden=verboten),
                                  metadata={"bild": str(png), "schrift": schrift}))
        client = FakeClient(antworten)
        ev = VisionEvaluator(target_client=client, target_model="fake")
        ev._target_max_model_len = None  # kein /v1/models im Fake → kein Clamping
        res = {r.test_id: r for r in ev.evaluate_batch(cases)}

    allok &= check(f"Bildkanal: {len(client.bild_gesehen)} Anfragen, alle mit data-URI",
                   len(client.bild_gesehen) == 5 and all(client.bild_gesehen))
    r = res["vis-fraktur-901"]
    allok &= check(f"Fraktur: normalisiert 0 → PASS, zeichengetreu > 0 ({r.metadata.get('cer_zeichengetreu')})",
                   r.verdict == Verdict.PASS and r.metadata["cer_normalisiert"] == 0
                   and r.metadata["cer_zeichengetreu"] > 0)
    allok &= check("Kurrent: Unsinn → FAIL", res["vis-kurrent-901"].verdict == Verdict.FAIL)
    allok &= check("Bild: 12.5% gegen 12,5 % → PASS", res["vis-bild-901"].verdict == Verdict.PASS)
    allok &= check("Falle: 'nicht zu sehen' → PASS", res["vis-falle-901"].verdict == Verdict.PASS)
    allok &= check("Falle: erfundener Wert → KNOCKOUT", res["vis-falle-902"].verdict == Verdict.KNOCKOUT)
    # Ausgabeformate der OCR-Spezialisten
    allok &= check("ausgabe parse: Rahmen-/Klassenmarken weg, Zeilen bleiben",
                   ausgabe_zu_text("<x_0.1><y_0.2>Erste Zeile\nzweite **Zeile**<x_0.9><y_0.3><class_Text>",
                                   "parse") == "Erste Zeile\nzweite Zeile")
    allok &= check("ausgabe unlimited_ocr: ref auspacken, det weg",
                   ausgabe_zu_text("<|ref|>text<|/ref|><|det|>[[1, 2, 3, 4]]<|/det|>\nDaß iſt", "unlimited_ocr")
                   == "text\nDaß iſt")
    allok &= check("ausgabe unlimited_ocr: Byte-Level-Token (Ġ, Ċ, Ã¶) zurueck in Text",
                   ausgabe_zu_text("ĠDieĠKÃ¶nigsbergerĠPri-ĊvatbankĠÃŁ", "unlimited_ocr")
                   == "Die Königsberger Pri-\nvatbank ß")
    allok &= check("ausgabe unlimited_ocr: richtiger Text bleibt unangetastet",
                   ausgabe_zu_text("Die Königsberger Bank", "unlimited_ocr") == "Die Königsberger Bank")
    allok &= check("ausgabe doctags: Orte und Tags weg, je Element eine Zeile",
                   ausgabe_zu_text("<doctag><text><loc_10><loc_20><loc_30><loc_40>Erste</text>"
                                   "<text><loc_1><loc_2><loc_3><loc_4>Zweite</text></doctag>", "doctags")
                   == "Erste\nZweite")
    allok &= check("ausgabe text: unveraendert", ausgabe_zu_text("**a**\n# b", "text") == "**a**\n# b")

    # Fester Aufgabenprompt und Nachbearbeitung im Ablauf
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "t.png"
        mini_png(png)
        client = FakeClient({"</s><s><output_markdown>": "<x_0.1><y_0.1>Daß ist der\nerste Versuch<class_Text>"})
        ev = VisionEvaluator(target_client=client, target_model="fake", ausgabe="parse",
                             fester_prompt="</s><s><output_markdown>")
        ev._target_max_model_len = None
        tc = TestCase(id="vis-fraktur-902", category="vision", subcategory="T2_fraktur", language="de",
                      difficulty="medium", prompt="Transkribiere …",
                      expected=Expected(type="transkription", value="Daß iſt der\nerſte Verſuch"),
                      metadata={"bild": str(png), "schrift": "druck"})
        r = ev.evaluate(tc)
    allok &= check(f"fester Prompt + parse: PASS, gelesen ohne Marken, Rohantwort bleibt ({r.verdict.value})",
                   r.verdict == Verdict.PASS and r.metadata.get("gelesen") == "Daß ist der\nerste Versuch"
                   and "<x_0.1>" in r.response)

    # Nur bestimmte Fallarten (OCR-Spezialisten: nur Transkription)
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "t.png"
        mini_png(png)
        client = FakeClient({"X": "Daß ist der\nerste Versuch"})
        ev = VisionEvaluator(target_client=client, target_model="fake", fester_prompt="X", arten=["transkription"])
        ev._target_max_model_len = None
        mk = lambda fid, art: TestCase(id=fid, category="vision", subcategory="x", language="de",  # noqa: E731
                                       difficulty="medium", prompt="p",
                                       expected=Expected(type=art, value="Daß iſt der\nerſte Verſuch"),
                                       metadata={"bild": str(png), "schrift": "druck"})
        res = ev.evaluate_batch([mk("vis-fraktur-903", "transkription"), mk("vis-bild-903", "antwort"),
                                 mk("vis-falle-903", "falle")])
    allok &= check(f"arten=transkription: nur 1 von 3 Faellen bewertet ({[r.test_id for r in res]})",
                   [r.test_id for r in res] == ["vis-fraktur-903"] and len(client.bild_gesehen) == 1)

    print("ALLE TESTS OK" if allok else "TESTS FEHLGESCHLAGEN")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
