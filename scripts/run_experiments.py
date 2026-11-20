"""
Eksperyment porównawczy: jakość i spójność ilustracji generowanych z opisu wydarzeń.

Czynniki (każda kombinacja jest oceniana na tych samych scenach i seedach -> porównania sparowane):
  - llm      : model piszący opis sceny (SceneDirector) lub "naive" (surowy polski tekst, bez LLM),
  - context  : "ctx" (kontekst lore z RAG + karty postaci) vs "noctx" (sam opis zdarzeń),
  - variant  : "base" (SD 1.5) vs "lora" (SD 1.5 + LoRA stylu, z tokenem aktywującym).

Metryki:
  - CLIP Score obrazu względem niezależnego opisu referencyjnego (`reference_en` w scenes.json),
  - spójność postaci (DINOv2-I i CLIP-I) między scenami z jedną postacią,
  - jakość specyfikacji sceny: poprawność JSON, zgodność listy postaci, opóźnienie LLM.
Różnice warunków: bootstrap sparowany po scenach (95% CI); różnica istotna, gdy CI nie zawiera 0.

Fazy (każda wznawialna - istniejące wyniki są pomijane; Ollama i model dyfuzyjny nie dzielą VRAM):
  specs  - LLM-y generują specyfikacje scen (po każdym modelu Ollama jest zwalniana),
  render - generowanie obrazów (najpierw wariant base, potem lora),
  eval   - metryki, statystyki, tabele i siatka porównawcza.

Przykład:
  .\\.venv\\Scripts\\python.exe -m scripts.run_experiments --out outputs/experiments/main
  .\\.venv\\Scripts\\python.exe -m scripts.run_experiments --phase specs --llm-models llama3 --limit 3 --out outputs/experiments/_try
"""
import argparse
import csv
import json
import os
import platform
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from src.image_gen.config import SD15_MODEL_ID, ImageGenConfig
from src.image_gen.evaluation import paired_difference, summarize
from src.image_gen.prompt_builder import PromptBuilder
from src.image_gen.scene_director import JSON_BLOCK, SceneDirector, SceneSpec

load_dotenv()

CTX_LEVELS = ("ctx", "noctx")
VARIANTS = ("base", "lora")
FACTORS = ("llm", "ctx", "variant")
PLAYER_NAMES = ["Arin", "Theron"]  # gracze znani dyrektorowi sceny (tak jak w grze)
NAIVE = "naive"


def log(msg: str) -> None:
    print(msg, flush=True)


def safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name)


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm-models", nargs="+", default=["llama3", "qwen2.5:7b", "mistral"])
    p.add_argument("--skip-naive", action="store_true", help="Pomiń baseline bez LLM (surowy tekst).")
    p.add_argument("--scenes", default="data/evaluation/scenes.json")
    p.add_argument("--limit", type=int, default=None, help="Tylko pierwsze N scen (do prób).")
    p.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    p.add_argument("--lora", default="outputs/lora/style_r16/best", help="Katalog z wagami LoRA.")
    p.add_argument("--lora-scale", type=float, default=0.8)
    p.add_argument("--image-model", default=SD15_MODEL_ID)
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--guidance", type=float, default=7.0)
    p.add_argument("--out", default="outputs/experiments/main")
    p.add_argument("--style-ref", default="data/training/style",
                   help="Katalog z obrazami stylu (metadata.jsonl) - wzorzec dla metryki wierności stylu.")
    p.add_argument("--phase", choices=["specs", "render", "eval", "all"], default="all")
    p.add_argument("--ollama-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    p.add_argument("--embed-model", default=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"))
    p.add_argument("--llm-temperature", type=float, default=0.2)
    return p.parse_args()


# ----------------------------------------------------------------------
# Faza 1: kontekst lore i specyfikacje scen
# ----------------------------------------------------------------------
class Recorder:
    """Opakowanie LLM zapamiętujące surową odpowiedź (do oceny poprawności JSON)."""

    def __init__(self, llm):
        self.llm = llm
        self.raw = ""

    def complete(self, prompt):
        out = self.llm.complete(prompt)
        self.raw = str(out)
        return out


