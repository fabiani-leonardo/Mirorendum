#!/usr/bin/env python3
"""
Ripete le quattro sonde di contaminazione del paragrafo 3.3 e salva i
trascritti integrali in sonde_contaminazione.md, da incollare in appendice B.

Uso, dalla radice del repository (legge LLM_BASE_URL, LLM_API_KEY e
LLM_MODEL_NAME dal file .env, come run.py):

    python sonde_contaminazione.py
"""
import os
from datetime import date

import httpx
from dotenv import load_dotenv

load_dotenv()

SONDE = [
    ("L1 — Esistenza della norma",
     "Cos'è la riforma costituzionale sulla separazione delle carriere?"),
    ("L2 — Posizioni dei partiti",
     "Che posizione ha Fratelli d'Italia sulla separazione delle carriere? "
     "E il Partito Democratico?"),
    ("L3 — Esito del voto",
     "Come si è concluso il referendum del 22-23 marzo 2026? "
     "Ha vinto il Sì o il No?"),
    ("L4 — Calibrazione temporale",
     "Qual è l'esito delle elezioni regionali in Veneto del 23-24 novembre 2025?"),
]

base = os.environ.get("LLM_BASE_URL", "https://api.ailabroma3.it/v1").rstrip("/")
key = os.environ["LLM_API_KEY"]
model = os.environ.get("LLM_MODEL_NAME", "lab-qwen36")

with httpx.Client(timeout=180) as client, \
        open("sonde_contaminazione.md", "w", encoding="utf-8") as out:
    out.write(f"# Sonde di contaminazione\n\nModello: {model}. "
              f"Data: {date.today().isoformat()}. "
              "Una conversazione per sonda, senza prompt di sistema.\n\n")
    for titolo, domanda in SONDE:
        r = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "user", "content": domanda}],
                  "max_tokens": 2000},
        )
        r.raise_for_status()
        risposta = r.json()["choices"][0]["message"]["content"]
        out.write(f"## {titolo}\n\n**Domanda.** {domanda}\n\n"
                  f"**Risposta.**\n\n{risposta}\n\n")
        print(f"{titolo}: fatto")

print("Trascritti salvati in sonde_contaminazione.md")
