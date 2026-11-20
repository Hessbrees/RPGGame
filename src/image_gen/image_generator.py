import gc
import logging

from .config import ImageGenConfig

logger = logging.getLogger(__name__)


def release_ollama(base_url: str, model: str) -> None:
    """Wyładowuje model z Ollamy (keep_alive=0), aby zwolnić VRAM przed generowaniem obrazu."""
    try:
        import ollama

        ollama.Client(host=base_url).generate(model=model, prompt="", keep_alive=0)
    except Exception as exc:  # Ollama może nie być uruchomiona – to nie jest błąd krytyczny.
        logger.warning("Nie udało się zwolnić modelu Ollama: %s", exc)


class ImageGenerator:
    """
    Opakowanie na potok dyfuzyjny (diffusers) z obsługą adapterów LoRA.
    Model jest ładowany leniwie i może być zwolniony z pamięci (unload), żeby współdzielić
    6 GB VRAM z modelem językowym.
    """

    def __init__(self, config: ImageGenConfig):
        self.config = config
        self.pipe = None

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self.pipe is not None:
            return

        import torch
        from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler

        cuda = torch.cuda.is_available()
        dtype = torch.float16 if cuda else torch.float32

        pipe = AutoPipelineForText2Image.from_pretrained(self.config.model_id, dtype=dtype)
        if not self.config.is_turbo:
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

        adapter_names, adapter_weights = [], []
        for i, path in enumerate(self.config.lora_paths):
            name = f"lora_{i}"
            pipe.load_lora_weights(path, adapter_name=name)
            adapter_names.append(name)
            adapter_weights.append(self.config.lora_scale)
        if adapter_names:
            pipe.set_adapters(adapter_names, adapter_weights=adapter_weights)

        if cuda:
            pipe.enable_model_cpu_offload()
            pipe.vae.enable_slicing()
        pipe.set_progress_bar_config(disable=True)
        self.pipe = pipe

    def unload(self) -> None:
        """Zwalnia model i pamięć GPU."""
        self.pipe = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @property
    def tokenizer(self):
        self.load()
        return self.pipe.tokenizer

    # ------------------------------------------------------------------
    def generate(self, prompt: str, negative_prompt: str = "", seed: int | None = None):
        """Generuje pojedynczy obraz (PIL.Image). Ten sam seed i prompt dają ten sam wynik."""
        import torch

        self.load()
        seed = self.config.base_seed if seed is None else seed
        generator = torch.Generator(device="cpu").manual_seed(seed)

        kwargs = dict(
            prompt=prompt,
            width=self.config.width,
            height=self.config.height,
            num_inference_steps=self.config.effective_steps(),
            guidance_scale=self.config.effective_guidance(),
            generator=generator,
        )
        if not self.config.is_turbo:
            kwargs["negative_prompt"] = negative_prompt

        return self.pipe(**kwargs).images[0]
