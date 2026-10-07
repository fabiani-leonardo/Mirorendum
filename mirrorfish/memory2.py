"""
Memoria riflessiva — port diretto del tuo reflective_memory.py.

Cosa resta identico (e' la parte tua, quella che vale):
  - append-only scratchpad invece di riscrivere la bio;
  - la bio statica non passa MAI attraverso l'LLM di riflessione;
  - "nessun cambiamento" deve essere il caso comune, non l'eccezione;
  - le due CRITICAL STYLE RULE (niente ID numerici, forma impersonale).

Cosa sparisce: tutta la sezione 3 del file originale, cioe' la glue con
OASIS/CAMEL (_rewrite_agent_persona_and_slide_memory, _extract_last_env_prompt,
il rimescolamento di agent.memory, la riassegnazione di agent._system_message).
Erano ~150 righe che esistevano solo per aggirare il fatto che CAMEL non
espone un setter per il system message e non fa trimming della memoria. Senza
CAMEL non servono: il prompt viene ricostruito da zero a ogni tick.

Cosa cambia: le note stanno su SQLite invece che su dynamic_profiles.json.
Niente piu' lock threading, niente scritture atomiche fatte a mano, e le note
sono interrogabili con SQL insieme a tutto il resto (utile per la tesi:
"quante note ha generato ogni fascia d'eta'" e' una query, non uno script).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .llm import LLMClient, LLMResponse, parse_json_response

REFLECTION_SYSTEM = (
    "Simuli il processo di riflessione interiore di un utente di social media. "
    "Ricevi la sua biografia statica (che definisce la sua reale identità e il suo "
    "livello di impegno politico), le note accumulate finora, e i post che ha appena letto. "
    "REGOLA 1: Il livello di interesse politico della biografia è FONDAMENTALE. "
    "Un utente disinteressato, apolitico o astenuto, nella maggior parte dei casi, scorrerà i "
    "post sul referendum ignorandoli, senza formarsi un'opinione. "
    "Segnala un cambiamento SOLO se i post toccano la sua vita privata in modo diretto. "
    "REGOLA 2: Non citare identificatori interni (es. 'post 47'). Riferisciti all'autore o al tema. "
    "REGOLA 3: Nota e motivazione vanno scritte in forma impersonale, omettendo il "
    "nome dell'agente. Inizia direttamente dall'azione. "
    "Esempi di apertura: "
    "'Si convince che...', 'Rafforza la propria posizione su...', 'Sviluppa una riserva verso...', "
    "'Cambia idea riguardo a...'. Per chi non è interessato: 'Legge il dibattito ma resta indifferente a...', "
    "'Ignora la polemica su...'. "
    "REGOLA 4: Il verbo di apertura deve concordare con l'argomento. Se l'argomento è "
    "a FAVORE, non aprire con 'rafforza la diffidenza'. "
    "Indica poi in `direzione` da che parte spinge quanto hai scritto: "
    "'verso_si' se avvicina all'approvazione, 'verso_no' se l'allontana, 'nessuna' se è "
    "solo un'osservazione senza direzione, 'ignorato' se l'utente non si fa coinvolgere. "
    "REGOLA 5: Non attribuire all'agente posizioni non supportate dalla biografia. "
    "Se è disinteressato, la reazione attesa è ignorare il post politico. "
    "Rispondi solo con un oggetto JSON, in italiano, senza prosa attorno."
)

REFLECTION_USER = """Biografia statica (definizione dell'identita'):
\"\"\"{bio}\"\"\"

Note accumulate finora:
{notes}

Post appena letti:
{posts}

Decidi se questi post colpiscono l'agente al punto da formare, spostare o rafforzare
un'opinione, TENENDO CONTO del suo livello di interesse politico. 
Se i post sono banali, gia' coerenti con le note esistenti, O SE L'AGENTE E' DISINTERESSATO
alla politica, NON aggiungere una nota (imposta "note_added": false): questo deve essere il caso comune.

Se e solo se qualcosa e' davvero cambiato, scrivi UNA frase breve (max {max_chars}
caratteri) in forma impersonale.

Rispondi esattamente in questa forma:
{{"note_added": true/false, "note": "la frase, o stringa vuota",
  "direzione": "verso_si" | "verso_no" | "nessuna" | "ignorato",
  "reasoning": "una proposizione che spieghi la scelta basata sulla biografia"}}"""


@dataclass
class ReflectionResult:
    agent_id: int
    note_added: bool = False
    note: str = ""
    direzione: str = "nessuna"
    reasoning: str = ""
    error: str | None = None


class ReflectionEngine:
    def __init__(self, client: LLMClient, max_note_chars: int = 400):
        self.client = client
        self.max_note_chars = max_note_chars

    async def reflect(
        self,
        agent: sqlite3.Row,
        existing_notes: list[str],
        recent_posts: list[str],
        *,
        max_tokens: int,
        temperature: float,
    ) -> tuple[ReflectionResult, LLMResponse | None]:
        agent_id = int(agent["agent_id"])
        if not recent_posts:
            return ReflectionResult(agent_id, reasoning="niente da leggere"), None

        user = REFLECTION_USER.format(
            bio=(agent["static_bio"] or "")[:1500],
            notes="\n".join(f"- {n}" for n in existing_notes[-10:]) or "(nessuna)",
            posts="\n".join(f"- {p}" for p in recent_posts if p and p.strip()),
            max_chars=self.max_note_chars,
        )
        resp = await self.client.complete(
            REFLECTION_SYSTEM, user,
            max_tokens=max_tokens, temperature=temperature, json_mode=True,
        )
        if resp.error:
            return ReflectionResult(agent_id, error=f"llm:{resp.error}"), resp

        data = parse_json_response(resp.text)
        if not isinstance(data, dict):
            reason = "truncated" if resp.truncated else "unparsable"
            return ReflectionResult(agent_id, error=f"parse:{reason}"), resp

        note = str(data.get("note") or "").strip()
        added = bool(data.get("note_added", False))
        if len(note) > self.max_note_chars:
            note = note[: self.max_note_chars].rsplit(" ", 1)[0] + "..."
        if added and not note:
            added = False

        direzione = str(data.get("direzione") or "nessuna").strip().lower()
        if direzione not in ("verso_si", "verso_no", "nessuna","ignorato"):
            direzione = "nessuna"

        return ReflectionResult(
            agent_id=agent_id, note_added=added, note=note,
            reasoning=str(data.get("reasoning") or ""), direzione=direzione,
        ), resp
