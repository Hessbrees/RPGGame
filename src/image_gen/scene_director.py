import json
import re
from dataclasses import dataclass, field, asdict

DIRECTOR_PROMPT = """You are a visual scene director for a fantasy RPG illustrator.
Read the game events (they are in Polish) and describe ONE key moment as an image brief.
Answer with a single JSON object and nothing else. All values must be in ENGLISH.

Required keys:
- "location": short visual description of the place (max 12 words)
- "characters_present": list of character names visible in the scene
- "action": what is happening visually, one sentence (max 20 words)
- "mood": 2-3 mood words
- "time_of_day": e.g. "night", "dusk", "dawn", "day"
- "lighting": e.g. "torchlight", "moonlight", "foggy daylight"
- "importance": integer 1-5, how visually significant and story-relevant this moment is
  (1 = idle talk, 3 = exploration, 5 = combat, discovery, death or climax)

Known player characters: {characters}
{context_block}
Game events:
{events}

JSON:"""

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class SceneSpec:
    """Ustrukturyzowany opis sceny przekazywany do PromptBuilder."""

    location: str = "dark forest"
    characters_present: list[str] = field(default_factory=list)
    action: str = ""
    mood: str = "tense"
    time_of_day: str = "night"
    lighting: str = "dim light"
    importance: int = 3
    source_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class SceneDirector:
    """
    Zamienia polskie zdarzenia z gry na ustrukturyzowany opis sceny (JSON) przy pomocy LLM.
    Wynik zawiera też ocenę ważności, która służy do filtrowania momentów wartych zilustrowania.
    """

    def __init__(self, llm):
        self.llm = llm

    def analyze(
        self,
        events: list[str],
        character_names: list[str],
        lore_context: str = "",
    ) -> SceneSpec:
        context_block = f"World lore (for visual details):\n{lore_context[:600]}\n" if lore_context else ""
        prompt = DIRECTOR_PROMPT.format(
            characters=", ".join(character_names) or "none",
            context_block=context_block,
            events="\n".join(events[-4:]),
        )
        raw = str(self.llm.complete(prompt))
        spec = self.parse(raw, character_names)
        spec.source_text = " ".join(events[-2:])
        return spec

    @staticmethod
    def parse(raw: str, character_names: list[str]) -> SceneSpec:
        """Odporny parser odpowiedzi LLM; przy błędzie zwraca scenę domyślną o średniej ważności."""
        data: dict = {}
        match = JSON_BLOCK.search(raw)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}

        def text(key: str, default: str) -> str:
            value = data.get(key, default)
            return str(value).strip() if value else default

        present = data.get("characters_present", [])
        if not isinstance(present, list):
            present = []
        # Zostawiamy tylko znane postacie graczy; pozostali (NPC) opisani są w "action".
        present = [n for n in character_names if any(n.lower() in str(p).lower() for p in present)]

        try:
            importance = max(1, min(5, int(data.get("importance", 3))))
        except (TypeError, ValueError):
            importance = 3

        return SceneSpec(
            location=text("location", "dark forest"),
            characters_present=present,
            action=text("action", ""),
            mood=text("mood", "tense"),
            time_of_day=text("time_of_day", "night"),
            lighting=text("lighting", "dim light"),
            importance=importance,
        )
