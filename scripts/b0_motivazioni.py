#!/usr/bin/env python3
"""
b0_motivazioni — interrogazione diretta del modello sulle ragioni del voto.

Completa per le motivazioni il disegno a tre livelli gia' usato per il voto:
  B0  il modello stima direttamente le ragioni dell'elettorato   (questo script)
  B1  la popolazione sintetica all'inizio, senza dinamica         (motivazioni_chiuse.py --iniziale)
  B2  la popolazione alla fine della campagna                     (motivazioni_chiuse.py)

Al modello si chiede, separatamente per chi vota SI e per chi vota NO, la
percentuale di elettori che indicherebbe ciascuna motivazione del questionario
reale, con piu' risposte possibili come nella rilevazione originale.

Due condizioni, come per la popolazione:
  letterale     solo il testo della scheda
  schieramenti  la scheda piu' chi ha proposto la legge e quali partiti la sostengono

Scelte di metodo:
  - l'ordine delle opzioni e' mescolato a ogni chiamata, e le opzioni sono
    numerate senza codici: elencarle nell'ordine del questionario reale,
    che e' per frequenza decrescente, suggerirebbe la classifica;
  - la data del voto e' omessa, come nelle altre sonde B0: indicandola, il
    modello riconosce di essere oltre il proprio limite di conoscenza;
  - le opzioni fittizie sono incluse come controllo: dicono quanta quota il
    modello attribuisce a una ragione che nella riforma non esiste.

Poiche' nella stima del voto il modello comprime le stime verso il centro,
oltre ai livelli conta l'ORDINE: la correlazione di Spearman fra le stime e le
quote reali dice se il modello mette in cima le stesse ragioni degli elettori.

Uso, dalla radice del progetto:
  export KEY=...
  python scripts/b0_motivazioni.py --testi testi_originali.json
  python scripts/b0_motivazioni.py --testi testi_originali.json --mostra-prompt
  python scripts/b0_motivazioni.py --testi testi_originali.json \\
      --url http://WORKSTATION:8000/v1/chat/completions --model NOME --out-prefix b0mot_llama405

Produce:
  <prefix>_raw.jsonl        ogni risposta grezza, con l'ordine delle opzioni mostrato
  <prefix>_riepilogo.json   medie, deviazioni, correlazioni per condizione e fronte
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b0_baseline import DEFAULT_MODEL, DEFAULT_URL, call_model, extract_json   # noqa: E402
from motivazioni_chiuse import OPZIONI, applica_testi                          # noqa: E402

SCHEDA = """In Italia si tiene un referendum costituzionale confermativo sul seguente quesito.

  «Approvate il testo della legge costituzionale concernente
  «Norme in materia di ordinamento giurisdizionale e di istituzione
  della Alta Corte disciplinare», approvato dal Parlamento e pubblicato
  nella Gazzetta Ufficiale?»

Votando SI si approva la legge, votando NO la si respinge."""

# Stesso testo di quesiti/ballot_schieramenti.txt: fatti, nessun argomento.
SCHIERAMENTI = ("La legge e' stata proposta dal Governo. Sostengono il SI Fratelli d'Italia, "
                "Lega e Forza Italia. Sostengono il NO Partito Democratico, Movimento 5 Stelle "
                "e Alleanza Verdi e Sinistra.")

DOMANDA = """{scheda}
{contesto}
Considera gli elettori che votano {voto}. Per ciascuna delle motivazioni seguenti, stima \
la percentuale di questi elettori che la indicherebbe come ragione del proprio voto. Ogni \
elettore puo' indicare piu' motivazioni, quindi le percentuali non devono sommare a 100.

{elenco}

Rispondi esclusivamente con un oggetto JSON, senza alcun testo prima o dopo, che associ a \
ciascun numero dell'elenco la percentuale stimata, da 0 a 100, nella forma:
{{"1": <numero>, "2": <numero>, ...}}"""

CONDIZIONI = {"letterale": "", "schieramenti": SCHIERAMENTI}


def prompt_per(condizione: str, voto: str, rep: int) -> tuple[str, list[str]]:
    """Prompt e ordine delle opzioni (lista di codici) per una chiamata."""
    opzioni = list(OPZIONI[voto])
    rng = random.Random(f"{condizione}|{voto}|{rep}")
    rng.shuffle(opzioni)
    elenco = "\n".join(f"{i}. {testo}" for i, (_, testo, _) in enumerate(opzioni, 1))
    contesto = f"\n{CONDIZIONI[condizione]}\n" if CONDIZIONI[condizione] else ""
    testo = DOMANDA.format(scheda=SCHEDA, contesto=contesto,
                           voto="SI" if voto == "SI" else "NO", elenco=elenco)
    return testo, [c for c, _, _ in opzioni]


def interpreta(obj, ordine: list[str]) -> dict[str, float] | None:
    """Da {"1": 40, ...} a {codice: 40.0}; None se manca qualcosa o e' fuori scala."""
    if not isinstance(obj, dict):
        return None
    stime = {}
    for i, codice in enumerate(ordine, 1):
        v = obj.get(str(i))
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        if not 0 <= v <= 100:
            return None
        stime[codice] = v
    return stime


