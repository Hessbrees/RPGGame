# Deep Learning w projekcie RPGGame – generowanie ilustracji

Stan na 2026-11-22. Szczegóły techniczne i komendy: `README.md` (sekcja „Generowanie ilustracji"); stan całego projektu i otwarte problemy: `WERYFIKACJA_IMPLEMENTACJI.md`.

## Co zostało przygotowane

- **Potok ilustracji w grze:** zdarzenia z gry → opis sceny od LLM (`SceneDirector`) → prompt (`PromptBuilder`) → Stable Diffusion 1.5 + LoRA → galeria. Tryby `deferred` (render po sesji) i `inline`; `inline` nie był sprawdzony na żywo.
- **Trening LoRA stylu:** własna pętla treningowa (`scripts/train_lora.py`), 1000 kroków, rank 16, walidacja i CLIP Score co 250 kroków. `val_loss` spadł z 0,1282 do 0,1247, a CLIP Score walidacyjny wzrósł z 32,1 do ok. 33.
- **Zbiór treningowy:** 93 obrazy (82 train, 11 val) z opisami i tokenem `rpgstyle`; panoramy dzielone na kwadratowe wycinki, podział bez wycieku między wycinkami jednego obrazu.
- **Eksperyment ilościowy** (`scripts/run_experiments.py`): 504 obrazy (14 warunków × 12 scen × 3 seedy). Porównuje model LLM piszący opis sceny (`llama3`, `qwen2.5:7b`, `mistral` i baseline bez LLM), kontekst (lore + karty postaci vs sam opis) oraz wariant obrazu (SD 1.5 vs SD 1.5 + LoRA).
- **Metryki:** CLIP Score względem niezależnego opisu referencyjnego, wierność stylu (podobieństwo CLIP do zbioru treningowego), spójność postaci (DINOv2-I, CLIP-I), jakość specyfikacji sceny (poprawność JSON, zgodność postaci, opóźnienie); różnice z 95% przedziałami ufności z bootstrapu sparowanego po scenach.
- **Testy:** 35 testów jednostkowych w `tests/` (w tym parser sceny, prompt i statystyki z `evaluation.py`).

## Główne wyniki

| Wniosek | Wynik |
|---------|-------|
| Opis sceny od LLM vs surowy tekst | CLIP Score wyższy o ok. 5,6–6,2 pkt (istotne) |
| LoRA vs base: wierność stylu | +0,016 [+0,008, +0,025] (istotne) |
| LoRA vs base: CLIP Score | −0,49 [−1,02, +0,03] (nieistotne; spadek istotny tylko dla `qwen2.5:7b`) |
| Kontekst vs brak: spójność postaci (DINOv2-I) | +0,21 [+0,12, +0,28] (istotne) |
| Kontekst vs brak: CLIP Score | brak istotnej różnicy |
| `llama3` vs `qwen2.5:7b` | brak istotnej różnicy; `mistral` ok. 1 pkt wyżej, ale najgorzej wskazuje postacie na scenie |

Pełne tabele: `outputs/experiments/main/summary.md`.

## Gdzie są materiały

| Co | Gdzie |
|----|-------|
| Kod modułu obrazów | `src/image_gen/` (`scene_director.py`, `prompt_builder.py`, `image_generator.py`, `evaluation.py`, `pipeline.py`, `gallery.py`) |
| Trening, zbiór, eksperyment | `scripts/train_lora.py`, `scripts/prepare_dataset.py`, `scripts/run_experiments.py` |
| Zbiór treningowy | `data/training/style/` (`metadata.jsonl`; surowe obrazy w `raw/style`) |
| Sceny do ewaluacji (12, z opisem referencyjnym) | `data/evaluation/scenes.json` |
| Wagi LoRA | `outputs/lora/style_r16/best` (najniższy `val_loss`) i `final`; logi `train_log.csv`, `eval_log.csv` |
| Wyniki eksperymentu | `outputs/experiments/main/`: `summary.md`, `summary.json`, `results.csv`, `consistency.csv`, `specs.json`, `prompts.json`, `comparison_*.png`, `images/` |
| Obrazy z gry | `outputs/images/` (PNG, `index.jsonl`, `gallery.html`) |
| Testy | `tests/test_image_gen.py` (oraz pozostałe testy projektu) |

## Jak odtworzyć

```powershell
# przygotowanie zbioru
python -m scripts.prepare_dataset --src raw/style --dst data/training/style --trigger rpgstyle --caption_rules data/training/caption_rules.json
# trening LoRA
python -m scripts.train_lora --data_dir data/training/style --output_dir outputs/lora/style_r16
# eksperyment (fazy specs/render/eval są wznawialne)
python -m scripts.run_experiments --out outputs/experiments/main
# gra z ilustracjami
python main.py --illustrate deferred --lora outputs/lora/style_r16/best --turns 6 --open-gallery
```

Wymagania: karta NVIDIA z CUDA (testowane na 6 GB VRAM), PyTorch z CUDA, Ollama z modelami `llama3`, `nomic-embed-text` oraz do eksperymentu `qwen2.5:7b` i `mistral`.

## Co jeszcze do zrobienia

**Do pracy zaliczeniowej**
- Opracowanie z wykresami; wykres krzywych treningu się nie wygenerował (brakowało `matplotlib`), ale dane są w CSV.
- Ocena ludzka (np. porównanie par obrazów), bo CLIP Score nie mierzy estetyki.
- Większy zbiór scen (12 to mało) i rozszerzenie `data/lore` (tylko ok. 760 B), po czym powtórzenie eksperymentu.
- Rozdzielenie wpływu lore i kart postaci w eksperymencie (obecnie jeden wariant „kontekst").

**Rozwinięcia odłożone**
- LoRA dla poszczególnych postaci (spójność wyglądu Arina i Therona).
- Kontrola liczby i pozycji postaci na obrazie (SD 1.5 myli się przy wielu postaciach).

**Niesprawdzone**
- Tryb `inline`, praca bez GPU, model SD-Turbo, kilka adapterów LoRA naraz.

**Ograniczenia wyników**
- Tylko 12 scen; przedziały dla spójności są zbyt wąskie (jednostką jest para postać–seed, nie scena).
- LoRA nie poprawia CLIP Score, a jej wpływ mierzy metryka pośrednia (podobieństwo do środka zbioru treningowego).
- Scena z goblinami pokazała 4 wojowników bez goblinów; część błędów wynika z opisu sceny od LLM, część z SD 1.5.
