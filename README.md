# RPGGame

Silnik sesji RPG oparty na AI – analiza porównawcza zdolności narracyjnych i decyzyjnych modeli językowych w symulowanym środowisku gier fabularnych. Wykorzystuje **LlamaIndex**, **Ollama** i **ChromaDB**.

## Architektura

```
main.py
└── GameOrchestrator              ← orkiestrator rozgrywki
    ├── Agenty LLM
    │   ├── GameMasterAgent       ← LLM jako Mistrz Gry (narracja, NPC, tempo)
    │   └── PlayerAgent           ← LLM jako Gracz (persona, decyzje, dialog)
    ├── Moduły RAG
    │   ├── LoreRAG               ← Lore master – opisy świata, bóstwa, legendy
    │   ├── NpcRAG                ← postacie NPC, dialogi, misje
    │   ├── JudgeRAG              ← Sędzia – zasady gry, profil vibe gracza
    │   └── ChronicleRAG          ← Kronikarz – pamięć fabuły, toolcalling, kompresja
    ├── Reranker                  ← BM25 / semantyczny reranker (redukcja halucynacji)
    └── GameState                 ← stan gry, tury, poziom trudności, NPC
```

## Struktura projektu

```
src/
├── orchestrator/
│   └── game_orchestrator.py
├── rags/
│   ├── base_rag.py
│   ├── lore_rag.py
│   ├── npc_rag.py
│   ├── judge_rag.py
│   ├── chronicle_rag.py
│   └── reranker.py
├── agents/
│   ├── game_master_agent.py
│   └── player_agent.py
└── game_state/
    └── game_state.py

data/
├── lore/               ← opisy świata, frakcje, klimat polityczny
├── npcs/               ← opisy postaci NPC
├── rules/              ← podręcznik zasad (dla Sędziego RAG)
├── scenarios/          ← scenariusze, punkty fabularne, zakończenia
├── chronicle/          ← dziennik fabuły (journal.json)
├── random_tables/      ← tabele losowych wydarzeń, nagród, imion NPC
└── player_preferences/ ← profile vibe rozgrywki
```

## Wymagania

- Python 3.10+
- [Ollama](https://ollama.ai/) z zainstalowanymi modelami:
  - `ollama pull llama3`
  - `ollama pull nomic-embed-text`

## Instalacja

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Uruchomienie

```bash
python main.py
```

## Style rozgrywki (vibe)

Przy inicjalizacji można wybrać styl rozgrywki:

| Vibe | Opis |
|------|------|
| `chaotyczna` | Częste losowe zdarzenia, nieprzewidywalne NPC |
| `trudna` | Surowe konsekwencje, możliwa śmierć postaci |
| `spokojna` | Narracyjna, stopniowe rozkręcanie akcji |
| `zrównoważona` | Mix akcji i narracji (domyślna) |

## Dodawanie wiedzy

Umieść pliki `.txt` lub `.md` w odpowiednich folderach:
- `data/lore/` – historia i świat gry
- `data/npcs/` – opisy postaci NPC
- `data/rules/` – zasady gry dla Sędziego RAG
- `data/scenarios/` – scenariusze i moduły przygody
- `data/random_tables/` – tabele losowe, nagrody, imiona NPC

ChromaDB automatycznie zaindeksuje dokumenty przy pierwszym uruchomieniu. Dziennik fabuły (`data/chronicle/journal.json`) jest aktualizowany automatycznie podczas rozgrywki i cyklicznie kompresowany przez ChronicleRAG.
