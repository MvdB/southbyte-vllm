#!/usr/bin/env python3
"""Qwen3Guard-Stream hinter einer OpenAI-Chat-Schnittstelle, fuer den Feldlauf.

Qwen3Guard-Stream ist kein generatives Modell und laeuft nicht ueber vLLM (die
Architektur Qwen3ForGuardModel fehlt dort, siehe probe_qwen3guard_stream.py).
Damit derselbe GuardEvaluator und derselbe Adapter wie fuer Qwen3Guard-Gen
greifen, antwortet dieser Server auf /v1/chat/completions mit demselben Text:

    Safety: Safe|Unsafe|Controversial
    Categories: <Kategorie>|None

Abbildung des Stroms auf ein Urteil je Nachricht:

  * Nutzeranfrage: der ganze Turn auf einmal, Urteil am Ende des Turns — wie in
    der Modellkarte und der Probe.
  * Assistenzantwort: erst der Nutzer-Turn als Zustand, dann die Antwort Token
    fuer Token; das Urteil ist die strengste Stufe, die dabei auftritt. Ein
    Streaming-Guard bricht beim ersten unsicheren Token ab, ein spaeteres Safe
    hebt das nicht auf.

Aufruf im Image spark-qwen3-tts:v1 (transformers 4.57.3, FastAPI):

    docker run -d --name vllm-qwen3guard-stream --gpus all -p 8000:8000 --entrypoint python3 \\
      -v ~/hf_models:/hf_models:ro -v "$PWD/testplan/guards":/guards:ro \\
      -e MODEL_DIR=/hf_models/Qwen--Qwen3Guard-Stream-4B \\
      spark-qwen3-tts:v1 /guards/qwen3guard_stream_server.py
"""
import os
import time

import torch
import transformers.utils.generic as _generic
import uvicorn
from fastapi import FastAPI
from transformers import AutoModel, AutoTokenizer

# Der mitgelieferte modeling_qwen3_guard.py dekoriert mit @check_model_inputs ohne
# Klammern (transformers 4.55). Seit 4.57 ist das eine Fabrik
# check_model_inputs(tie_last_hidden_states=True); ohne Anpassung scheitert jeder
# Aufruf mit "unexpected keyword argument 'input_ids'". Die Modelldateien bleiben
# unangetastet, sie kommen aus dem Collection-Sync.
_fabrik = _generic.check_model_inputs


def _beide_formen(arg=None, **kwargs):
    if callable(arg):
        return _fabrik()(arg)
    return _fabrik(**kwargs) if arg is None else _fabrik(arg, **kwargs)


_generic.check_model_inputs = _beide_formen

MODELL = os.environ.get("MODEL_DIR", "/hf_models/Qwen--Qwen3Guard-Stream-4B")
NAME = os.path.basename(MODELL.rstrip("/"))
RANG = {"Safe": 0, "Controversial": 1, "Unsafe": 2}

tok = AutoTokenizer.from_pretrained(MODELL, trust_remote_code=True)
mod = AutoModel.from_pretrained(MODELL, device_map="auto", torch_dtype=torch.bfloat16,
                                trust_remote_code=True).eval()
app = FastAPI()


def ende_nutzerturn(ids: list[int]) -> int:
    """Index des <|im_end|>, das den letzten Nutzer-Turn schliesst (wie in der Modellkarte)."""
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    user = tok.convert_tokens_to_ids("user")
    im_end = tok.convert_tokens_to_ids("<|im_end|>")
    start = next(i for i in range(len(ids) - 1, -1, -1) if ids[i:i + 2] == [im_start, user])
    return next(i for i in range(start + 2, len(ids)) if ids[i] == im_end)


@torch.inference_mode()
def urteil(nachrichten: list[dict]) -> tuple[str, str]:
    text = tok.apply_chat_template(nachrichten, tokenize=False, add_generation_prompt=False,
                                   enable_thinking=False)
    ids = tok(text, return_tensors="pt").input_ids[0]
    ende = ende_nutzerturn(ids.tolist())
    ergebnis, zustand = mod.stream_moderate_from_ids(ids[:ende + 1], role="user", stream_state=None)
    stufe, kategorie = ergebnis["risk_level"][-1], ergebnis["category"][-1]
    if not any(n["role"] == "assistant" for n in nachrichten):
        return stufe, kategorie
    stufe, kategorie = "Safe", None  # Antwort-Moderation: nur die Assistenzseite zaehlt
    for i in range(ende + 1, len(ids)):
        ergebnis, zustand = mod.stream_moderate_from_ids(ids[i], role="assistant", stream_state=zustand)
        s = ergebnis["risk_level"][-1]
        if RANG.get(s, 0) > RANG[stufe]:
            stufe, kategorie = s, ergebnis["category"][-1]
    return stufe, kategorie


@app.get("/v1/models")
def modelle() -> dict:
    return {"object": "list", "data": [{"id": NAME, "object": "model"}]}


@app.get("/health")
def gesund() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
def chat(anfrage: dict) -> dict:
    nachrichten = [{"role": n["role"], "content": n["content"] if isinstance(n["content"], str)
                    else " ".join(p.get("text", "") for p in n["content"])}
                   for n in anfrage.get("messages", []) if n.get("role") in ("user", "assistant")]
    stufe, kategorie = urteil(nachrichten)
    inhalt = f"Safety: {stufe}\nCategories: {kategorie if stufe != 'Safe' and kategorie else 'None'}"
    return {
        "id": f"guard-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()), "model": NAME,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": inhalt}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
