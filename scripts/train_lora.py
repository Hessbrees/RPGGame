"""
Trening LoRA (adaptacja UNet) dla Stable Diffusion 1.5 na zbiorze przygotowanym przez scripts.prepare_dataset.

Dostosowany do 6 GB VRAM:
  - UNet w fp16, trenowane tylko wagi LoRA (fp32) + mixed precision (autocast + GradScaler),
  - gradient checkpointing,
  - latenty VAE i osadzenia tekstu liczone raz i trzymane w pamięci (VAE i enkoder tekstu nie biorą udziału w treningu).

Co jest logowane (reprodukowalność i materiał do raportu):
  config.json        – hiperparametry, wersje bibliotek, liczebność zbioru
  train_log.csv      – loss, lr, norma gradientu
  eval_log.csv       – val loss (stałe t i szum), CLIP Score próbek walidacyjnych
  validation/        – obrazy walidacyjne ze stałymi seedami (krok 0 = model bazowy)
  best/ final/ checkpoint-N/ – wagi LoRA (best = najniższy val loss; ochrona przed przeuczeniem)

Przykład:
  python -m scripts.train_lora --data_dir data/training/style --output_dir outputs/lora/style_r16
"""
import argparse
import csv
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from src.image_gen.character_sheets import STYLE_TRIGGER
from src.image_gen.config import SD15_MODEL_ID

DEFAULT_VALIDATION_PROMPTS = [
    "a hooded thief sneaking between dark trees in a misty forest at night",
    "an armored knight fighting goblins in a torch-lit cave",
    "ancient elven ruins under moonlight, crumbling columns and ivy",
]
VAL_TIMESTEPS = [100, 300, 500, 700, 900]


