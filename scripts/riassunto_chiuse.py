#!/usr/bin/env python3
"""
riassunto_chiuse — riassume i log di motivazioni_chiuse.py in una tabella,
con i criteri C3 e C4 fissati al paragrafo 6.7.

  C3  le ragioni politiche sono assenti   N3 (opposizione al Governo) < 10%
  C4  il No simulato e' nel merito         N7 (contro la separazione) > 30%

Accanto riporta S5 (sostegno al Governo, fra i favorevoli) e l'opzione
fittizia NX, che misura il fondo di adesione automatica fra i contrari.

Uso, dalla radice del progetto:
  python scripts/riassunto_chiuse.py                 # tutti i logs/chiuse_*.log
  python scripts/riassunto_chiuse.py logs/chiuse_sens_*.log
"""

import glob
import re
import sys

RIGA = re.compile(r"^\s+(S\d|N\d|SX|NX)\s+(\d+)%", re.M)
NUM = re.compile(r"Ha votato (SI|NO): (\d+) agenti")


def leggi(path):
    testo = open(path, encoding="utf-8", errors="replace").read()
    quote = {k: int(v) for k, v in RIGA.findall(testo)}
    n = dict(NUM.findall(testo))
    return quote, int(n.get("SI", 0)), int(n.get("NO", 0))


def main():
    files = sys.argv[1:] or sorted(glob.glob("logs/chiuse_*.log"))
    if not files:
        print("nessun log trovato"); return
    print(f"\n{'esecuzione':<30}{'n Si':>5}{'n No':>5}{'S5':>6}{'SX':>6}  |{'N1':>5}{'N2':>5}{'N3':>5}{'N6':>5}{'N7':>5}{'NX':>5}    C3   C4")
    print("-" * 102)
    c3_no, c4_no, righe = [], [], 0
    for f in files:
        q, nsi, nno = leggi(f)
        if "N3" not in q:
            print(f"{f:<34}  (log incompleto o non leggibile)")
            continue
        righe += 1
        nome = re.sub(r"^.*chiuse_|\.log$", "", f)
        c3 = q["N3"] < 10
        c4 = q.get("N7", 0) > 30
        if not c3: c3_no.append(nome)
        if not c4: c4_no.append(nome)
        s5 = f"{q['S5']}%" if nsi else "-"
        sx = f"{q.get('SX', 0)}%" if nsi else "-"
        no = "".join(f"{q.get(k, 0):>4}%" for k in ("N1", "N2", "N3", "N6", "N7", "NX"))
        print(f"{nome:<30}{nsi:>5}{nno:>5}{s5:>6}{sx:>6}  |{no}"
              f"   {' si ' if c3 else ' NO '} {' si ' if c4 else ' NO '}")
    print(f"\nC3, ragioni politiche assenti: "
          + (f"regge in tutte le {righe} esecuzioni" if not c3_no else f"NON regge in {', '.join(c3_no)}"))
    print(f"C4, No nel merito: "
          + (f"regge in tutte le {righe} esecuzioni" if not c4_no else f"NON regge in {', '.join(c4_no)}"))
    print("Ogni quota va letta accanto all'opzione fittizia del proprio fronte, SX per i"
          " favorevoli e NX per i contrari: cio' che non la supera e' compatibile con la"
          " sola adesione automatica. Con pochi favorevoli, S5 e SX poggiano su pochi agenti.")


if __name__ == "__main__":
    main()
