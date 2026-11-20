from .character_sheets import (
    NEGATIVE_PROMPT,
    STYLE_PREFIX,
    STYLE_TRIGGER,
    CharacterSheet,
    sheet_for,
    state_modifiers,
)
from .scene_director import SceneSpec

# Limit tokenizatora CLIP (bez tokenów specjalnych).
CLIP_MAX_TOKENS = 75
# Rezerwa na separator ", " między opisem sceny a blokiem stylu i na niedokładność dekodowania.
SAFETY_TOKENS = 3


class PromptBuilder:
    """
    Składa końcowy prompt dla modelu dyfuzyjnego z trzech źródeł:
    1) opis sceny, 2) karty postaci (+ modyfikatory ze stanu gry), 3) stały blok stylu.
    Blok stylu ma zarezerwowany budżet tokenów, a ucinany jest tylko opis sceny, więc styl
    jest zawsze obecny, a to warunek spójności obrazów w sesji.
    """

    def __init__(self, style_prefix: str = STYLE_PREFIX, negative: str = NEGATIVE_PROMPT,
                 use_character_sheets: bool = True, use_triggers: bool = True, tokenizer=None):
        self.style_prefix = style_prefix
        self.negative = negative
        self.use_character_sheets = use_character_sheets
        self.use_triggers = use_triggers
        self.tokenizer = tokenizer

    def build(self, scene: SceneSpec, player_states: list | None = None) -> tuple[str, str]:
        """Zwraca (prompt, negative_prompt)."""
        player_states = player_states or []
        by_name = {p.name: p for p in player_states}

        parts: list[str] = [scene.action] if scene.action else []

        if self.use_character_sheets:
            for name in scene.characters_present:
                state = by_name.get(name)
                sheet: CharacterSheet = sheet_for(name, state.persona if state else None)
                piece = sheet.render(use_trigger=self.use_triggers)
                if state:
                    modifier = state_modifiers(state.hp)
                    if modifier:
                        piece += f", {modifier}"
                parts.append(piece)

        parts += [scene.location, scene.time_of_day, scene.lighting, f"{scene.mood} atmosphere"]

        style = f"{STYLE_TRIGGER}, {self.style_prefix}" if self.use_triggers else self.style_prefix
        scene_prompt = ", ".join(p.strip(" ,.") for p in parts if p and p.strip())
        budget = max(CLIP_MAX_TOKENS - self._count(style) - SAFETY_TOKENS, 10)
        scene_prompt = self._truncate(scene_prompt, budget)
        return f"{scene_prompt}, {style}", self.negative

    def build_raw(self, text: str) -> tuple[str, str]:
        """Prompt bez udziału LLM i kart postaci (baseline): surowy tekst + blok stylu."""
        style = f"{STYLE_TRIGGER}, {self.style_prefix}" if self.use_triggers else self.style_prefix
        budget = max(CLIP_MAX_TOKENS - self._count(style) - SAFETY_TOKENS, 10)
        return f"{self._truncate(text.strip(' ,.'), budget)}, {style}", self.negative

    def _count(self, text: str) -> int:
        if self.tokenizer is not None:
            return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])
        # Szacunek bez tokenizatora: ~1.3 tokenu na słowo.
        return int(len(text.split()) * 1.3) + 1

    def _truncate(self, text: str, max_tokens: int) -> str:
        if self._count(text) <= max_tokens:
            return text
        if self.tokenizer is not None:
            ids = self.tokenizer(text, add_special_tokens=False)["input_ids"]
            return self.tokenizer.decode(ids[:max_tokens]).strip(" ,")
        return " ".join(text.split()[: int(max_tokens / 1.3)]).strip(" ,")
