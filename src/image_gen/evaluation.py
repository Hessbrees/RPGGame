"""
Metryki oceny wygenerowanych obrazów.

- CLIP Score (obraz <-> tekst): zgodność ilustracji z opisem sceny, 100 * max(cos, 0).
- CLIP-I / DINO-I (obraz <-> obraz): średnie podobieństwo kosinusowe obrazów tej samej postaci.
  Służy do pomiaru spójności postaci między scenami (DINOv2 jest czulszy na identyczność obiektu).
"""
import itertools
import random
import statistics

from .config import CLIP_MODEL_ID, DINO_MODEL_ID


def _as_tensor(features):
    """transformers >= 5 zwraca z get_*_features obiekt (pooler_output = rzutowane cechy), starsze - tensor."""
    return features if hasattr(features, "norm") else features.pooler_output


class ImageEvaluator:
    def __init__(self, clip_id: str = CLIP_MODEL_ID, dino_id: str = DINO_MODEL_ID, device: str | None = None):
        import torch

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.clip_id = clip_id
        self.dino_id = dino_id
        self._clip = None
        self._dino = None

    # ------------------------------------------------------------------
    def _load_clip(self):
        if self._clip is None:
            from transformers import CLIPModel, CLIPProcessor

            model = CLIPModel.from_pretrained(self.clip_id).to(self.device).eval()
            self._clip = (model, CLIPProcessor.from_pretrained(self.clip_id))
        return self._clip

    def _load_dino(self):
        if self._dino is None:
            from transformers import AutoImageProcessor, AutoModel

            model = AutoModel.from_pretrained(self.dino_id).to(self.device).eval()
            self._dino = (model, AutoImageProcessor.from_pretrained(self.dino_id))
        return self._dino

    def free(self) -> None:
        self._clip = None
        self._dino = None
        if self.device == "cuda":
            self.torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    def clip_score(self, images: list, texts: list[str]) -> list[float]:
        """CLIP Score dla par (obraz, tekst). Teksty dłuższe niż 77 tokenów są ucinane."""
        torch = self.torch
        model, processor = self._load_clip()
        inputs = processor(
            text=texts, images=images, return_tensors="pt", padding=True, truncation=True, max_length=77
        ).to(self.device)
        with torch.no_grad():
            img = torch.nn.functional.normalize(
                _as_tensor(model.get_image_features(pixel_values=inputs["pixel_values"])), dim=-1)
            txt = torch.nn.functional.normalize(
                _as_tensor(model.get_text_features(
                    input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"])),
                dim=-1,
            )
        cos = (img * txt).sum(dim=-1)
        return [100.0 * max(float(c), 0.0) for c in cos]

    def embeddings(self, images: list, backbone: str = "dino"):
        """Znormalizowane osadzenia obrazów (backbone: 'clip' lub 'dino')."""
        torch = self.torch
        with torch.no_grad():
            if backbone == "clip":
                model, processor = self._load_clip()
                pixel = processor(images=images, return_tensors="pt")["pixel_values"].to(self.device)
                feats = _as_tensor(model.get_image_features(pixel_values=pixel))
            else:
                model, processor = self._load_dino()
                pixel = processor(images=images, return_tensors="pt")["pixel_values"].to(self.device)
                feats = model(pixel_values=pixel).pooler_output
        return torch.nn.functional.normalize(feats, dim=-1)

    def style_centroid(self, reference_images: list, batch: int = 16):
        """Znormalizowany środek osadzeń CLIP obrazów referencyjnych (opis stylu zbioru treningowego)."""
        embs = [self.embeddings(reference_images[i:i + batch], "clip").cpu()
                for i in range(0, len(reference_images), batch)]
        centroid = self.torch.cat(embs).mean(dim=0)
        return self.torch.nn.functional.normalize(centroid, dim=-1)

    def style_scores(self, images: list, centroid) -> list[float]:
        """Podobieństwo kosinusowe osadzeń CLIP obrazów do środka stylu (wyżej = bliżej stylu referencyjnego)."""
        emb = self.embeddings(images, "clip").cpu()
        return [float(v) for v in emb @ centroid]

    def consistency(self, images: list, backbone: str = "dino") -> float | None:
        """Średnie podobieństwo parami obrazów tej samej postaci (None, gdy mniej niż 2 obrazy)."""
        if len(images) < 2:
            return None
        emb = self.embeddings(images, backbone)
        sims = [float(emb[i] @ emb[j]) for i, j in itertools.combinations(range(len(images)), 2)]
        return sum(sims) / len(sims)


# ----------------------------------------------------------------------
# Statystyka opisowa i porównania warunków eksperymentu
# ----------------------------------------------------------------------

def summarize(values: list[float], n_boot: int = 2000, seed: int = 0) -> dict:
    """Średnia, odchylenie standardowe i 95% przedział ufności (bootstrap)."""
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "mean": None, "std": None, "ci95": None}
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(n_boot))
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "ci95": [means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]],
    }


def paired_difference(a: list[float], b: list[float], n_boot: int = 2000, seed: int = 0) -> dict:
    """
    Sparowana różnica A - B (te same sceny i seedy) z 95% CI z bootstrapu.
    Jeśli przedział nie zawiera 0, różnica jest istotna na poziomie ~5%.
    """
    diffs = [x - y for x, y in zip(a, b)]
    stats = summarize(diffs, n_boot, seed)
    stats["significant"] = bool(stats["ci95"]) and (stats["ci95"][0] > 0 or stats["ci95"][1] < 0)
    return stats
