#!/usr/bin/env python3
"""Gesamturteile vorhandener Berichte nach der aktuellen Regel neu berechnen.

Das Gesamturteil ist eine AUSWERTUNG der gespeicherten Einzelurteile, keine
eigene Messung. Aendert sich die Regel — wie am 2026-08-23, als aus "ein K.O.
irgendwo" eine gestufte Bewertung wurde —, muss deshalb kein einziges Modell
erneut laufen. Dieses Skript liest die Berichte, wendet dieselbe Logik an wie
reporter._model_summary und schreibt nur den summary-Block zurueck.

Was NICHT angefasst wird: die Einzelurteile, die Antworten, die Denkspuren, die
Playbook-Bloecke. Nur `summary` wird ersetzt, und das alte Urteil bleibt als
`overall_vorher` daneben stehen — ein Bericht, der seine eigene Vorgeschichte
verliert, laesst sich nicht mehr pruefen.

    python neubewerten.py --probe            # nur zeigen, nichts schreiben
    python neubewerten.py reports/<lauf>     # schreiben
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# .env vor dem Config-Import laden, sonst bleiben die ${...}-Platzhalter in
# testplan.yaml stehen und das Parsen scheitert — gleiche Reihenfolge wie im
# orchestrator.
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    import os
    for _zeile in _env.read_text(encoding="utf-8").splitlines():
        if _zeile.strip() and not _zeile.lstrip().startswith("#") and "=" in _zeile:
            _k, _, _v = _zeile.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from evaluators.base import EvalResult, PlaybookResult, Verdict  # noqa: E402
from lib.config import TestplanConfig  # noqa: E402
from reporter import gesamturteil  # noqa: E402

HIER = Path(__file__).resolve().parent
# Dieselbe Kohorte, die build_site.py und make_public_site.py auswerten.
KOHORTE = "2026-lokal-judge-claude-sonnet-5"
# Datum, unter dem ein ersetztes Urteil im Verlauf abgelegt wird.
STAND = __import__("datetime").date.today().isoformat()


def bewerten(d: dict, th) -> dict:
    """Gesamturteil eines gespeicherten Berichts nach der aktuellen Regel.

    Bis 2026-09-13 stand hier eine eigene Kopie der Regel aus
    reporter.gesamturteil. Sie war schon auseinandergelaufen — anderer Wortlaut
    der Gruende — und haette jede kuenftige Aenderung der Regel verpasst. Jetzt
    werden die Einzelurteile zu PlaybookResults zurueckgebaut und DIESELBE
    Funktion aufgerufen, die Bericht und Orchestrator benutzen.
    """
    pbs = []
    for name, pb in d.get("playbooks", {}).items():
        rs = [EvalResult(test_id=r.get("test_id", ""), model=r.get("model", ""),
                         evaluator=r.get("evaluator", ""), verdict=Verdict(r["verdict"]),
                         score=float(r.get("score") or 0.0), response=r.get("response", ""),
                         reasoning=r.get("reasoning", ""))
              for r in pb.get("results", [])]
        pbs.append(PlaybookResult(playbook=name, model=d.get("meta", {}).get("model", ""), results=rs))
    return gesamturteil(pbs, th)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verzeichnisse", nargs="*", type=Path,
                    help="Berichtsverzeichnisse; ohne Angabe nur die gepinnte Kohorte")
    ap.add_argument("--probe", action="store_true", help="nur anzeigen, nichts schreiben")
    a = ap.parse_args()

    th = TestplanConfig.load(HIER / "config" / "testplan.yaml").thresholds
    # Standard ist NUR die gepinnte Kohorte. Alte Laufverzeichnisse stammen aus
    # anderen Testdaten und teils von anderen Judges; ihre Urteile mit der
    # heutigen Regel zu ueberschreiben, waere kein Nachrechnen, sondern eine
    # Faelschung. Wer sie doch will, gibt sie ausdruecklich an.
    verz = a.verzeichnisse or [HIER / "reports" / KOHORTE]
    dateien = [j for v in verz for j in sorted(v.glob("*.json"))
               if "dashboard" not in j.name.lower()]

    geaendert = unveraendert = 0
    print(f"{'Bericht':44} {'vorher':>7} → {'nachher':<7} Grund")
    for j in dateien:
        try:
            d = json.loads(j.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "playbooks" not in d or "summary" not in d:
            continue
        s = d["summary"]
        alt = s.get("overall")
        neu = bewerten(d, th)
        # Auch bei gleichem Urteil neu schreiben, wenn sich die GRUENDE aendern:
        # ein Modell, das schon K.O. war und einen weiteren kritischen Fall
        # hinzubekommt, behielte sonst eine unvollstaendige Begruendung.
        if neu["overall"] == alt and neu["ko_gruende"] == s.get("ko_gruende"):
            unveraendert += 1
            continue
        grund = "; ".join(neu["ko_gruende"]) or "—"
        art = "Urteil" if neu["overall"] != alt else "Gruende"
        print(f"{j.parent.name + '/' + j.stem:44} {str(alt):>7} → {neu['overall']:<7} [{art}] {grund[:60]}")
        if not a.probe:
            # Die Vorgeschichte waechst, statt ueberschrieben zu werden:
            # overall_vorher haelt das allererste Urteil fest, urteilsverlauf
            # jeden weiteren Zwischenstand.
            neu["overall_vorher"] = s.get("overall_vorher", alt)
            neu["urteilsverlauf"] = s.get("urteilsverlauf", []) + [
                {"overall": alt, "ko_gruende": s.get("ko_gruende"), "ersetzt_am": STAND}]
            d["summary"] = neu
            j.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        geaendert += 1

    wort = "waeren zu aendern" if a.probe else "geaendert"
    print(f"\n{geaendert} {wort}, {unveraendert} unveraendert, {len(dateien)} geprueft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