def parse_args():
    p = argparse.ArgumentParser(description="Trening LoRA stylu dla SD 1.5")
    p.add_argument("--data_dir", required=True)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--base_model", default=SD15_MODEL_ID)
    p.add_argument("--resolution", type=int, default=512)
    p.add_argument("--rank", type=int, default=16)
    p.add_argument("--alpha", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--lr_scheduler", default="cosine")
    p.add_argument("--warmup_steps", type=int, default=50)
    p.add_argument("--max_steps", type=int, default=1000, help="Liczba kroków optymalizatora")
    p.add_argument("--batch_size", type=int, default=2)
    p.add_argument("--grad_accum", type=int, default=2)
    p.add_argument("--snr_gamma", type=float, default=None, help="Min-SNR weighting (np. 5.0); None = wyłączone")
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--eval_every", type=int, default=250)
    p.add_argument("--save_every", type=int, default=500)
    p.add_argument("--validation_prompt", action="append", default=None)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_rows(data_dir: Path) -> tuple[list[dict], list[dict]]:
    lines = (data_dir / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line]
    train = [r for r in rows if r.get("split", "train") == "train"]
    val = [r for r in rows if r.get("split") == "val"]
    return train, val


@torch.no_grad()
def encode_rows(rows: list[dict], data_dir: Path, vae, tokenizer, text_encoder, device) -> list[dict]:
    """Liczy raz: rozkład latentów obrazu (mean, std) i osadzenie tekstu."""
    cache = []
    for row in rows:
        image = Image.open(data_dir / row["file_name"]).convert("RGB")
        x = torch.from_numpy(np.asarray(image).copy()).permute(2, 0, 1).float() / 127.5 - 1.0
        dist = vae.encode(x.unsqueeze(0).to(device, torch.float16)).latent_dist
        ids = tokenizer(row["text"], padding="max_length", max_length=tokenizer.model_max_length,
                        truncation=True, return_tensors="pt").input_ids.to(device)
        emb = text_encoder(ids)[0]
        cache.append({"mean": dist.mean.cpu(), "std": dist.std.cpu(), "emb": emb.cpu()})
    return cache


def make_batch(cache: list[dict], idx: list[int], scaling: float, device, generator=None):
    mean = torch.cat([cache[i]["mean"] for i in idx]).to(device)
    std = torch.cat([cache[i]["std"] for i in idx]).to(device)
    emb = torch.cat([cache[i]["emb"] for i in idx]).to(device)
    noise = torch.randn(mean.shape, generator=generator, device="cpu").to(device, mean.dtype)
    return (mean + std * noise) * scaling, emb


def snr_weights(scheduler, timesteps, gamma: float):
    alphas = scheduler.alphas_cumprod.to(timesteps.device)[timesteps]
    snr = alphas / (1.0 - alphas)
    clipped = torch.minimum(snr, torch.full_like(snr, gamma))
    if scheduler.config.prediction_type == "v_prediction":
        return clipped / (snr + 1)
    return clipped / snr


def diffusion_loss(unet, scheduler, latents, emb, timesteps, noise, snr_gamma=None):
    noisy = scheduler.add_noise(latents, noise, timesteps)
    if scheduler.config.prediction_type == "v_prediction":
        target = scheduler.get_velocity(latents, noise, timesteps)
    else:
        target = noise
    with torch.autocast("cuda", dtype=torch.float16):
        pred = unet(noisy, timesteps, emb).sample
    loss = F.mse_loss(pred.float(), target.float(), reduction="none").mean(dim=[1, 2, 3])
    if snr_gamma:
        loss = loss * snr_weights(scheduler, timesteps, snr_gamma)
    return loss.mean()


@torch.no_grad()
def validation_loss(unet, scheduler, val_cache, scaling, device) -> float:
    """Val loss na stałych krokach t i stałym szumie – porównywalny między checkpointami."""
    if not val_cache:
        return float("nan")
    unet.eval()
    gen = torch.Generator(device="cpu").manual_seed(1234)
    losses = []
    for i in range(len(val_cache)):
        latents, emb = make_batch(val_cache, [i], scaling, device, generator=gen)
        for t in VAL_TIMESTEPS:
            noise = torch.randn(latents.shape, generator=gen, device="cpu").to(device, latents.dtype)
            ts = torch.tensor([t], device=device)
            losses.append(float(diffusion_loss(unet, scheduler, latents, emb, ts, noise)))
    unet.train()
    return sum(losses) / len(losses)


def save_lora(unet, path: Path) -> None:
    from diffusers import StableDiffusionPipeline
    from diffusers.utils import convert_state_dict_to_diffusers
    from peft.utils import get_peft_model_state_dict

    path.mkdir(parents=True, exist_ok=True)
    state = convert_state_dict_to_diffusers(get_peft_model_state_dict(unet))
    StableDiffusionPipeline.save_lora_weights(save_directory=str(path), unet_lora_layers=state, safe_serialization=True)


def build_pipeline(vae, text_encoder, tokenizer, unet, base_model):
    from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline

    scheduler = DPMSolverMultistepScheduler.from_pretrained(base_model, subfolder="scheduler")
    pipe = StableDiffusionPipeline(
        vae=vae, text_encoder=text_encoder, tokenizer=tokenizer, unet=unet, scheduler=scheduler,
        safety_checker=None, feature_extractor=None, requires_safety_checker=False,
    )
    pipe.set_progress_bar_config(disable=True)
    return pipe


@torch.no_grad()
def run_validation_images(pipe, prompts: list[str], step: int, out_dir: Path, evaluator, seed: int) -> float:
    """Generuje próbki ze stałymi seedami (z tokenem stylu i bez) oraz liczy średni CLIP Score."""
    pipe.unet.eval()
    out_dir.mkdir(parents=True, exist_ok=True)
    images, texts = [], []
    for i, prompt in enumerate(prompts):
        for tag, full in (("trigger", f"{STYLE_TRIGGER}, {prompt}"), ("plain", prompt)):
            gen = torch.Generator(device="cpu").manual_seed(seed + i)
            with torch.autocast("cuda", dtype=torch.float16):
                image = pipe(full, num_inference_steps=25, guidance_scale=7.0, generator=gen).images[0]
            image.save(out_dir / f"step{step:05d}_p{i}_{tag}.png")
            images.append(image)
            texts.append(prompt)
    pipe.unet.train()
    return float(np.mean(evaluator.clip_score(images, texts)))


def plot_curves(out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    def read(name):
        with open(out_dir / name, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    train, ev = read("train_log.csv"), read("eval_log.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    steps = [int(r["step"]) for r in train]
    loss = np.array([float(r["loss"]) for r in train])
    axes[0].plot(steps, loss, alpha=0.3, label="train loss")
    if len(loss) >= 20:
        axes[0].plot(steps[19:], np.convolve(loss, np.ones(20) / 20, mode="valid"), label="train loss (średnia 20)")
    axes[0].plot([int(r["step"]) for r in ev], [float(r["val_loss"]) for r in ev], "o-", label="val loss")
    axes[0].set_xlabel("krok"), axes[0].set_ylabel("MSE"), axes[0].legend()
    axes[1].plot([int(r["step"]) for r in ev], [float(r["clip_score"]) for r in ev], "o-")
    axes[1].set_xlabel("krok"), axes[1].set_ylabel("CLIP Score (próbki walidacyjne)")
    fig.tight_layout()
    fig.savefig(out_dir / "curves.png", dpi=150)


def main():
    args = parse_args()
    assert torch.cuda.is_available(), "Trening wymaga GPU z CUDA"
    set_seed(args.seed)
    device = torch.device("cuda")
    data_dir, out_dir = Path(args.data_dir), Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = args.validation_prompt or DEFAULT_VALIDATION_PROMPTS

    import diffusers
    import peft
    import transformers
    from diffusers import AutoencoderKL, DDPMScheduler, UNet2DConditionModel
    from diffusers.optimization import get_scheduler
    from peft import LoraConfig
    from transformers import CLIPTextModel, CLIPTokenizer

    from src.image_gen.evaluation import ImageEvaluator

    tokenizer = CLIPTokenizer.from_pretrained(args.base_model, subfolder="tokenizer")
    text_encoder = CLIPTextModel.from_pretrained(
        args.base_model, subfolder="text_encoder", dtype=torch.float16).to(device)
    vae = AutoencoderKL.from_pretrained(args.base_model, subfolder="vae", torch_dtype=torch.float16).to(device)
    unet = UNet2DConditionModel.from_pretrained(
        args.base_model, subfolder="unet", torch_dtype=torch.float16).to(device)
    noise_scheduler = DDPMScheduler.from_pretrained(args.base_model, subfolder="scheduler")
    for module in (text_encoder, vae, unet):
        module.requires_grad_(False)
    text_encoder.eval()
    vae.eval()

    train_rows, val_rows = load_rows(data_dir)
    scaling = vae.config.scaling_factor
    print(f"Zbiór: train={len(train_rows)}, val={len(val_rows)}. Liczenie cache latentów...")
    train_cache = encode_rows(train_rows, data_dir, vae, tokenizer, text_encoder, device)
    val_cache = encode_rows(val_rows, data_dir, vae, tokenizer, text_encoder, device)

    unet.add_adapter(LoraConfig(
        r=args.rank, lora_alpha=args.alpha, init_lora_weights="gaussian",
        target_modules=["to_k", "to_q", "to_v", "to_out.0"],
    ))
    params = [p for p in unet.parameters() if p.requires_grad]
    for p in params:
        p.data = p.data.float()
    n_params = sum(p.numel() for p in params)
    print(f"Trenowalne parametry LoRA: {n_params / 1e6:.2f} M")
    unet.enable_gradient_checkpointing()
    unet.train()

    optimizer = torch.optim.AdamW(params, lr=args.lr, weight_decay=1e-2)
    lr_scheduler = get_scheduler(args.lr_scheduler, optimizer=optimizer,
                                 num_warmup_steps=args.warmup_steps, num_training_steps=args.max_steps)
    scaler = torch.amp.GradScaler("cuda")

    (out_dir / "config.json").write_text(json.dumps({
        "args": vars(args),
        "versions": {"torch": torch.__version__, "diffusers": diffusers.__version__,
                     "transformers": transformers.__version__, "peft": peft.__version__},
        "dataset": {"train": len(train_rows), "val": len(val_rows)},
        "trainable_params": n_params,
        "effective_batch": args.batch_size * args.grad_accum,
    }, indent=2), encoding="utf-8")

    evaluator = ImageEvaluator(device="cpu")
    pipe = build_pipeline(vae, text_encoder, tokenizer, unet, args.base_model)

    train_f = open(out_dir / "train_log.csv", "w", newline="", encoding="utf-8")
    eval_f = open(out_dir / "eval_log.csv", "w", newline="", encoding="utf-8")
    train_log, eval_log = csv.writer(train_f), csv.writer(eval_f)
    train_log.writerow(["step", "loss", "lr", "grad_norm"])
    eval_log.writerow(["step", "val_loss", "clip_score"])

    def evaluate(step: int, best: dict) -> None:
        val = validation_loss(unet, noise_scheduler, val_cache, scaling, device)
        clip = run_validation_images(pipe, prompts, step, out_dir / "validation", evaluator, args.seed)
        eval_log.writerow([step, f"{val:.5f}", f"{clip:.3f}"])
        eval_f.flush()
        print(f"[eval] step={step} val_loss={val:.5f} clip_score={clip:.2f}")
        if val == val and val < best["loss"]:  # val == val odrzuca NaN
            best["loss"] = val
            save_lora(unet, out_dir / "best")

    best = {"loss": float("inf")}
    evaluate(0, best)  # krok 0 = model bazowy (LoRA ma zerowy wkład na starcie)

    order: list[int] = []
    window: list[float] = []
    start = time.time()
    for step in range(1, args.max_steps + 1):
        step_loss = 0.0
        for _ in range(args.grad_accum):
            idx = []
            while len(idx) < args.batch_size:
                if not order:
                    order = random.sample(range(len(train_cache)), len(train_cache))
                idx.append(order.pop())
            latents, emb = make_batch(train_cache, idx, scaling, device)
            noise = torch.randn_like(latents)
            ts = torch.randint(0, noise_scheduler.config.num_train_timesteps, (latents.shape[0],), device=device)
            loss = diffusion_loss(unet, noise_scheduler, latents, emb, ts, noise, args.snr_gamma)
            scaler.scale(loss / args.grad_accum).backward()
            step_loss += loss.item() / args.grad_accum

        scaler.unscale_(optimizer)
        grad_norm = float(torch.nn.utils.clip_grad_norm_(params, args.max_grad_norm))
        scaler.step(optimizer)
        scaler.update()
        lr_scheduler.step()
        optimizer.zero_grad(set_to_none=True)

        window = (window + [step_loss])[-20:]
        train_log.writerow([step, f"{step_loss:.5f}", f"{lr_scheduler.get_last_lr()[0]:.3e}", f"{grad_norm:.3f}"])
        if step % 10 == 0:
            train_f.flush()
            print(f"step {step}/{args.max_steps} loss(avg20)={np.mean(window):.4f} "
                  f"lr={lr_scheduler.get_last_lr()[0]:.2e} {(time.time() - start) / step:.1f}s/step")
        if step % args.eval_every == 0 or step == args.max_steps:
            evaluate(step, best)
        if step % args.save_every == 0 and step != args.max_steps:
            save_lora(unet, out_dir / f"checkpoint-{step}")

    save_lora(unet, out_dir / "final")
    train_f.close()
    eval_f.close()
    try:
        plot_curves(out_dir)
    except ImportError:
        print("Brak matplotlib – pomijam wykres krzywych uczenia.")
    print(f"Gotowe. Wagi: {out_dir / 'final'} (ostatni krok), {out_dir / 'best'} (najniższy val loss)")


if __name__ == "__main__":
    main()
