# Wyniki eksperymentu

## CLIP Score (obraz vs opis referencyjny; średnia po scenach, 95% CI)

| LLM | kontekst | wariant | n scen | CLIP Score | 95% CI |
|---|---|---|---|---|---|
| llama3 | ctx | base | 12 | 29.60 | [27.10, 31.51] |
| llama3 | ctx | lora | 12 | 30.00 | [28.09, 31.62] |
| llama3 | noctx | base | 12 | 31.00 | [30.04, 31.83] |
| llama3 | noctx | lora | 12 | 29.83 | [28.61, 30.92] |
| mistral | ctx | base | 12 | 31.35 | [29.97, 32.69] |
| mistral | ctx | lora | 12 | 31.36 | [30.10, 32.51] |
| mistral | noctx | base | 12 | 31.26 | [30.34, 32.23] |
| mistral | noctx | lora | 12 | 30.70 | [29.73, 31.70] |
| naive | noctx | base | 12 | 24.88 | [23.14, 26.55] |
| naive | noctx | lora | 12 | 24.77 | [23.06, 26.24] |
| qwen2.5:7b | ctx | base | 12 | 30.11 | [28.73, 31.45] |
| qwen2.5:7b | ctx | lora | 12 | 29.38 | [27.90, 30.81] |
| qwen2.5:7b | noctx | base | 12 | 31.37 | [30.38, 32.42] |
| qwen2.5:7b | noctx | lora | 12 | 30.13 | [28.99, 31.27] |

## Porównania sparowane (różnica CLIP Score, bootstrap po scenach)

| Porównanie | pary | różnica [95% CI] | istotne |
|---|---|---|---|
| LoRA vs base (wszystkie) | 252 | -0.49 [-1.02, +0.03] | nie |
| ctx vs noctx (wszystkie) | 216 | -0.42 [-1.87, +0.73] | nie |
| LoRA vs base (llama3) | 72 | -0.38 [-1.04, +0.29] | nie |
| LoRA vs base (mistral) | 72 | -0.27 [-1.03, +0.63] | nie |
| LoRA vs base (naive) | 36 | -0.11 [-1.07, +0.82] | nie |
| LoRA vs base (qwen2.5:7b) | 72 | -0.98 [-1.59, -0.39] | tak |
| ctx vs noctx (llama3) | 72 | -0.62 [-3.14, +1.33] | nie |
| ctx vs noctx (mistral) | 72 | +0.37 [-0.96, +1.59] | nie |
| ctx vs noctx (qwen2.5:7b) | 72 | -1.01 [-2.59, +0.31] | nie |
| llama3 vs mistral (noctx+ctx dopasowane) | 144 | -1.06 [-2.22, -0.11] | tak |
| llama3 vs naive (noctx+ctx dopasowane) | 72 | +5.59 [+4.75, +6.50] | tak |
| llama3 vs qwen2.5:7b (noctx+ctx dopasowane) | 144 | -0.14 [-1.15, +0.77] | nie |
| mistral vs naive (noctx+ctx dopasowane) | 72 | +6.16 [+5.23, +7.28] | tak |
| mistral vs qwen2.5:7b (noctx+ctx dopasowane) | 144 | +0.92 [+0.31, +1.54] | tak |
| naive vs qwen2.5:7b (noctx+ctx dopasowane) | 72 | -5.93 [-7.46, -4.38] | tak |

## Wierność stylu (cos CLIP do środka zbioru treningowego LoRA; średnia po scenach, 95% CI)

