# Mirorendum

Simulatore multi-agente basato su modelli linguistici (LLM) di una campagna referendaria.

Mirorendum ricostruisce una piccola rete sociale di elettori sintetici, gli fa leggere le notizie di agenzia pubblicate durante la campagna, li lascia interagire (post, risposte, mi piace) e periodicamente chiede a ciascuno come voterebbe. Il caso di studio è il **referendum costituzionale del 22–23 marzo 2026 sulla separazione delle carriere**, ma il quesito, la popolazione e le notizie sono file di ingresso: lo strumento si può riusare per un'altra consultazione senza toccare il codice.

Il progetto è stato sviluppato per la tesi di laurea triennale *"Mirorendum: simulazione multi-agente basata su LLM di una campagna referendaria"* (Ingegneria Informatica e Intelligenza Artificiale, Università Roma Tre, A.A. 2025/2026, relatore Prof. Fabio Gasparetti). È una riscrittura di MiroFish-Offline, da cui eredita l'impostazione generale (profili, feed, memoria riflessiva) ma non la dipendenza da OASIS/CAMEL.

> **Nota.** Mirorendum è uno strumento di ricerca, non uno strumento di previsione. I risultati della tesi mostrano che la simulazione completa si discosta in modo sistematico dall'esito reale; il simulatore serve soprattutto a capire *perché*.

---

## Indice

