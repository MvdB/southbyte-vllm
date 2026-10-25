#!/usr/bin/env python3
"""Entscheidungsmodell (laya) hinter einer OpenAI-Chat-Schnittstelle, fuer den Feldlauf.

laya-multilingual ist kein Guard und kein generatives Modell: es beantwortet
typisierte Fragen ueber einen Zustand mit einer Wahrscheinlichkeit, in einem
Vorwaertsdurchlauf (das Muster von Jev). Damit derselbe GuardEvaluator greift,
nimmt dieser Server den Adapter `entscheidung` entgegen: Zustand und Fragen
stehen im Feld `entscheidung` des Anfragekoerpers (extra_body), die Antwort ist
das JSON der laya-Antworten, z. B. {"verstoss": {"type": "noul", "noul": 0.83}}.

Bewusst ohne die Ollaya-Laufzeit: die laedt Modelle selbst nach. Hier kommen die
Gewichte aus ~/hf_models (Collection-Sync), die Faelle verlassen die Maschine nicht.

Aufruf (Image aus guards/Dockerfile.laya):

    docker run -d --name vllm-laya --gpus all -p 127.0.0.1:8000:8000 \\
      -v ~/hf_models:/hf_models:ro -v "$PWD/testplan/guards":/guards:ro \\
      -e MODEL_DIR=/hf_models/convaiinnovations--laya-multilingual \\
      spark-laya:v1 /guards/laya_server.py
"""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

os.environ.setdefault("USE_TF", "0")  # laut Modellkarte: TF-Probe kann laya.load() blockieren

import laya  # noqa: E402
import torch  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402

MODELL = os.environ.get("MODEL_DIR", "/hf_models/convaiinnovations--laya-multilingual")
NAME = os.path.basename(MODELL.rstrip("/"))
GERAET = os.environ.get("LAYA_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")


def arbeitskopie(quelle: str) -> str:
    """Beschreibbare Sicht auf den Modellordner im Container.

    laya repariert beim Laden tokenizer/tokenizer_config.json im Modellordner selbst
    (extra_special_tokens als Liste, was transformers ab 4.5x nicht mehr liest). Der
    Ordner kommt aus dem Collection-Sync und ist schreibgeschuetzt eingehaengt; er
    bleibt unveraendert. Die Gewichte werden nur verlinkt, kopiert wird allein der
    kleine Tokenizer-Ordner.
    """
    ziel = Path(tempfile.mkdtemp(prefix="laya-"))
    for eintrag in Path(quelle).iterdir():
        if eintrag.name == "tokenizer":
            shutil.copytree(eintrag, ziel / eintrag.name)
        else:
            (ziel / eintrag.name).symlink_to(eintrag)
    return str(ziel)


agent = laya.load(arbeitskopie(MODELL), device=GERAET)
app = FastAPI()


@app.get("/v1/models")
def modelle() -> dict:
    return {"object": "list", "data": [{"id": NAME, "object": "model"}]}


@app.get("/health")
def gesund() -> dict:
    return {"status": "ok", "device": GERAET, "laya": laya.__version__}


@app.post("/v1/chat/completions")
def chat(anfrage: dict) -> dict:
    e = anfrage.get("entscheidung")
    if not isinstance(e, dict) or "zustand" not in e or "fragen" not in e:
        raise HTTPException(400, "Feld 'entscheidung' mit 'zustand' und 'fragen' fehlt")
    ergebnis = agent.predict(e["zustand"], e["fragen"])
    inhalt = json.dumps(ergebnis.get("answers", {}), ensure_ascii=False)
    return {
        "id": f"entscheidung-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()),
        "model": NAME,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": inhalt}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
