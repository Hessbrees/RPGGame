# RPGGame

Silnik sesji RPG oparty na AI – analiza porównawcza zdolności narracyjnych i decyzyjnych modeli językowych w symulowanym środowisku gier fabularnych. Wykorzystuje **LlamaIndex**, **Ollama** i **ChromaDB**. Przebieg rozgrywki może być ilustrowany obrazami generowanymi przez model dyfuzyjny (**Stable Diffusion 1.5 + LoRA**).

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
    ├── IllustrationPipeline      ← ilustracje z przebiegu gry (opcjonalne, --illustrate)
    │   ├── SceneDirector         ← LLM: polskie zdarzenia → opis sceny (JSON, EN) + ocena ważności
    │   ├── PromptBuilder         ← scena + karty postaci + stały blok stylu (budżet 75 tokenów CLIP)
    │   ├── ImageGenerator        ← Stable Diffusion 1.5 (diffusers) + adaptery LoRA
    │   └── Gallery               ← zapis PNG, index.jsonl, galeria HTML
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
├── game_state/
│   ├── game_state.py
│   └── state_updater.py      ← parser odpowiedzi arbitra i stosowanie zmian HP/ekwipunku, filtr narracji
└── image_gen/
    ├── config.py             ← konfiguracja (zmienne IMAGE_*)
    ├── scene_director.py
    ├── character_sheets.py   ← stałe opisy wizualne postaci, modyfikatory z HP
    ├── prompt_builder.py
    ├── image_generator.py
    ├── gallery.py
    ├── pipeline.py
    └── evaluation.py         ← CLIP Score, spójność (DINOv2/CLIP), bootstrap

scripts/
├── prepare_dataset.py        ← przygotowanie zbioru treningowego LoRA
├── train_lora.py             ← trening LoRA stylu (własna pętla, walidacja, CLIP Score)
└── run_experiments.py        ← eksperyment porównawczy (LLM × kontekst × LoRA)

tests/                      ← testy jednostkowe z atrapą LLM (pytest, bez Ollamy)

data/
├── lore/               ← opisy świata, frakcje, klimat polityczny
├── npcs/               ← opisy postaci NPC
├── rules/              ← podręcznik zasad (dla Sędziego RAG)
├── scenarios/          ← scenariusze, punkty fabularne, zakończenia
├── chronicle/          ← dziennik bieżącej sesji (journal.json); archiwum poprzednich sesji w archive/
├── random_tables/      ← tabele losowych wydarzeń, nagród, imion NPC
├── player_preferences/ ← profile vibe rozgrywki
├── training/           ← zbiór treningowy LoRA (metadata.jsonl, podział train/val)
└── evaluation/         ← scenes.json: 12 scen z opisem referencyjnym do ewaluacji

