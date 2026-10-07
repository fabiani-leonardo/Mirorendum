#!/usr/bin/env bash
# Raccoglie in dati_tesi.txt i dati che mancano alla tesi.
# Uso, dalla radice del repository:  bash raccogli_dati.sh
# Poi incolla in chat il contenuto di dati_tesi.txt.
set -u
REF=runs/sens_segui_partito_s1
VER=runs/campagna1-1
NEWS=start/notizieansa/notizie_referendum
OUT=dati_tesi.txt
G="CASE WHEN a.static_bio LIKE '%vota Fratelli%' OR a.static_bio LIKE '%vota Forza Italia%' OR a.static_bio LIKE '%vota Lega%' THEN 'centrodestra' WHEN a.static_bio LIKE '%vota Partito Democratico%' OR a.static_bio LIKE '%vota Movimento 5%' OR a.static_bio LIKE '%vota Alleanza%' THEN 'centrosinistra' WHEN a.static_bio NOT LIKE '%vota %' THEN 'senza partito' ELSE 'altri' END"

{
echo "== 1. Commit, impronta e configurazione (appendice A)"
for r in "$REF" "$VER"; do
  echo "-- $r"
  sqlite3 "$r/run.db" "SELECT key, value FROM run_meta WHERE key IN ('fingerprint','code_version','vote_question','llm')"
  sqlite3 "$r/run.db" "SELECT value FROM run_meta WHERE key = 'sim_config'"
done

echo; echo "== 2. Il prompt di riflessione nei due commit (paragrafo 7.5, appendice D)"
for r in "$REF" "$VER"; do
  C=$(sqlite3 "$r/run.db" "SELECT json_extract(value, '\$.commit') FROM run_meta WHERE key = 'code_version'")
  S=$(sqlite3 "$r/run.db" "SELECT json_extract(value, '\$.modifiche_non_committate') FROM run_meta WHERE key = 'code_version'")
  echo "-- $r: commit $C, modifiche non committate: $S"
  git show "$C:mirrorfish/memory.py" 2>/dev/null | grep -n "IN VOTO\|solo come contesto\|ignorato" \
    || echo "   (nessuna corrispondenza, o commit non trovato)"
done
echo "-- albero di lavoro attuale:"
grep -n "IN VOTO\|solo come contesto\|ignorato" mirrorfish/memory.py || echo "   (nessuna corrispondenza)"

echo; echo "== 3. Note e riflessioni per gruppo (paragrafo 7.5)"
for r in "$REF" "$VER"; do
  echo "-- $r: gruppo | note | agenti con almeno una nota"
  sqlite3 "$r/run.db" "SELECT $G AS gruppo, COUNT(n.note_id), COUNT(DISTINCT n.agent_id) FROM note n JOIN agent a ON a.agent_id = n.agent_id WHERE a.is_voter = 1 GROUP BY gruppo"
  echo "   chiamate di riflessione per gruppo:"
  sqlite3 "$r/run.db" "SELECT $G AS gruppo, COUNT(*) FROM llm_call c JOIN agent a ON a.agent_id = c.agent_id WHERE c.purpose = 'reflection' AND a.is_voter = 1 GROUP BY gruppo"
done
echo "-- riferimento, senza partito: voto finale | agenti | note medie"
sqlite3 "$REF/run.db" "SELECT v.vote, COUNT(*), ROUND(AVG((SELECT COUNT(*) FROM note n WHERE n.agent_id = a.agent_id)), 1) FROM vote v JOIN agent a ON a.agent_id = v.agent_id WHERE v.label = 'final' AND a.is_voter = 1 AND a.static_bio NOT LIKE '%vota %' GROUP BY v.vote"
echo "-- verifica, testo delle note dei senza partito:"
sqlite3 "$VER/run.db" "SELECT n.tick, n.direzione, n.note FROM note n JOIN agent a ON a.agent_id = n.agent_id WHERE a.is_voter = 1 AND a.static_bio NOT LIKE '%vota %' ORDER BY n.tick"

echo; echo "== 4. Corpus ANSA (bibliografia, paragrafo 8.1)"
echo "-- numero di file:"; ls "$NEWS" | wc -l
echo "-- date di modifica, prima e ultima:"; ls -lt "$NEWS" | sed -n '2p;$p'
echo "-- dispacci che citano un sondaggio:"; grep -lis "sondagg" "$NEWS"/* | wc -l

echo; echo "== 5. Griglia di sensibilita' con il legame (paragrafo 7.8)"
ls -d runs/sens_lp_* 2>/dev/null || echo "(nessuna esecuzione sens_lp_*)"
} > "$OUT" 2>&1

echo "Fatto: $OUT"
