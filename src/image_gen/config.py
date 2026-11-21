import os
from dataclasses import dataclass, field


# Identyfikatory modeli na Hugging Face Hub.
SD15_MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-v1-5"
SD_TURBO_MODEL_ID = "stabilityai/sd-turbo"
CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
DINO_MODEL_ID = "facebook/dinov2-small"

# Modele destylowane (Turbo) nie używają classifier-free guidance.
TURBO_MARKERS = ("turbo", "lcm", "lightning")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ImageGenConfig:
    """Konfiguracja generowania ilustracji. Wartości domyślne pochodzą ze zmiennych środowiskowych."""

    # Tryb: "off" | "inline" (obraz zaraz po zdarzeniu) | "deferred" (kolejka, render po sesji)
    mode: str = field(default_factory=lambda: os.getenv("IMAGE_GEN_MODE", "off"))

    model_id: str = field(default_factory=lambda: os.getenv("IMAGE_MODEL_ID", SD15_MODEL_ID))
    lora_paths: list[str] = field(
        default_factory=lambda: [p for p in os.getenv("IMAGE_LORA_PATHS", "").split(";") if p]
    )
    lora_scale: float = field(default_factory=lambda: float(os.getenv("IMAGE_LORA_SCALE", "0.8")))

    width: int = 512
    height: int = 512
    steps: int = field(default_factory=lambda: int(os.getenv("IMAGE_STEPS", "25")))
    guidance_scale: float = field(default_factory=lambda: float(os.getenv("IMAGE_GUIDANCE", "7.0")))
    base_seed: int = field(default_factory=lambda: int(os.getenv("IMAGE_SEED", "42")))

    output_dir: str = field(default_factory=lambda: os.getenv("IMAGE_OUTPUT_DIR", "./outputs/images"))

    # Filtr ważności: obraz powstaje tylko dla scen o ocenie >= progu (skala 1-5).
    importance_threshold: int = field(default_factory=lambda: int(os.getenv("IMAGE_IMPORTANCE_THRESHOLD", "4")))
    min_turn_gap: int = 1  # minimalna liczba tur między kolejnymi obrazami
    max_images: int = field(default_factory=lambda: int(os.getenv("IMAGE_MAX_IMAGES", "20")))

    # Zwalnianie VRAM (6 GB): Ollama i model dyfuzyjny nie mogą być ładowane jednocześnie.
    unload_ollama: bool = field(default_factory=lambda: _env_bool("IMAGE_UNLOAD_OLLAMA", True))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    # Dodatkowe modele Ollama (np. osobny model GM/graczy), które też trzeba wyładować przed renderowaniem.
    ollama_extra_models: list[str] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.mode in {"inline", "deferred"}

    @property
    def is_turbo(self) -> bool:
        return any(marker in self.model_id.lower() for marker in TURBO_MARKERS)

    def effective_steps(self) -> int:
        return min(self.steps, 4) if self.is_turbo else self.steps

    def effective_guidance(self) -> float:
        return 0.0 if self.is_turbo else self.guidance_scale