| LLM | kontekst | wariant | podobieństwo | 95% CI |
|---|---|---|---|---|
| llama3 | ctx | base | 0.7732 | [0.7582, 0.7871] |
| llama3 | ctx | lora | 0.8011 | [0.7871, 0.8160] |
| llama3 | noctx | base | 0.7638 | [0.7430, 0.7823] |
| llama3 | noctx | lora | 0.7820 | [0.7685, 0.7954] |
| mistral | ctx | base | 0.7783 | [0.7617, 0.7936] |
| mistral | ctx | lora | 0.7815 | [0.7640, 0.7960] |
| mistral | noctx | base | 0.7411 | [0.7092, 0.7714] |
| mistral | noctx | lora | 0.7573 | [0.7336, 0.7801] |
| naive | noctx | base | 0.7650 | [0.7546, 0.7755] |
| naive | noctx | lora | 0.7919 | [0.7811, 0.8022] |
| qwen2.5:7b | ctx | base | 0.7781 | [0.7570, 0.7930] |
| qwen2.5:7b | ctx | lora | 0.7911 | [0.7657, 0.8090] |
| qwen2.5:7b | noctx | base | 0.7531 | [0.7272, 0.7749] |
| qwen2.5:7b | noctx | lora | 0.7577 | [0.7247, 0.7845] |

| Porównanie stylu | pary | różnica [95% CI] | istotne |
|---|---|---|---|
| LoRA vs base (wszystkie) | 252 | +0.0157 [+0.0080, +0.0246] | tak |
| LoRA vs base (llama3) | 72 | +0.0231 [+0.0103, +0.0380] | tak |
| LoRA vs base (mistral) | 72 | +0.0097 [-0.0023, +0.0242] | nie |
| LoRA vs base (naive) | 36 | +0.0269 [+0.0151, +0.0395] | tak |
| LoRA vs base (qwen2.5:7b) | 72 | +0.0088 [-0.0018, +0.0180] | nie |

## Spójność postaci (średnie podobieństwo kosinusowe obrazów jednej postaci)

| LLM | kontekst | wariant | DINOv2-I | CLIP-I |
|---|---|---|---|---|
| llama3 | ctx | base | 0.554 | 0.804 |
| llama3 | ctx | lora | 0.561 | 0.804 |
| llama3 | noctx | base | 0.330 | 0.743 |
| llama3 | noctx | lora | 0.378 | 0.783 |
| mistral | ctx | base | 0.524 | 0.786 |
| mistral | ctx | lora | 0.471 | 0.765 |
| mistral | noctx | base | 0.284 | 0.722 |
| mistral | noctx | lora | 0.325 | 0.735 |
| naive | noctx | base | 0.478 | 0.862 |
| naive | noctx | lora | 0.519 | 0.871 |
| qwen2.5:7b | ctx | base | 0.554 | 0.795 |
| qwen2.5:7b | ctx | lora | 0.537 | 0.818 |
| qwen2.5:7b | noctx | base | 0.313 | 0.733 |
| qwen2.5:7b | noctx | lora | 0.327 | 0.743 |

| Porównanie spójności | pary | różnica [95% CI] | istotne |
|---|---|---|---|
| dino: LoRA vs base | 42 | +0.01 [-0.00, +0.03] | nie |
| dino: ctx vs noctx | 36 | +0.21 [+0.12, +0.28] | tak |
| clip_i: LoRA vs base | 42 | +0.01 [-0.00, +0.02] | nie |
| clip_i: ctx vs noctx | 36 | +0.05 [+0.02, +0.08] | tak |

## Jakość specyfikacji scen (SceneDirector)

| LLM | kontekst | n | poprawny JSON | postacie zgodne | opóźnienie [s] | śr. ważność |
|---|---|---|---|---|---|---|
| llama3 | ctx | 12 | 100% | 92% | 4.8 | 3.6 |
| llama3 | noctx | 12 | 100% | 92% | 4.4 | 3.8 |
| mistral | ctx | 12 | 100% | 83% | 8.7 | 4.6 |
| mistral | noctx | 12 | 100% | 58% | 8.5 | 4.4 |
| qwen2.5:7b | ctx | 12 | 100% | 100% | 5.4 | 3.8 |
| qwen2.5:7b | noctx | 12 | 100% | 75% | 4.4 | 3.8 |