1. [Come funziona](#come-funziona)
2. [Requisiti](#requisiti)
3. [Installazione](#installazione)
4. [Configurazione del modello](#configurazione-del-modello)
5. [Dati di ingresso](#dati-di-ingresso)
6. [Primo avvio senza modello](#primo-avvio-senza-modello)
7. [Una simulazione completa](#una-simulazione-completa)
8. [Opzioni principali](#opzioni-principali)
9. [Cosa produce un'esecuzione](#cosa-produce-unesecuzione)
10. [Interrompere e riprendere](#interrompere-e-riprendere)
11. [Analisi dei risultati](#analisi-dei-risultati)
12. [Struttura del repository](#struttura-del-repository)

---

## Come funziona

La simulazione avanza a **tick** (nella configurazione della tesi, un tick = un giorno). A ogni tick:

1. le notizie ANSA del giorno vengono pubblicate da un account fonte;
2. il **recommender** compone il feed di ogni agente, mescolando post della sua rete e una quota di post esterni;
3. gli agenti attivi decidono in una sola chiamata al modello fino a tre azioni (scrivere, rispondere, mettere mi piace, non fare nulla);
4. ogni N tick gira la **riflessione**: il modello legge ciò che l'agente ha visto e decide se aggiungere una nota alla sua memoria (append-only, la biografia non viene mai riscritta);
5. ogni N tick, e comunque all'inizio e alla fine, si svolge un **sondaggio**: ciascun elettore riceve il testo della scheda e risponde SI, NO o ASTENUTO.

Tutto finisce in un database SQLite per esecuzione, interrogabile con SQL.

```
run.py ──► population (profili, rete) ──► engine (tick)
                                           ├─ news         notizie del giorno
                                           ├─ recommender  feed
                                           ├─ agent        azioni      ─┐
                                           ├─ memory       riflessione ─┼─► llm ─► endpoint OpenAI-compatibile
                                           └─ survey       voto        ─┘
                                           ▼
                                        store (run.db)
```

## Requisiti

- **Python 3.11 o superiore** (lo sviluppo è avvenuto su 3.14).
- Un **endpoint compatibile con l'API OpenAI** (`/v1/chat/completions`): vLLM, Ollama, LiteLLM, un servizio commerciale. Nella tesi è stato usato Qwen3.6-35B-A3B servito con vLLM dietro un gateway LiteLLM del laboratorio AI di Roma Tre.
- `sqlite3` da riga di comando, facoltativo ma comodo per interrogare i risultati.

Non serve una GPU sulla macchina che lancia la simulazione: il modello gira sull'endpoint.

## Installazione

```bash
git clone https://github.com/fabiani-leonardo/MirrorFish.git
cd MirrorFish

python -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Configurazione del modello

Le credenziali si leggono da variabili d'ambiente, oppure da un file `.env` nella radice del repository (caricato automaticamente con `python-dotenv`). **Non vanno mai scritte nel codice né committate.**

```dotenv
# .env
LLM_BASE_URL=https://api.ailabroma3.it/v1   # qualunque endpoint OpenAI-compatibile
LLM_API_KEY=la-tua-chiave
LLM_MODEL_NAME=lab-qwen36                    # nome del modello sull'endpoint
```

| Variabile | Obbligatoria | Default |
|---|---|---|
| `LLM_API_KEY` | sì (tranne con `--stub`) | — |
| `LLM_BASE_URL` | no | `https://api.ailabroma3.it/v1` |
| `LLM_MODEL_NAME` | no | `lab-qwen36` |

Prima di lanciare una simulazione lunga conviene verificare che l'endpoint risponda:

```bash
python scripts/endpoint.py check     # rete, TLS, una richiesta di prova
python scripts/endpoint.py probe     # consumo di token e header di rate limit
```

Se il modello ha una modalità di ragionamento (come Qwen3), il client prova a disattivarla e fa fallback automatico se il server rifiuta il parametro.

## Dati di ingresso

Una simulazione ha bisogno di tre cose:

| Ingresso | Opzione | Formato | Nel repository |
|---|---|---|---|
| Popolazione | `--profiles` | JSON di profili nello stile MiroFish (biografia, età, partito, relazioni, profondità di lettura) | `start/C/reddit_profiles.json` (100 elettori) |
| Notizie | `--news` | cartella di file `.txt`, uno per dispaccio, con la data nel nome (es. `05marzo2026-199.txt`) | `start/notizieansa/notizie_referendum/` (609 dispacci ANSA, 30/10/2025 – 21/03/2026) |
| Quesito | `--vote-question` | file di testo con la domanda posta agli agenti | `quesiti/ballot.txt` (testo della scheda reale) |

Per `--vote-question` si possono usare anche i nomi brevi `ballot`, `minimal` e `informed`. Il testo del quesito e la sua impronta vengono salvati nel database, così un file modificato dopo l'esecuzione non rende irriconoscibile il risultato.

Per simulare un altro referendum basta sostituire questi tre ingressi.

## Primo avvio senza modello

L'opzione `--stub` sostituisce il modello con risposte finte e, se mancano `--profiles` e `--news`, genera popolazione e notizie sintetiche. Serve a controllare che l'installazione funzioni, in pochi secondi e senza chiave:

```bash
python run.py --stub --agents 40 --days 5 --out runs/smoke
```

I numeri prodotti in questa modalità **non hanno alcun significato**.

## Una simulazione completa

Questo è il comando usato per le esecuzioni di riferimento della tesi (campagna dal 30 ottobre 2025 al 22 marzo 2026, 144 tick giornalieri):

```bash
python run.py --profiles start/C/reddit_profiles.json \
  --news start/notizieansa/notizie_referendum \
  --start 2025-10-30 --days 144 --hours-per-tick 24 --reflection-every 2 \
  --recommender hybrid --vote-question ./quesiti/ballot.txt --survey-every 30 \
  --max-news-per-tick 30 --seed 1 --segui-partito --seed-modello \
  --rpm 38 --concurrency 4 --resume \
  --out runs/campagna1
```

Per replicare con altri semi basta cambiare `--seed` e `--out` (un'esecuzione = una cartella). Con 100 agenti e un limite di 38 richieste al minuto un'esecuzione richiede diverse ore: conviene lanciarla con `nohup` o dentro `tmux`.

```bash
nohup python run.py ... --out runs/campagna2 --seed 2 > runs/campagna2.log 2>&1 &
```

Per vedere tutte le opzioni con i relativi default:

```bash
python run.py --help
python run.py --explain-policies     # tabella delle politiche del feed
```

## Opzioni principali

I default stanno in `mirrorfish/config.py`. Tutto ciò che influenza il risultato entra nella configurazione salvata nel database e nel suo *fingerprint*.

**Campagna e notizie**

| Opzione | Significato |
|---|---|
| `--profiles` | file JSON della popolazione |
| `--agents N` | usa solo i primi N profili |
| `--news` | cartella dei dispacci integrali |
| `--start`, `--days` | data di inizio e durata della campagna |
| `--hours-per-tick` | durata di un tick in ore: è la leva principale sul costo |
| `--max-news-per-tick` | tetto alle notizie pubblicate per tick |
| `--cf-news`, `--cf-from-tick` | controfattuale: da quel tick si usano notizie alternative |

**Rete e feed**

| Opzione | Significato |
|---|---|
| `--segui-partito` | ogni elettore segue l'account del partito indicato nella biografia |
| `--avg-degree`, `--homophily` | aggiunge legami deboli casuali fino al grado indicato, con la tendenza a legare simili; se omesso, la rete è solo quella dichiarata nelle biografie |
| `--no-relazioni` | ignora le relazioni delle biografie e costruisce la rete a caso |
| `--feed-size` | post mostrati per tick |
| `--out-of-network` | quota di post da fuori la rete dei seguiti (default 0,15) |
| `--recommender` | politica del feed: `random`, `recency`, `engagement`, `affinity`, `hybrid` |
| `--news-slots`, `--news-slots-mode` | quante notizie entrano nel feed e come dipendono dalla profondità di lettura (`gradiente`, `solo_profondita`, `uniforme`) |
| `--force-media-depth` | impone a tutti la stessa profondità di lettura (`integrale`, `titolo`, `nessuna`) |
| `--follow-drift-every` | ogni N tick chi interagisce spesso con qualcuno inizia a seguirlo; se omesso il grafo resta fisso |

**Agenti, memoria e sondaggi**

| Opzione | Significato |
|---|---|
| `--max-actions` | azioni per agente per tick, in una sola chiamata |
| `--max-post-chars` | lunghezza massima di un post (280 come X) |
| `--reflection-every` | ogni quanti tick gira la riflessione |
| `--vote-question` | quesito posto agli agenti |
| `--survey-every` | sondaggio intermedio ogni N tick, oltre a quelli iniziale e finale |

**Esecuzione**

| Opzione | Significato |
|---|---|
| `--out` | cartella dell'esecuzione |
| `--seed` | seme di popolazione, rete, feed e attività |
| `--seed-modello` | inoltra il seme anche alle richieste al modello |
| `--rpm`, `--concurrency` | richieste al minuto e chiamate in parallelo verso l'endpoint |
| `--stub` | modello finto, offline |
| `--resume` | riprende dall'ultimo tick completato |
| `--force` | cancella un `run.db` esistente e ricomincia |
| `--quiet` | meno output a terminale |

Se l'endpoint è condiviso con altre persone, non saturare il limite di richieste: il gateway non ha code a priorità e le chiamate degli altri cadrebbero per timeout.

## Cosa produce un'esecuzione

```
runs/campagna1/
├── run.db               # tutto lo stato della simulazione (SQLite)
├── shift_report.json    # transizioni di voto tra sondaggio iniziale e finale
└── graph.json           # rete sociale e interazioni, per la visualizzazione
```

Le tabelle principali di `run.db`:

| Tabella | Contenuto |
|---|---|
| `agent` | profili, biografia statica, partito, profondità di lettura, `is_voter` |
| `follow` | archi della rete sociale |
| `post` | notizie, post e risposte, con tick e autore |
| `reaction` | mi piace |
| `note` | note della memoria riflessiva, con tick e direzione (`verso_si`, `verso_no`, `nessuna`) |
| `vote` | ogni risposta di voto, con etichetta del sondaggio (`baseline`, `final`, intermedi) e motivazione |
| `llm_call` | telemetria di ogni chiamata: scopo, token, troncamenti, errori |
| `run_meta` | configurazione completa, `fingerprint`, commit git (`code_version`), testo del quesito, modello |

Esempio: voto finale degli elettori.

```bash
sqlite3 runs/campagna1/run.db \
  "SELECT vote, COUNT(*) FROM vote v JOIN agent a USING(agent_id)
   WHERE v.label = 'final' AND a.is_voter = 1 GROUP BY vote"
```

Il campo `code_version` registra il commit e se l'albero di lavoro aveva modifiche non committate: due esecuzioni con lo stesso fingerprint ma commit diversi **non** sono repliche.

## Interrompere e riprendere

- Ogni tick completato viene salvato. Se l'esecuzione si interrompe (Ctrl+C, endpoint irraggiungibile, macchina spenta), basta rilanciare lo stesso comando con `--resume`: il tick parziale viene ripulito e si riparte dal successivo.
- `--resume` rifiuta di proseguire se la configurazione è cambiata, e stampa quali parametri differiscono: un'esecuzione con parametri diversi a metà non corrisponderebbe a nessuna delle due configurazioni.
- Rilanciare su una cartella che contiene già un `run.db` senza `--resume` o `--force` è un errore voluto, per non sommare voti di due esecuzioni.
- Un file `run.lock` impedisce che due processi scrivano nella stessa cartella.
- Se l'endpoint fallisce troppe volte di seguito, la simulazione si ferma con un messaggio esplicito invece di produrre un'esecuzione vuota.

## Analisi dei risultati

Gli script in `scripts/` lavorano sui `run.db` già prodotti.

| Script | A cosa serve |
|---|---|
| `endpoint.py check \| probe \| ceiling \| concurrency` | diagnosi dell'endpoint, consumo di quota, ritmo sostenibile |
| `compare_runs.py` | confronto di più esecuzioni: quote, affluenza, traiettorie |
| `sensibilita_report.py --rif <run>` | tabella di sensibilità rispetto a un'esecuzione di riferimento |
| `revote.py` | ripete il voto su uno stato salvato, ad esempio con un quesito diverso |
| `motivazioni_chiuse.py` | chiede agli elettori le ragioni del voto su un elenco chiuso, confrontabile con il sondaggio post-voto reale |
| `b0_baseline.py`, `b0_motivazioni.py` | interrogazione diretta del modello, senza popolazione né simulazione |
| `render_feed.py`, `serve_feed.py` | il feed di un agente come pagina HTML |
| `render_graph.py` | visualizzazione interattiva della rete |
| `export_notes.py` | esporta le note della memoria riflessiva |

Ogni script accetta `--help`.

## Struttura del repository

```
MirrorFish/
├── run.py                  # punto d'ingresso
├── mirrorfish/
│   ├── config.py           # SimConfig e LLMConfig, default e fingerprint
│   ├── population.py       # caricamento dei profili e costruzione della rete
│   ├── news.py             # flusso delle notizie per tick
│   ├── recommender.py      # politiche del feed
│   ├── engine.py           # ciclo dei tick
│   ├── agent.py            # prompt e decisione delle azioni
│   ├── memory.py           # memoria riflessiva
│   ├── survey.py           # sondaggi di voto
│   ├── llm.py              # client OpenAI-compatibile, rate limit, stub
│   └── store.py            # database SQLite
├── scripts/                # diagnosi e analisi
├── quesiti/                # testi dei quesiti
├── start/                  # popolazione e notizie
├── runs/                   # esecuzioni (una cartella ciascuna)
└── requirements.txt
```

## Licenza e citazione

Se usi Mirorendum in un lavoro, cita la tesi:

> L. Fabiani, *Mirorendum: simulazione multi-agente basata su LLM di una campagna referendaria*, tesi di laurea triennale, Università degli Studi Roma Tre, A.A. 2025/2026.

I dispacci ANSA in `start/notizieansa/` sono inclusi a soli fini di ricerca e restano di proprietà dei rispettivi titolari.
