# RPGGame

Silnik RPG oparty na AI z wieloma modułami RAG i orkiestratorem, używający **LlamaIndex**, **Ollama** i **ChromaDB**.

## Architektura

```
main.py
└── GameOrchestrator          ← kieruje zapytania do właściwego RAG
    ├── LoreRAG               ← wiedza o świecie, historia, frakcje
    ├── NpcRAG                ← postacie NPC, dialogi, misje
    └── CombatRAG             ← mechaniki walki, czary, statystyki
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

## Dodawanie wiedzy

Umieść pliki `.txt` lub `.md` w odpowiednich folderach:
- `data/lore/` – historia i świat gry
- `data/npcs/` – opisy postaci NPC
- `data/combat/` – zasady i mechaniki walki

ChromaDB automatycznie zaindeksuje dokumenty przy pierwszym uruchomieniu.
