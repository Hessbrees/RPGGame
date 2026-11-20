from dataclasses import dataclass, field

# Wspólny blok stylu – dołączany do każdego promptu, aby obrazy z jednej sesji były spójne.
# Opis odpowiada stylowi zbioru treningowego LoRA, więc porównanie base vs LoRA jest uczciwe.
STYLE_PREFIX = "realistic fantasy digital art, concept art, dramatic lighting, highly detailed"

# Token aktywujący LoRA stylu (musi być taki sam jak --trigger w scripts.prepare_dataset).
STYLE_TRIGGER = "rpgstyle"

# Wspólny negatywny prompt.
NEGATIVE_PROMPT = (
    "blurry, low quality, deformed, extra limbs, extra fingers, bad anatomy, "
    "text, watermark, signature, cropped, out of frame, modern clothing"
)


@dataclass
class CharacterSheet:
    """Stały opis wizualny postaci (po angielsku – modele dyfuzyjne są trenowane na angielskich opisach)."""

    name: str
    appearance: str
    trigger_token: str = ""          # token aktywujący LoRA postaci (pusty, jeśli brak LoRA)
    aliases: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(n.lower() in text_lower for n in [self.name, *self.aliases])

    def render(self, use_trigger: bool = True) -> str:
        token = f"{self.trigger_token} " if (use_trigger and self.trigger_token) else ""
        return f"{token}{self.appearance}"


DEFAULT_SHEETS: dict[str, CharacterSheet] = {
    "Arin": CharacterSheet(
        name="Arin",
        appearance="a lean young thief, dark hooded cloak, short black hair, sharp green eyes, leather armor, twin daggers",
    ),
    "Theron": CharacterSheet(
        name="Theron",
        appearance="a broad-shouldered veteran warrior, silver-trimmed plate armor, short brown beard, scarred face, longsword and shield",
    ),
}


def sheet_for(name: str, persona: dict | None = None) -> CharacterSheet:
    """Zwraca kartę postaci; dla nieznanej postaci buduje opis z persony."""
    if name in DEFAULT_SHEETS:
        return DEFAULT_SHEETS[name]
    persona = persona or {}
    char_class = persona.get("class", "adventurer")
    return CharacterSheet(name=name, appearance=f"a {char_class}, fantasy adventurer")


def state_modifiers(hp: int, max_hp: int = 100) -> str:
    """Dynamiczne modyfikatory wyglądu zależne od stanu gry (HP)."""
    ratio = hp / max_hp if max_hp else 1.0
    if ratio <= 0.25:
        return "severely wounded, bloodied, exhausted"
    if ratio <= 0.6:
        return "wounded, torn clothes"
    return ""
