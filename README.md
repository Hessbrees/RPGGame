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
│   └── game_state.py
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

data/
├── lore/               ← opisy świata, frakcje, klimat polityczny
├── npcs/               ← opisy postaci NPC
├── rules/              ← podręcznik zasad (dla Sędziego RAG)
├── scenarios/          ← scenariusze, punkty fabularne, zakończenia
├── chronicle/          ← dziennik fabuły (journal.json)
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
| `--open-gallery` | po sesji otwiera galerię HTML w przeglądarce |

Obrazy trafiają do `outputs/images/` (PNG, `index.jsonl` z promptami i seedami, `gallery.html`).

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
