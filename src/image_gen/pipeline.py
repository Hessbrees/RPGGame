import logging
from dataclasses import dataclass
from pathlib import Path

from .config import ImageGenConfig
from .gallery import Gallery, ImageRecord
from .image_generator import ImageGenerator, release_ollama
from .prompt_builder import PromptBuilder
from .scene_director import SceneDirector, SceneSpec

logger = logging.getLogger(__name__)

# Kandydatami do ilustracji są tylko narracje GM; luźny dialog i same akcje pomijamy (oszczędność wywołań LLM).
ILLUSTRATABLE_TYPES = {"narration"}


@dataclass
class RenderJob:
    turn: int
    scene: SceneSpec
    prompt: str
    negative_prompt: str
    seed: int


class IllustrationPipeline:
    """
    Łączy cały tor: zdarzenie -> filtr ważności -> SceneDirector (LLM) -> PromptBuilder ->
    ImageGenerator -> Gallery.

    Tryby (patrz ImageGenConfig.mode):
    - inline:   obraz powstaje od razu po zdarzeniu (Ollama jest wyładowywana na czas generowania),
    - deferred: sceny trafiają do kolejki, a render następuje w flush() po zakończeniu sesji
                (LLM i model dyfuzyjny nigdy nie rywalizują o VRAM).
    """

    def __init__(self, llm, config: ImageGenConfig | None = None):
        self.config = config or ImageGenConfig()
        self.director = SceneDirector(llm)
        self.builder = PromptBuilder(use_triggers=bool(self.config.lora_paths))
        self.generator = ImageGenerator(self.config)
        self.gallery = Gallery(self.config.output_dir) if self.config.enabled else None
        self.queue: list[RenderJob] = []
        self._last_turn: int | None = None
        self._counter = len(self.gallery) if self.gallery else 0
        self._tokenizer_ready = False

    # ------------------------------------------------------------------
    def on_event(self, message: dict, game_state, events: list[str], lore_context: str = "") -> Path | None:
        """Wywoływane przez orkiestrator po każdej wiadomości na szynie komunikacyjnej."""
        if not self.config.enabled or message.get("type") not in ILLUSTRATABLE_TYPES:
            return None

        turn = message.get("turn", 0)
        if self._counter + len(self.queue) >= self.config.max_images:
            return None
        if self._last_turn is not None and turn - self._last_turn < self.config.min_turn_gap:
            return None

        names = [p.name for p in game_state.players]
        scene = self.director.analyze(events, names, lore_context)

        is_opening = self._last_turn is None and self._counter == 0
        if scene.importance < self.config.importance_threshold and not is_opening:
            logger.info("Pominięto scenę (ważność %d < %d)", scene.importance, self.config.importance_threshold)
            return None

        self._ensure_tokenizer()
        prompt, negative = self.builder.build(scene, game_state.players)
        job = RenderJob(turn, scene, prompt, negative, self.config.base_seed + self._counter + len(self.queue))
        self._last_turn = turn

        if self.config.mode == "deferred":
            self.queue.append(job)
            return None
        return self._render(job)

    def flush(self) -> list[Path]:
        """Renderuje zakolejkowane sceny (tryb deferred)."""
        paths = [self._render(job) for job in self.queue]
        self.queue.clear()
        return paths

    def close(self) -> Path | None:
        """Kończy sesję: renderuje zaległe sceny, zwalnia model i buduje galerię HTML."""
        if not self.config.enabled:
            return None
        self.flush()
        self.generator.unload()
        return self.gallery.build_html()

    # ------------------------------------------------------------------
    def _render(self, job: RenderJob) -> Path:
        if self.config.unload_ollama:
            release_ollama(self.config.ollama_base_url, self.config.ollama_model)

        image = self.generator.generate(job.prompt, job.negative_prompt, seed=job.seed)
        record = ImageRecord(
            index=self._counter,
            turn=job.turn,
            prompt=job.prompt,
            negative_prompt=job.negative_prompt,
            seed=job.seed,
            model_id=self.config.model_id,
            loras=list(self.config.lora_paths),
            scene=job.scene.to_dict(),
        )
        self._counter += 1
        path = self.gallery.save(image, record)
        logger.info("Zapisano ilustrację: %s", path)
        return path

    def _ensure_tokenizer(self) -> None:
        """Ładuje sam tokenizator CLIP (lekki) do dokładnego liczenia tokenów promptu."""
        if self._tokenizer_ready:
            return
        self._tokenizer_ready = True
        try:
            from transformers import CLIPTokenizer

            self.builder.tokenizer = CLIPTokenizer.from_pretrained(self.config.model_id, subfolder="tokenizer")
        except Exception as exc:
            logger.warning("Brak tokenizatora CLIP, używam szacunku: %s", exc)