def build_lore_cache(args, scenes: list[dict], out: Path) -> dict[str, str]:
    """Kontekst lore dla każdej sceny: top-2 fragmenty z RAG (bez syntezy LLM, więc identyczny dla wszystkich modeli)."""
    path = out / "lore_context.json"
    cache = read_json(path, {})
    todo = [s for s in scenes if s["id"] not in cache]
    if not todo:
        return cache

    import chromadb
    from llama_index.core import VectorStoreIndex
    from llama_index.embeddings.ollama import OllamaEmbedding
    from llama_index.vector_stores.chroma import ChromaVectorStore

    from src.rags.lore_rag import LoreRAG

    embed = OllamaEmbedding(model_name=args.embed_model, base_url=args.ollama_url)
    client = chromadb.PersistentClient(path=os.getenv("CHROMA_DB_PATH", "./chroma_db"))
    collection = client.get_or_create_collection(LoreRAG.COLLECTION_NAME)
    if collection.count() == 0:
        log("Kolekcja lore jest pusta - buduję indeks z data/lore ...")
        LoreRAG(llm=None, embed_model=embed)
    index = VectorStoreIndex.from_vector_store(ChromaVectorStore(chroma_collection=collection), embed_model=embed)
    retriever = index.as_retriever(similarity_top_k=2)
    for s in todo:
        nodes = retriever.retrieve(s["text_pl"][:300])
        cache[s["id"]] = "\n".join(n.get_content() for n in nodes)
    write_json(path, cache)
    log(f"Kontekst lore: {len(todo)} scen")
    return cache


def phase_specs(args, scenes: list[dict], out: Path) -> None:
    from llama_index.llms.ollama import Ollama

    from src.image_gen.image_generator import release_ollama

    lore = build_lore_cache(args, scenes, out)
    path = out / "specs.json"
    specs = read_json(path, {})

    for model in args.llm_models:
        todo = [(ctx, s) for ctx in CTX_LEVELS for s in scenes if s["id"] not in specs.get(f"{model}|{ctx}", {})]
        if not todo:
            log(f"[specs] {model}: komplet")
            continue
        log(f"[specs] {model}: {len(todo)} scen do opisania")
        recorder = Recorder(Ollama(model=model, base_url=args.ollama_url, request_timeout=300.0,
                                   temperature=args.llm_temperature))
        director = SceneDirector(recorder)
        recorder.llm.complete("Say OK.")  # rozgrzewka: ładowanie modelu nie zawyża pomiaru opóźnienia
        for i, (ctx, s) in enumerate(todo, 1):
            t0 = time.time()
            spec = director.analyze([s["text_pl"]], PLAYER_NAMES, lore[s["id"]] if ctx == "ctx" else "")
            latency = time.time() - t0
            match = JSON_BLOCK.search(recorder.raw)
            try:
                valid = bool(match) and isinstance(json.loads(match.group(0)), dict)
            except json.JSONDecodeError:
                valid = False
            specs.setdefault(f"{model}|{ctx}", {})[s["id"]] = {
                "spec": spec.to_dict(), "valid_json": valid, "latency_s": round(latency, 2), "raw": recorder.raw,
            }
            write_json(path, specs)
            log(f"  [{i}/{len(todo)}] {model} {ctx} {s['id']} valid={valid} {latency:.1f}s")
        release_ollama(args.ollama_url, model)


# ----------------------------------------------------------------------
# Plan zadań renderowania (deterministyczny na podstawie scen i specyfikacji)
# ----------------------------------------------------------------------
def build_jobs(args, scenes: list[dict], specs: dict) -> list[dict]:
    from transformers import CLIPTokenizer

    tokenizer = CLIPTokenizer.from_pretrained(args.image_model, subfolder="tokenizer")
    jobs: list[dict] = []

    def add(llm, ctx, variant, scene, prompt, negative):
        for seed in args.seeds:
            rel = Path("images") / safe(llm) / ctx / variant / f"{scene['id']}_s{seed}.png"
            jobs.append({"llm": llm, "ctx": ctx, "variant": variant, "scene": scene["id"], "seed": seed,
                         "prompt": prompt, "negative": negative, "path": rel.as_posix()})

    for variant in VARIANTS:
        triggers = variant == "lora"
        if not args.skip_naive:
            builder = PromptBuilder(use_character_sheets=False, use_triggers=triggers, tokenizer=tokenizer)
            for s in scenes:
                prompt, negative = builder.build_raw(s["text_pl"])
                add(NAIVE, "noctx", variant, s, prompt, negative)
        for model in args.llm_models:
            for ctx in CTX_LEVELS:
                builder = PromptBuilder(use_character_sheets=ctx == "ctx", use_triggers=triggers, tokenizer=tokenizer)
                for s in scenes:
                    entry = specs.get(f"{model}|{ctx}", {}).get(s["id"])
                    if entry is None:
                        continue
                    prompt, negative = builder.build(SceneSpec(**entry["spec"]))
                    add(model, ctx, variant, s, prompt, negative)
    return jobs