outputs/                ← generowane: images/ (galeria), lora/ (wagi), experiments/ (wyniki)
```

## Wymagania

- Python 3.10+
- [Ollama](https://ollama.ai/) z zainstalowanymi modelami:
  - `ollama pull llama3`
  - `ollama pull nomic-embed-text`
- Do ilustracji (opcjonalnie): karta NVIDIA z CUDA (testowane na 6 GB VRAM – RTX 4050 Laptop) i PyTorch z CUDA
- Do porównania modeli w eksperymencie: `ollama pull qwen2.5:7b` oraz `ollama pull mistral`

## Instalacja

```bash
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # PyTorch z CUDA (tylko dla ilustracji)
pip install -r requirements.txt
cp .env.example .env
```

## Uruchomienie

```bash
python main.py
```

Z ilustracjami:

```bash
python main.py --illustrate deferred --lora outputs/lora/style_r16/best --turns 6 --open-gallery
```

| Opcja | Opis |
|-------|------|
| `--illustrate off\|inline\|deferred` | `inline` – obraz zaraz po zdarzeniu; `deferred` – kolejka renderowana po sesji (oszczędza VRAM) |
| `--lora ŚCIEŻKA` | wagi LoRA (można podać wielokrotnie) |
| `--turns N` | maksymalna liczba tur (domyślnie 10) |
| `--gm-model MODEL` | osobny model Ollama dla Mistrza Gry (domyślnie `OLLAMA_MODEL`) |
| `--player-model MODEL...` | model dla graczy: jeden dla wszystkich albo dwa (Arin, Theron) |
| `--keep-journal` | nie archiwizuj dziennika poprzedniej sesji, dopisuj do niego |
| `--open-gallery` | po sesji otwiera galerię HTML w przeglądarce |

Przykład z różnymi modelami: `python main.py --gm-model qwen2.5:7b --player-model llama3 mistral`. Ollama sama wymienia modele w pamięci GPU, więc przy 6 GB VRAM każda zmiana modelu w trakcie tury chwilę trwa.

### Przebieg rozgrywki

- Tryb swobodny: gracze rozmawiają, a GM kończy rozmowę, gdy padą słowa o akcji (heurystyka) lub rozmowa się przeciąga. Tryb turowy: każdy gracz wybiera akcję, a po 3 rundach GM wraca do rozmowy swobodnej.
- Po każdej akcji GM opisuje skutki (zna imię i klasę gracza, zasady z Sędziego RAG i stan gry), a arbiter (drugie wywołanie LLM) ustala zmiany dla wszystkich graczy. HP, ekwipunek i status `active` są aktualizowane w kodzie (`[Stan] Arin: HP 100 -> 80` w konsoli i w dzienniku); gra kończy się porażką, gdy wszyscy gracze tracą przytomność.
- Zmiany stanu wynikają z oceny LLM, więc ich jakość zależy od modelu. Rzuty k20 są tylko opisywane w narracji, a nie liczone w kodzie.

Obrazy trafiają do `outputs/images/` (PNG, `index.jsonl` z promptami i seedami, `gallery.html`).

## Style rozgrywki (vibe)

Styl rozgrywki jest parametrem `vibe` w `GameOrchestrator` (w `main.py` ustawiony na `zrównoważona`; wyboru w CLI jeszcze nie ma):

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

Indeksy ChromaDB budowane są od zera tylko wtedy, gdy zmieni się zawartość plików w folderze lub model embeddings (odcisk w `chroma_db/rag_fingerprints.json`), więc restart nie dubluje wpisów. Dziennik fabuły (`data/chronicle/journal.json`) zaczyna się pusty w każdej sesji (poprzedni trafia do `data/chronicle/archive/`; `--keep-journal` to wyłącza), jest uzupełniany podczas rozgrywki i kompresowany przez ChronicleRAG po przekroczeniu 40 wpisów.

## Testy

```bash
pip install pytest
pytest tests
```

Testy (35) używają atrapy LLM i fałszywych embeddingów, więc nie wymagają Ollamy ani GPU: indeksowanie RAG bez duplikatów, parser i stosowanie zmian stanu, orkiestrator (imię gracza w prompcie GM, HP, koniec gry, przełączanie trybów, dziennik, osobne modele) oraz `image_gen` (parser sceny, prompt, statystyki). Skrypty `test_core_functionality.py` i `test_polish.py` w katalogu głównym to stare testy ręczne wymagające Ollamy i nie są częścią zestawu.

## Generowanie ilustracji

### Jak to działa

1. Ilustrację wyzwala tylko narracja Mistrza Gry. `SceneDirector` (LLM) zamienia polskie zdarzenia na opis sceny w JSON po angielsku (miejsce, postacie, akcja, nastrój, światło) i ocenia jego ważność w skali 1–5.
2. Obraz powstaje, gdy ważność ≥ progu (`IMAGE_IMPORTANCE_THRESHOLD`, domyślnie 4); pierwsza scena jest ilustrowana zawsze, a łącznie nie więcej niż `IMAGE_MAX_IMAGES`.
3. `PromptBuilder` składa prompt z opisu sceny, kart postaci (stałe opisy wyglądu Arina i Therona, modyfikatory z HP, np. „wounded") i stałego bloku stylu. Ucinany jest tylko opis sceny, więc styl zawsze mieści się w limicie CLIP.
4. `ImageGenerator` generuje obraz (SD 1.5, 512×512, ten sam seed i prompt dają ten sam wynik).
5. Ollama i model dyfuzyjny nie mieszczą się razem w 6 GB VRAM, dlatego przed renderowaniem model Ollama jest wyładowywany (`IMAGE_UNLOAD_OLLAMA`).

### Konfiguracja (`.env`)

| Zmienna | Domyślnie | Opis |
|---------|-----------|------|
| `IMAGE_GEN_MODE` | `off` | `off` / `inline` / `deferred` |
| `IMAGE_MODEL_ID` | `stable-diffusion-v1-5/stable-diffusion-v1-5` | model bazowy |
| `IMAGE_LORA_PATHS` | – | wagi LoRA rozdzielone średnikiem |
| `IMAGE_LORA_SCALE` | `0.8` | siła adaptera LoRA |
| `IMAGE_STEPS`, `IMAGE_GUIDANCE`, `IMAGE_SEED` | `25`, `7.0`, `42` | parametry generowania |
| `IMAGE_OUTPUT_DIR` | `./outputs/images` | katalog wyjściowy |
| `IMAGE_IMPORTANCE_THRESHOLD`, `IMAGE_MAX_IMAGES` | `4`, `20` | filtr ilustrowanych scen |
| `IMAGE_UNLOAD_OLLAMA` | `true` | zwalnianie VRAM przed renderowaniem |

### Trening LoRA stylu

Przygotowanie zbioru (obrazy w `raw/style`; panoramy są dzielone na kwadratowe wycinki, podział train/val bez wycieku między wycinkami jednego obrazu):

```bash
python -m scripts.prepare_dataset --src raw/style --dst data/training/style --trigger rpgstyle --caption_rules data/training/caption_rules.json
```

Trening (domyślnie rank 16, 1000 kroków, batch 2 × akumulacja 2, ok. 1,2–2 s/krok na RTX 4050):

```bash
python -m scripts.train_lora --data_dir data/training/style --output_dir outputs/lora/style_r16
```

Co `--eval_every` kroków liczone są `val_loss` i CLIP Score na obrazach walidacyjnych. Wagi zapisują się do `best/` (najniższy `val_loss`) i `final/`; logi do `train_log.csv` i `eval_log.csv`. W przebiegu referencyjnym `val_loss` spadł z 0,1282 do 0,1247, a CLIP Score walidacyjny wzrósł z 32,1 do ok. 33.

### Eksperyment porównawczy

```bash
python -m scripts.run_experiments --out outputs/experiments/main
```

Porównuje (te same sceny i seedy, więc różnice są sparowane):

- **model opisujący scenę:** `llama3`, `qwen2.5:7b`, `mistral` oraz baseline `naive` (surowy polski tekst, bez LLM),
- **kontekst:** lore z RAG i karty postaci vs sam opis zdarzeń,
- **wariant obrazu:** SD 1.5 vs SD 1.5 + LoRA.

Metryki: CLIP Score względem niezależnego opisu referencyjnego, wierność stylu (podobieństwo CLIP do zbioru treningowego), spójność postaci (DINOv2-I, CLIP-I) oraz jakość specyfikacji sceny (poprawność JSON, zgodność postaci, opóźnienie). Różnice mają 95% przedziały ufności z bootstrapu po scenach. Fazy (`--phase specs|render|eval|all`) są wznawialne. Wyniki trafiają do `summary.md`, `summary.json`, `results.csv`, `consistency.csv` oraz siatek porównawczych `comparison_*.png`.

Wyniki przebiegu referencyjnego (12 scen × 3 seedy, 504 obrazy):

| Wniosek | Wynik |
|---------|-------|
| Opis sceny od LLM vs surowy tekst | CLIP Score wyższy o ok. 5,6–6,2 pkt (istotne) |
| LoRA vs base: wierność stylu | +0,016 [+0,008, +0,025] (istotne) |
| LoRA vs base: CLIP Score | −0,49 [−1,02, +0,03] (nieistotne; spadek istotny tylko dla `qwen2.5:7b`) |
| Kontekst vs brak: spójność postaci (DINOv2-I) | +0,21 [+0,12, +0,28] (istotne) |
| Kontekst vs brak: CLIP Score | brak istotnej różnicy |
| `llama3` vs `qwen2.5:7b` | brak istotnej różnicy; `mistral` ok. 1 pkt wyżej, ale najgorzej wskazuje postacie na scenie |

Ograniczenia: tylko 12 scen; przedziały dla spójności są zbyt wąskie (jednostką jest para postać–seed, a nie niezależna scena); kontekst łączy lore i karty postaci, więc nie rozdziela ich wpływu; SD 1.5 słabo radzi sobie ze scenami z wieloma postaciami.
