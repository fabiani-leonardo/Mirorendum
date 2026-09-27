#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Analisi di sensibilita' ai parametri arbitrari: raccomandatore, quota fuori
# rete, temperature, corpus. Ogni variante cambia UN parametro rispetto alla
# configurazione di riferimento (hybrid, 24 h per tick, quesito ballot, seme
# esteso al modello).
#
# Uso, dalla radice del progetto:
#   bash scripts/sensibilita.sh 1      # onda 1: tutte le varianti col seme 1
#   bash scripts/sensibilita.sh 2      # onda 2: tutte le varianti col seme 2
#   bash scripts/sensibilita.sh piano  # mostra cosa lancerebbe, senza lanciare
#
# Riprendibile: una run gia' conclusa viene saltata, una interrotta riprende.
# Richiede le patch seed_modello e temperature gia' applicate.
# La run di riferimento col seme 1 esiste gia' (campagna_completa3): non viene
# rilanciata.
# ---------------------------------------------------------------------------
set -u
ONDA="${1:-piano}"

BASE="--profiles start/C/reddit_profiles.json --start 2025-10-30 --days 144 \
--hours-per-tick 24 --reflection-every 2 --vote-question ./quesiti/ballot.txt \
--survey-every 30 --max-news-per-tick 30 --seed-modello --rpm 38 --concurrency 4"
NOTIZIE="--news start/notizieansa/notizie_referendum"
VUOTE="--news start/notizieansa/notizie_vuote"

# nome|argomenti. L'ordine e' quello di utilita': se l'onda si interrompe a
# meta', le varianti piu' informative sono gia' state eseguite.
VARIANTI=(
  "rif|$NOTIZIE --recommender hybrid"
  "senza_notizie|$VUOTE --recommender hybrid"
  "random|$NOTIZIE --recommender random"
  "recency|$NOTIZIE --recommender recency"
  "fuori_rete_50|$NOTIZIE --recommender hybrid --out-of-network 0.5"
  "riflessione_02|$NOTIZIE --recommender hybrid --temperatura-riflessione 0.2"
  "riflessione_07|$NOTIZIE --recommender hybrid --temperatura-riflessione 0.7"
  "azione_04|$NOTIZIE --recommender hybrid --temperatura-azione 0.4"
  "azione_10|$NOTIZIE --recommender hybrid --temperatura-azione 1.0"
  "engagement|$NOTIZIE --recommender engagement"
  "affinity|$NOTIZIE --recommender affinity"
)

conclusa() {  # la run ha gia' la rilevazione finale?
  local db="$1/run.db"
  [ -f "$db" ] && [ "$(sqlite3 "$db" "SELECT COUNT(*) FROM vote WHERE label='final'" 2>/dev/null)" -gt 0 ]
}

case "$ONDA" in
  1|2) SEME="$ONDA" ;;
  piano) SEME="" ;;
  *) echo "uso: $0 1|2|piano"; exit 1 ;;
esac

mkdir -p runs logs
n=0
for semi in ${SEME:-1 2}; do
  for v in "${VARIANTI[@]}"; do
    nome="${v%%|*}"; args="${v#*|}"
    # la run di riferimento col seme 1 esiste gia'
    if [ "$nome" = "rif" ] && [ "$semi" = "1" ]; then continue; fi
    out="runs/sens_${nome}_s${semi}"
    n=$((n + 1))
    if [ "$ONDA" = "piano" ]; then
      stato="da lanciare"; conclusa "$out" && stato="gia' conclusa"
      printf "%2d  %-26s %s\n" "$n" "$out" "$stato"
      continue
    fi
    if conclusa "$out"; then
      echo "[salto] $out gia' conclusa"; continue
    fi
    echo "[$(date '+%d/%m %H:%M')] avvio $out"
    python run.py $BASE $args --seed "$semi" --resume --out "$out" \
      > "logs/sens_${nome}_s${semi}.log" 2>&1 \
      && echo "[$(date '+%d/%m %H:%M')] conclusa $out" \
      || echo "[$(date '+%d/%m %H:%M')] ERRORE in $out, vedi logs/sens_${nome}_s${semi}.log"
  done
done
[ "$ONDA" = "piano" ] && echo && echo "$n run, circa $((n * 5 / 2)) ore in sequenza a 38 richieste al minuto"