def ranghi(valori: list[float]) -> list[float]:
    ordine = sorted(range(len(valori)), key=lambda i: valori[i])
    r = [0.0] * len(valori)
    i = 0
    while i < len(ordine):
        j = i
        while j + 1 < len(ordine) and valori[ordine[j + 1]] == valori[ordine[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordine[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = ranghi(x), ranghi(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def stampa(condizione: str, voto: str, stime: list[dict[str, float]], invalide: int) -> dict:
    print(f"\n{'=' * 78}\n {condizione.upper()}  —  chi vota {voto}: "
          f"{len(stime)} risposte valide, {invalide} non interpretabili\n{'=' * 78}")
    if not stime:
        return {}
    righe, reali, medie = [], [], []
    for codice, testo, reale in OPZIONI[voto]:
        valori = [s[codice] for s in stime]
        m = statistics.mean(valori)
        sd = statistics.stdev(valori) if len(valori) > 1 else 0.0
        righe.append((codice, testo, reale, m, sd))
        if reale is not None:
            reali.append(reale); medie.append(m)
    rango_stima = {c: r for (c, *_), r in zip(righe, ranghi([-x[3] for x in righe]))}
    print(f"  {'cod':<5}{'reale':>7}{'stima':>8}{'sd':>6}{'posto':>7}  motivazione")
    for codice, testo, reale, m, sd in sorted(righe, key=lambda x: -(x[2] if x[2] is not None else -1)):
        r = f"{reale}%" if reale is not None else "fittizia"
        print(f"  {codice:<5}{r:>7}{m:>7.0f}%{sd:>6.1f}{rango_stima[codice]:>7.0f}  {testo[:44]}")
    rho = spearman(medie, reali)
    mae = statistics.mean(abs(a - b) for a, b in zip(medie, reali))
    fittizia = next((m for c, _, r, m, _ in righe if r is None), None)
    print(f"\n  ordine rispetto al reale, Spearman: {rho:+.2f}" if rho is not None else "")
    print(f"  errore assoluto medio sulle quote reali: {mae:.1f} punti")
    if fittizia is not None:
        print(f"  quota attribuita all'opzione fittizia: {fittizia:.0f}%")
    return {"n_valide": len(stime), "n_invalide": invalide, "spearman": rho, "mae": mae,
            "fittizia": fittizia,
            "opzioni": {c: {"reale": r, "media": m, "sd": sd} for c, _, r, m, sd in righe}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=0.2,
                    help="come la chiamata di voto della simulazione")
    ap.add_argument("--max-tokens", type=int, default=640,
                    help="come la chiamata di voto della simulazione")
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--testi", help="file JSON con la formulazione originale (testi_originali.json)")
    ap.add_argument("--condizioni", nargs="+", default=list(CONDIZIONI), choices=list(CONDIZIONI))
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--rpm", type=int, default=38)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out-prefix", default="b0mot")
    ap.add_argument("--mostra-prompt", action="store_true",
                    help="stampa un prompt di esempio per condizione e fronte, senza chiamare il modello")
    args = ap.parse_args()

    if args.testi:
        print(f"formulazione da {args.testi}: {', '.join(applica_testi(args.testi))}")
    if args.mostra_prompt:
        for cond in args.condizioni:
            for voto in ("SI", "NO"):
                testo, ordine = prompt_per(cond, voto, 0)
                print(f"\n----- {cond} / {voto}  (ordine: {' '.join(ordine)}) -----\n{testo}")
        return

    key = os.environ.get("KEY")
    if not key:
        sys.exit("variabile KEY non impostata")

    lavori = [(c, v, r) for c in args.condizioni for v in ("SI", "NO") for r in range(args.reps)]
    print(f"{len(lavori)} chiamate a {args.model}, T={args.temperature}, "
          f"circa {len(lavori) / max(args.rpm, 1):.0f} minuti a {args.rpm} rpm")

    intervallo = 60.0 / max(args.rpm, 1)
    blocco, prossima = threading.Lock(), [time.monotonic()]

    def esegui(lavoro):
        cond, voto, rep = lavoro
        testo, ordine = prompt_per(cond, voto, rep)
        with blocco:
            attesa = prossima[0] - time.monotonic()
            prossima[0] = max(prossima[0], time.monotonic()) + intervallo
        if attesa > 0:
            time.sleep(attesa)
        try:
            out = call_model(args.url, key, args.model, testo, args.temperature,
                             args.max_tokens, args.thinking)
            stime = interpreta(extract_json(out["content"]), ordine)
            return {"condizione": cond, "voto": voto, "rep": rep, "ordine": ordine,
                    "risposta": out["content"], "finish_reason": out["finish_reason"],
                    "stime": stime}
        except Exception as e:                                   # noqa: BLE001
            return {"condizione": cond, "voto": voto, "rep": rep, "ordine": ordine,
                    "errore": str(e), "stime": None}

    risultati = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for i, fut in enumerate(as_completed([pool.submit(esegui, l) for l in lavori]), 1):
            risultati.append(fut.result())
            if i % 20 == 0 or i == len(lavori):
                print(f"  {i}/{len(lavori)}", flush=True)

    with open(f"{args.out_prefix}_raw.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(risultati, key=lambda r: (r["condizione"], r["voto"], r["rep"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    riepilogo = {"modello": args.model, "temperatura": args.temperature, "reps": args.reps,
                 "testi": args.testi, "condizioni": {}}
    for cond in args.condizioni:
        riepilogo["condizioni"][cond] = {}
        for voto in ("SI", "NO"):
            sel = [r for r in risultati if r["condizione"] == cond and r["voto"] == voto]
            valide = [r["stime"] for r in sel if r["stime"]]
            riepilogo["condizioni"][cond][voto] = stampa(cond, voto, valide, len(sel) - len(valide))
    with open(f"{args.out_prefix}_riepilogo.json", "w", encoding="utf-8") as f:
        json.dump(riepilogo, f, ensure_ascii=False, indent=2)
    print(f"\nscritti {args.out_prefix}_raw.jsonl e {args.out_prefix}_riepilogo.json")
    print("Lettura: conta l'ordine piu' dei livelli. Una correlazione alta dice che il modello")
    print("mette in cima le stesse ragioni degli elettori reali, anche se ne comprime le quote.")


if __name__ == "__main__":
    main()
