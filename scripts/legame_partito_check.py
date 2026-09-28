#!/usr/bin/env python3
"""
legame_partito_check — esperimento naturale sulle esecuzioni gia' condotte.

Nel grafo iniziale, per un difetto del parser dei nomi, seguono il proprio
partito solo gli elettori di PD, Forza Italia e AVS; quelli di Fratelli
d'Italia, Lega e M5S no. Le run gia' fatte contengono quindi un confronto
gratuito: a parita' di schieramento, chi riceve i messaggi del proprio
partito dalla propria rete vota diversamente da chi non li riceve?

Il confronto piu' informativo e' dentro il centrodestra: Forza Italia
(legata) contro Fratelli d'Italia e Lega (non legate). Se il legame conta,
gli elettori di FI terminano con una quota di Si' superiore.

Nessuna chiamata al modello.

Uso, dalla radice del progetto:
  python scripts/legame_partito_check.py
  python scripts/legame_partito_check.py runs/sens_*/run.db runs/campagna_completa3/run.db
"""

import glob
import re
import sqlite3
import sys
from collections import defaultdict

PARTITI = [
    ("FdI", r"vota Fratelli d'Italia", False, "Si"),
    ("Lega", r"vota Lega\b", False, "Si"),
    ("FI", r"vota Forza Italia", True, "Si"),
    ("PD", r"vota Partito Democratico", True, "No"),
    ("AVS", r"vota Alleanza Verdi", True, "No"),
    ("M5S", r"vota Movimento 5 Stelle", False, "No"),
]


def partito_di(bio):
    for nome, rx, _, _ in PARTITI:
        if re.search(rx, bio or ""):
            return nome
    return None


def main():
    dbs = sys.argv[1:] or sorted(glob.glob("runs/sens_*/run.db")) + ["runs/campagna_completa3/run.db"]
    tot = defaultdict(lambda: {"SI": 0, "NO": 0, "ASTENUTO": 0})
    usate = 0
    for db in dbs:
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            righe = con.execute(
                "SELECT a.static_bio, v.vote FROM vote v JOIN agent a ON a.agent_id = v.agent_id "
                "WHERE v.label = 'final' AND v.vote != 'ERROR'").fetchall()
            con.close()
        except sqlite3.Error:
            continue
        if not righe:
            continue
        usate += 1
        for bio, voto in righe:
            p = partito_di(bio)
            if p:
                tot[p][voto] += 1

    print(f"\n{usate} esecuzioni analizzate, voto finale per partito dichiarato\n")
    print(f"{'partito':<8}{'segue il partito':>18}{'posizione':>11}{'agenti':>9}"
          f"{'Si':>8}{'No':>8}{'Ast':>8}   voto conforme al partito")
    print("-" * 96)
    for nome, _, legato, posizione in PARTITI:
        c = tot[nome]
        n = sum(c.values())
        if not n:
            continue
        conforme = c["SI"] if posizione == "Si" else c["NO"]
        print(f"{nome:<8}{'si' if legato else 'NO':>18}{posizione:>11}{n:>9}"
              f"{100*c['SI']/n:>7.0f}%{100*c['NO']/n:>7.0f}%{100*c['ASTENUTO']/n:>7.0f}%"
              f"   {100*conforme/n:5.0f}%")

    print("""
Come leggerlo. Il confronto informativo e' FI contro FdI e Lega: stessa
posizione ufficiale, legame diverso. Se FI mostra un voto conforme molto piu'
alto, il legame con il partito conta, e la sua assenza per FdI e Lega concorre
alla spoliticizzazione. Se le quote sono simili, il legame non e' la causa.
Cautela: gli elettori di FI sono 6 per esecuzione, e possono differire da
quelli di FdI anche per altri attributi della biografia.""")


if __name__ == "__main__":
    main()
