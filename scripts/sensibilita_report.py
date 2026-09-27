#!/usr/bin/env python3
"""
sensibilita_report — verifica se le conclusioni della tesi reggono al variare
dei parametri arbitrari. Nessuna chiamata al modello.

Il punto non e' se la quota di Si' cambia: con una dispersione fra semi
dell'ordine di 16-18 punti, due esecuzioni per variante non possono rilevare
differenze di livello, e "nessuna differenza" sarebbe solo assenza di prova.
Il punto e' se cambiano le CONCLUSIONI, che sono effetti grandi e stabili.

I criteri sono fissati qui, prima di vedere i risultati. Modificarli dopo
averli visti annullerebbe il valore dell'analisi.

  C1  deriva verso il No       V finale < V iniziale
  C2  spoliticizzazione        scarto di Si' fra centrodestra e centrosinistra
                               al voto finale < SOGLIA_SCARTO punti
                               (88 all'inizio con gli schieramenti, 70-80 nella realta')

C3 e C4 (assenza delle ragioni politiche, No nel merito) si leggono
dall'output di motivazioni_chiuse.py, da lanciare su ciascuna run.

Uso, dalla radice del progetto:
  python scripts/sensibilita_report.py
  python scripts/sensibilita_report.py --rif runs/campagna_completa3
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sqlite3
from pathlib import Path

SOGLIA_SCARTO = 30.0

PART_NO = re.compile(r"Partito Democratico|Movimento 5 Stelle|Alleanza Verdi|AVS", re.I)
PART_SI = re.compile(r"Fratelli d'Italia|Forza Italia|Lega\b", re.I)


def leggi(db: Path) -> dict | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        def voti(label):
            return {r[0]: r[1] for r in con.execute(
                "SELECT agent_id, vote FROM vote WHERE label=? AND vote!='ERROR'", (label,))}
        b, f = voti("baseline"), voti("final")
        if not f:
            return None
        bio = {r[0]: r[1] or "" for r in con.execute(
            "SELECT agent_id, static_bio FROM agent WHERE is_voter=1 AND is_source=0")}
        meta = {r[0]: r[1] for r in con.execute("SELECT key, value FROM run_meta")}
        note = con.execute("SELECT COUNT(*) FROM note").fetchone()[0]
    finally:
        con.close()

    def V(v):
        si = sum(1 for x in v.values() if x == "SI"); no = sum(1 for x in v.values() if x == "NO")
        return 100 * si / (si + no) if si + no else float("nan")

    def quota_si(v, rx):
        g = [x for a, x in v.items() if rx.search(bio.get(a, ""))]
        return 100 * sum(1 for x in g if x == "SI") / len(g) if g else float("nan")

    aff = 100 * sum(1 for x in f.values() if x in ("SI", "NO")) / len(f)
    cfg = json.loads(meta.get("sim_config", "{}") or "{}")
    llm = json.loads(meta.get("llm", "{}") or "{}")
    return {
        "V0": V(b), "Vf": V(f), "aff": aff, "note": note,
        "cd": quota_si(f, PART_SI), "cs": quota_si(f, PART_NO),
        "rec": cfg.get("recommender", "?"), "oon": cfg.get("out_of_network", "?"),
        "temp": llm.get("temperature", {}),
    }


def nome_seme(d: Path, rif: Path) -> tuple[str, str]:
    if d.resolve() == rif.resolve():
        return "rif", "1"
    m = re.match(r"sens_(.+)_s(\d+)$", d.name)
    return (m.group(1), m.group(2)) if m else (d.name, "?")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rif", default="runs/campagna_completa3",
                    help="run di riferimento col seme 1 (hybrid, seme al modello)")
    a = ap.parse_args()
    rif = Path(a.rif)

    cartelle = [rif] + sorted(Path(p) for p in glob.glob("runs/sens_*"))
    righe = []
    for d in cartelle:
        db = d / "run.db"
        if not db.is_file():
            continue
        r = leggi(db)
        if r is None:
            print(f"  (in corso o incompleta: {d})")
            continue
        n, s = nome_seme(d, rif)
        r.update(nome=n, seme=s, gap=r["cd"] - r["cs"])
        r["C1"] = r["Vf"] < r["V0"]
        r["C2"] = r["gap"] < SOGLIA_SCARTO
        righe.append(r)

    if not righe:
        print("nessuna run conclusa trovata"); return

    print(f"\n{'variante':<16}{'seme':>5}{'V0':>7}{'Vfin':>7}{'affl.':>7}"
          f"{'CD Si':>7}{'CS Si':>7}{'scarto':>8}{'note':>6}   C1   C2")
    print("-" * 96)
    ordine = {n: i for i, n in enumerate(
        ["rif", "senza_notizie", "random", "recency", "fuori_rete_50", "riflessione_02",
         "riflessione_07", "azione_04", "azione_10", "engagement", "affinity"])}
    righe.sort(key=lambda r: (ordine.get(r["nome"], 99), r["seme"]))
    for r in righe:
        ok = lambda b: " si " if b else " NO "
        print(f"{r['nome']:<16}{r['seme']:>5}{r['V0']:>6.1f}%{r['Vf']:>6.1f}%{r['aff']:>6.0f}%"
              f"{r['cd']:>6.0f}%{r['cs']:>6.0f}%{r['gap']:>+8.0f}{r['note']:>6}  {ok(r['C1'])} {ok(r['C2'])}")

    print("\nESITO PER CONCLUSIONE")
    for c, desc in (("C1", "deriva verso il No"), ("C2", f"scarto partitico finale < {SOGLIA_SCARTO:.0f} punti")):
        falliti = [f"{r['nome']} s{r['seme']}" for r in righe if not r[c]]
        if falliti:
            print(f"  {c} {desc}: NON regge in {', '.join(falliti)}")
            print(f"     -> la conclusione e' condizionata a quel parametro: va dichiarata come tale")
        else:
            print(f"  {c} {desc}: regge in tutte le {len(righe)} esecuzioni")

    coppie = {}
    for r in righe:
        coppie.setdefault(r["nome"], {})[r["seme"]] = r["Vf"]
    diff = [abs(v["1"] - v["2"]) for v in coppie.values() if "1" in v and "2" in v]
    if diff:
        print(f"\nDispersione fra seme 1 e seme 2 della stessa variante: media {sum(diff)/len(diff):.1f} punti "
              f"su {len(diff)} varianti.")
        print("Differenze di V fra varianti inferiori a questa soglia non sono interpretabili.")
    print("\nC3 e C4: lanciare motivazioni_chiuse.py su ciascuna run e riportare, fra i contrari,")
    print("la quota che sceglie 'opposizione al Governo' (C3: < 10%) e 'contrario alla")
    print("separazione delle carriere' (C4: > 30%), accanto a quella dell'opzione fittizia.")


if __name__ == "__main__":
    main()
