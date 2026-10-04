#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Analisi di sensibilita' nella configurazione FINALE: come sensibilita.sh, ma
# con il legame elettore-partito (--segui-partito) in tutte le esecuzioni.
# Ogni variante cambia UN parametro rispetto al riferimento (hybrid, 24 h per
# tick, quesito ballot, seme esteso al modello, legame con il partito).
#
# Il riferimento esiste gia': sens_segui_partito_s1 e _s2. Prima della prima
# onda copialo nei nomi che il report si aspetta:
#   cp -r runs/sens_segui_partito_s1 runs/sens_lp_rif_s1
#   cp -r runs/sens_segui_partito_s2 runs/sens_lp_rif_s2
#
# Uso, dalla radice del progetto:
#   bash scripts/sensibilita_legame.sh piano  # mostra cosa lancerebbe
#   bash scripts/sensibilita_legame.sh 1      # onda 1: varianti col seme 1, piu' la ripetizione del riferimento
#   bash scripts/sensibilita_legame.sh 2      # onda 2: varianti col seme 2
# Report:
#   python scripts/sensibilita_report.py --glob 'runs/sens_lp_*' --rif ''
#
# Riprendibile: una run gia' conclusa viene saltata, una interrotta riprende.
# ---------------------------------------------------------------------------
set -u
ONDA="${1:-piano}"

BASE="--profiles start/C/reddit_profiles.json --start 2025-10-30 --days 144 \
--hours-per-tick 24 --reflection-every 2 --vote-question ./quesiti/ballot.txt \
--survey-every 30 --max-news-per-tick 30 --seed-modello --segui-partito --rpm 38 --concurrency 4"
NOTIZIE="--news start/notizieansa/notizie_referendum"
VUOTE="--news start/notizieansa/notizie_vuote"

# nome|argomenti, in ordine di utilita'. "rumore" ripete il riferimento con lo
# stesso seme: misura il rumore dello strumento nella configurazione finale.
VARIANTI=(
  "rumore|$NOTIZIE --recommender hybrid"
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

conclusa() {
  local db="$1/run.db"
  [ -f "$db" ] && [ "$(sqlite3 "$db" "SELECT COUNT(*) FROM vote WHERE label='final'" 2>/dev/null)" -gt 0 ]
}

case "$ONDA" in
  1|2) SEMI="$ONDA" ;;
  piano) SEMI="1 2" ;;
  *) echo "uso: $0 1|2|piano"; exit 1 ;;
esac

mkdir -p runs logs
n=0
for seme in $SEMI; do
  for v in "${VARIANTI[@]}"; do
    nome="${v%%|*}"; args="${v#*|}"
    # la ripetizione del riferimento serve solo con il seme 1
    if [ "$nome" = "rumore" ] && [ "$seme" != "1" ]; then continue; fi
    out="runs/sens_lp_${nome}_s${seme}"
    n=$((n + 1))
    if [ "$ONDA" = "piano" ]; then
      stato="da lanciare"; conclusa "$out" && stato="gia' conclusa"
      printf "%2d  %-30s %s\n" "$n" "$out" "$stato"
      continue
    fi
    if conclusa "$out"; then echo "[salto] $out gia' conclusa"; continue; fi
    echo "[$(date '+%d/%m %H:%M')] avvio $out"
    python run.py $BASE $args --seed "$seme" --resume --out "$out" \
      > "logs/sens_lp_${nome}_s${seme}.log" 2>&1 \
      && echo "[$(date '+%d/%m %H:%M')] conclusa $out" \
      || echo "[$(date '+%d/%m %H:%M')] ERRORE in $out, vedi logs/sens_lp_${nome}_s${seme}.log"
  done
done
[ "$ONDA" = "piano" ] && echo && echo "$n run, circa $((n * 5 / 2)) ore in sequenza a 38 richieste al minuto"