def load_specs_or_fail(out: Path) -> dict:
    specs = read_json(out / "specs.json", None)
    if specs is None:
        sys.exit("Brak specs.json - uruchom najpierw fazę 'specs'.")
    return specs


# ----------------------------------------------------------------------
# Faza 2: renderowanie
# ----------------------------------------------------------------------
def phase_render(args, scenes: list[dict], out: Path) -> None:
    from src.image_gen.image_generator import ImageGenerator, release_ollama

    jobs = build_jobs(args, scenes, load_specs_or_fail(out))
    write_json(out / "prompts.json", jobs)
    for model in args.llm_models:
        release_ollama(args.ollama_url, model)

    for variant in VARIANTS:
        todo = [j for j in jobs if j["variant"] == variant and not (out / j["path"]).exists()]
        log(f"[render] {variant}: {len(todo)} obrazów do wygenerowania (z {sum(j['variant'] == variant for j in jobs)})")
        if not todo:
            continue
        config = ImageGenConfig(
            mode="deferred", model_id=args.image_model,
            lora_paths=[args.lora] if variant == "lora" else [], lora_scale=args.lora_scale,
            steps=args.steps, guidance_scale=args.guidance,
        )
        generator = ImageGenerator(config)
        t0 = time.time()
        for i, j in enumerate(todo, 1):
            target = out / j["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            image = generator.generate(j["prompt"], j["negative"], seed=j["seed"])
            image.save(target)
            if i % 10 == 0 or i == len(todo):
                eta = (time.time() - t0) / i * (len(todo) - i)
                log(f"  {variant} {i}/{len(todo)} (pozostało ok. {eta / 60:.1f} min)")
        generator.unload()


# ----------------------------------------------------------------------
# Faza 3: ewaluacja
# ----------------------------------------------------------------------
def paired_scene_diff(rows: list[dict], factor: str, a: str, b: str, where=None, value: str = "clip") -> dict:
    """Różnica A - B dla par różniących się tylko poziomem `factor`; uśredniona po scenach, bootstrap po scenach."""
    idx: dict[tuple, dict] = defaultdict(dict)
    for r in rows:
        if where and not where(r):
            continue
        key = tuple(r[k] for k in FACTORS if k != factor) + (r["scene"], r["seed"])
        idx[key][r[factor]] = r[value]
    by_scene_a: dict[str, list] = defaultdict(list)
    by_scene_b: dict[str, list] = defaultdict(list)
    for key, levels in idx.items():
        if a in levels and b in levels:
            by_scene_a[key[-2]].append(levels[a])
            by_scene_b[key[-2]].append(levels[b])
    scene_ids = sorted(by_scene_a)
    if not scene_ids:
        return {"n": 0, "mean": None, "std": None, "ci95": None, "significant": False, "n_pairs": 0}
    result = paired_difference([statistics.fmean(by_scene_a[s]) for s in scene_ids],
                               [statistics.fmean(by_scene_b[s]) for s in scene_ids])
    result["n_pairs"] = sum(len(v) for v in by_scene_a.values())
    return result


def make_grid(out: Path, rows: list[dict], scenes: list[dict], llm: str, ctx: str, seed: int) -> Path | None:
    """Siatka: wiersze = sceny, kolumny = base | lora (ten sam LLM, kontekst i seed)."""
    from PIL import Image, ImageDraw

    thumb = 256
    chosen = scenes[:6]
    cols = [v for v in VARIANTS]
    canvas = Image.new("RGB", (thumb * len(cols), (thumb + 18) * len(chosen)), "white")
    draw = ImageDraw.Draw(canvas)
    found = False
    for r_i, s in enumerate(chosen):
        for c_i, variant in enumerate(cols):
            p = out / "images" / safe(llm) / ctx / variant / f"{s['id']}_s{seed}.png"
            if not p.exists():
                continue
            found = True
            canvas.paste(Image.open(p).convert("RGB").resize((thumb, thumb)), (c_i * thumb, r_i * (thumb + 18) + 18))
            draw.text((c_i * thumb + 4, r_i * (thumb + 18) + 3), f"{s['id']} {variant}", fill="black")
    if not found:
        return None
    path = out / f"comparison_{safe(llm)}_{ctx}_s{seed}.png"
    canvas.save(path)
    return path


def phase_eval(args, scenes: list[dict], out: Path) -> None:
    from PIL import Image

    from src.image_gen.evaluation import ImageEvaluator

    specs = load_specs_or_fail(out)
    # Prompty z fazy render (to one faktycznie wygenerowały obrazy); przebudowa tylko, gdy ich brak.
    planned = read_json(out / "prompts.json", None) or build_jobs(args, scenes, specs)
    jobs = [j for j in planned if (out / j["path"]).exists()]
    if not jobs:
        sys.exit("Brak obrazów - uruchom najpierw fazę 'render'.")
    ref = {s["id"]: s["reference_en"] for s in scenes}
    gt_chars = {s["id"]: s["characters"] for s in scenes}
    log(f"[eval] obrazów: {len(jobs)}")

    evaluator = ImageEvaluator()
    centroid = None
    meta = Path(args.style_ref) / "metadata.jsonl"
    if meta.exists():
        names = [json.loads(line)["file_name"] for line in meta.read_text(encoding="utf-8").splitlines() if line.strip()]
        centroid = evaluator.style_centroid([Image.open(Path(args.style_ref) / n).convert("RGB") for n in names])
        log(f"[eval] wzorzec stylu: {len(names)} obrazów")
    else:
        log(f"[eval] brak {meta} - pomijam metrykę stylu")
    rows: list[dict] = []
    batch = 16
    for i in range(0, len(jobs), batch):
        chunk = jobs[i:i + batch]
        images = [Image.open(out / j["path"]).convert("RGB") for j in chunk]
        scores = evaluator.clip_score(images, [ref[j["scene"]] for j in chunk])
        styles = evaluator.style_scores(images, centroid) if centroid is not None else [None] * len(chunk)
        for j, sc, st in zip(chunk, scores, styles):
            row = {"llm": j["llm"], "ctx": j["ctx"], "variant": j["variant"], "scene": j["scene"],
                   "seed": j["seed"], "clip": round(sc, 4)}
            if st is not None:
                row["style"] = round(st, 4)
            row.update(prompt=j["prompt"], image=j["path"])
            rows.append(row)
        log(f"  CLIP {min(i + batch, len(jobs))}/{len(jobs)}")

    with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # --- spójność postaci: obrazy scen z jedną postacią, grupowane per warunek i seed ---
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        chars = gt_chars[r["scene"]]
        if len(chars) == 1:
            groups[(r["llm"], r["ctx"], r["variant"], r["seed"], chars[0])].append(r["image"])
    cons_rows: list[dict] = []
    for (llm, ctx, variant, seed, char), paths in groups.items():
        if len(paths) < 2:
            continue
        images = [Image.open(out / p).convert("RGB") for p in paths]
        cons_rows.append({
            "llm": llm, "ctx": ctx, "variant": variant, "scene": f"{char}_s{seed}", "seed": 0, "character": char,
            "n_images": len(images),
            "dino": evaluator.consistency(images, "dino"), "clip_i": evaluator.consistency(images, "clip"),
        })
    if cons_rows:
        with open(out / "consistency.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cons_rows[0]))
            w.writeheader()
            w.writerows(cons_rows)
    evaluator.free()

    summary = summarize_results(rows, cons_rows, specs, scenes)
    summary["config"] = environment_info(args)
    write_json(out / "summary.json", summary)
    (out / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    if args.llm_models:
        for ctx in CTX_LEVELS:
            grid = make_grid(out, rows, scenes, args.llm_models[0], ctx, args.seeds[0])
            if grid:
                log(f"Siatka: {grid}")
    log(f"Gotowe: {out / 'summary.md'}")


def summarize_results(rows, cons_rows, specs, scenes) -> dict:
    # Warunki: średnia CLIP per scena (uśredniona po seedach), potem statystyka po scenach.
    per_cond: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per_cond[(r["llm"], r["ctx"], r["variant"])][r["scene"]].append(r["clip"])
    conditions = [
        {"llm": k[0], "ctx": k[1], "variant": k[2],
         **summarize([statistics.fmean(v) for v in by_scene.values()])}
        for k, by_scene in sorted(per_cond.items())
    ]

    llms = sorted({r["llm"] for r in rows})
    real_llms = [m for m in llms if m != NAIVE]
    comparisons = [{"name": "LoRA vs base (wszystkie)", **paired_scene_diff(rows, "variant", "lora", "base")},
                   {"name": "ctx vs noctx (wszystkie)", **paired_scene_diff(rows, "ctx", "ctx", "noctx")}]
    for m in llms:
        comparisons.append({"name": f"LoRA vs base ({m})",
                            **paired_scene_diff(rows, "variant", "lora", "base", where=lambda r, m=m: r["llm"] == m)})
    for m in real_llms:
        comparisons.append({"name": f"ctx vs noctx ({m})",
                            **paired_scene_diff(rows, "ctx", "ctx", "noctx", where=lambda r, m=m: r["llm"] == m)})
    for i, a in enumerate(llms):
        for b in llms[i + 1:]:
            comparisons.append({"name": f"{a} vs {b} (noctx+ctx dopasowane)",
                                **paired_scene_diff(rows, "llm", a, b, where=lambda r, a=a, b=b: r["llm"] in (a, b))})

    consistency = []
    for key in sorted({(r["llm"], r["ctx"], r["variant"]) for r in cons_rows}):
        sel = [r for r in cons_rows if (r["llm"], r["ctx"], r["variant"]) == key]
        consistency.append({"llm": key[0], "ctx": key[1], "variant": key[2],
                            "dino": summarize([r["dino"] for r in sel]),
                            "clip_i": summarize([r["clip_i"] for r in sel])})
    cons_comparisons = []
    for metric in ("dino", "clip_i"):
        cons_comparisons.append({"name": f"{metric}: LoRA vs base",
                                 **paired_scene_diff(cons_rows, "variant", "lora", "base", value=metric)})
        cons_comparisons.append({"name": f"{metric}: ctx vs noctx",
                                 **paired_scene_diff(cons_rows, "ctx", "ctx", "noctx", value=metric)})

    gt = {s["id"]: set(s["characters"]) for s in scenes}
    spec_quality = []
    for key, entries in sorted(specs.items()):
        entries = {k: v for k, v in entries.items() if k in gt}
        if not entries:
            continue
        llm, ctx = key.split("|")
        spec_quality.append({
            "llm": llm, "ctx": ctx, "n": len(entries),
            "valid_json_rate": statistics.fmean(e["valid_json"] for e in entries.values()),
            "characters_exact_rate": statistics.fmean(
                set(e["spec"]["characters_present"]) == gt[sid] for sid, e in entries.items()),
            "mean_latency_s": statistics.fmean(e["latency_s"] for e in entries.values()),
            "mean_importance": statistics.fmean(e["spec"]["importance"] for e in entries.values()),
        })
    return {"conditions": conditions, "comparisons": comparisons, "consistency": consistency,
            "consistency_comparisons": cons_comparisons, "spec_quality": spec_quality,
            **style_summary(rows, llms)}


def style_summary(rows: list[dict], llms: list[str]) -> dict:
    """Wierność stylu: podobieństwo CLIP do środka zbioru treningowego LoRA (oraz różnice sparowane)."""
    if not rows or "style" not in rows[0]:
        return {}
    per_cond: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per_cond[(r["llm"], r["ctx"], r["variant"])][r["scene"]].append(r["style"])
    conditions = [{"llm": k[0], "ctx": k[1], "variant": k[2],
                   **summarize([statistics.fmean(v) for v in by_scene.values()])}
                  for k, by_scene in sorted(per_cond.items())]
    comparisons = [{"name": "LoRA vs base (wszystkie)",
                    **paired_scene_diff(rows, "variant", "lora", "base", value="style")}]
    for m in llms:
        comparisons.append({"name": f"LoRA vs base ({m})", **paired_scene_diff(
            rows, "variant", "lora", "base", where=lambda r, m=m: r["llm"] == m, value="style")})
    return {"style_conditions": conditions, "style_comparisons": comparisons}


def _fmt_ci(d: dict) -> str:
    if d.get("mean") is None:
        return "brak danych"
    return f"{d['mean']:+.2f} [{d['ci95'][0]:+.2f}, {d['ci95'][1]:+.2f}]"


def render_markdown(s: dict) -> str:
    lines = ["# Wyniki eksperymentu", "",
             "## CLIP Score (obraz vs opis referencyjny; średnia po scenach, 95% CI)", "",
             "| LLM | kontekst | wariant | n scen | CLIP Score | 95% CI |", "|---|---|---|---|---|---|"]
    for c in s["conditions"]:
        lines.append(f"| {c['llm']} | {c['ctx']} | {c['variant']} | {c['n']} | {c['mean']:.2f} | "
                     f"[{c['ci95'][0]:.2f}, {c['ci95'][1]:.2f}] |")
    lines += ["", "## Porównania sparowane (różnica CLIP Score, bootstrap po scenach)", "",
              "| Porównanie | pary | różnica [95% CI] | istotne |", "|---|---|---|---|"]
    for c in s["comparisons"]:
        lines.append(f"| {c['name']} | {c['n_pairs']} | {_fmt_ci(c)} | {'tak' if c['significant'] else 'nie'} |")
    if s.get("style_conditions"):
        lines += ["", "## Wierność stylu (cos CLIP do środka zbioru treningowego LoRA; średnia po scenach, 95% CI)", "",
                  "| LLM | kontekst | wariant | podobieństwo | 95% CI |", "|---|---|---|---|---|"]
        for c in s["style_conditions"]:
            lines.append(f"| {c['llm']} | {c['ctx']} | {c['variant']} | {c['mean']:.4f} | "
                         f"[{c['ci95'][0]:.4f}, {c['ci95'][1]:.4f}] |")
        lines += ["", "| Porównanie stylu | pary | różnica [95% CI] | istotne |", "|---|---|---|---|"]
        for c in s["style_comparisons"]:
            ci = c["ci95"]
            text = "brak danych" if ci is None else f"{c['mean']:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]"
            lines.append(f"| {c['name']} | {c['n_pairs']} | {text} | {'tak' if c['significant'] else 'nie'} |")
    if s["consistency"]:
        lines += ["", "## Spójność postaci (średnie podobieństwo kosinusowe obrazów jednej postaci)", "",
                  "| LLM | kontekst | wariant | DINOv2-I | CLIP-I |", "|---|---|---|---|---|"]
        for c in s["consistency"]:
            lines.append(f"| {c['llm']} | {c['ctx']} | {c['variant']} | {c['dino']['mean']:.3f} | {c['clip_i']['mean']:.3f} |")
        lines += ["", "| Porównanie spójności | pary | różnica [95% CI] | istotne |", "|---|---|---|---|"]
        for c in s["consistency_comparisons"]:
            lines.append(f"| {c['name']} | {c['n_pairs']} | {_fmt_ci(c)} | "
                         f"{'tak' if c['significant'] else 'nie'} |")
    lines += ["", "## Jakość specyfikacji scen (SceneDirector)", "",
              "| LLM | kontekst | n | poprawny JSON | postacie zgodne | opóźnienie [s] | śr. ważność |",
              "|---|---|---|---|---|---|---|"]
    for q in s["spec_quality"]:
        lines.append(f"| {q['llm']} | {q['ctx']} | {q['n']} | {q['valid_json_rate']:.0%} | "
                     f"{q['characters_exact_rate']:.0%} | {q['mean_latency_s']:.1f} | {q['mean_importance']:.1f} |")
    return "\n".join(lines) + "\n"


def environment_info(args) -> dict:
    info = {"args": vars(args), "python": platform.python_version()}
    try:
        import diffusers
        import torch
        import transformers

        info.update(torch=torch.__version__, diffusers=diffusers.__version__, transformers=transformers.__version__)
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass
    return info


# ----------------------------------------------------------------------
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    scenes = json.loads(Path(args.scenes).read_text(encoding="utf-8"))
    if args.limit:
        scenes = scenes[: args.limit]
    write_json(out / "config.json", environment_info(args))

    if args.phase in ("specs", "all"):
        phase_specs(args, scenes, out)
    if args.phase in ("render", "all"):
        phase_render(args, scenes, out)
    if args.phase in ("eval", "all"):
        phase_eval(args, scenes, out)


if __name__ == "__main__":
    main()
