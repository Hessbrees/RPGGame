from dataclasses import dataclass, field
from enum import Enum


class ConversationMode(str, Enum):
    FREE = "swobodna"       # Gracze rozmawiają swobodnie
    TURN_BASED = "turowa"   # Mistrz gry prowadzi konkretną scenę (walka, dialog, sprawdzenie)


class GameVibe(str, Enum):
    CHAOTIC = "chaotyczna"
    HARD = "trudna"
    CALM = "spokojna"
    BALANCED = "zrównoważona"


@dataclass
class PlayerState:
    """Stan pojedynczego gracza."""
    name: str
    persona: dict = field(default_factory=dict)
    hp: int = 100
    inventory: list = field(default_factory=list)
    active: bool = True


@dataclass
class GameState:
    """
    Zarządza stanem całej rozgrywki.
    Odpowiada za:
    - Śledzenie aktualnego stanu gry i tury.
    - Zarządzanie poziomem trudności (vibe).
    - Przechowywanie zmiennych wpływających na poziom trudności.
    - Ukrywanie informacji niedostępnych dla graczy.
    """

    scenario: str = ""
    vibe: GameVibe = GameVibe.BALANCED
    conversation_mode: ConversationMode = ConversationMode.FREE
    current_turn: int = 0
    players: list[PlayerState] = field(default_factory=list)
    active_npcs: list[dict] = field(default_factory=list)
    difficulty: float = 1.0          # mnożnik trudności (0.5 – łatwa, 2.0 – bardzo trudna)
    hidden_info: dict = field(default_factory=dict)   # info niedostępne dla graczy
    world_state: str = ""            # bieżący opis sytuacji w świecie

    def next_turn(self) -> None:
        """Przechodzi do następnej tury."""
        self.current_turn += 1

    def adjust_difficulty(self, delta: float) -> None:
        """Dynamicznie dostosowuje poziom trudności."""
        self.difficulty = max(0.1, self.difficulty + delta)

    def add_npc(self, npc: dict) -> None:
        """Dodaje NPC do świata."""
        self.active_npcs.append(npc)

    def remove_npc(self, npc_name: str) -> None:
        """Usuwa NPC ze świata."""
        self.active_npcs = [n for n in self.active_npcs if n.get("name") != npc_name]

    def set_hidden_info(self, key: str, value: str) -> None:
        """Zapisuje informację niedostępną dla graczy."""
        self.hidden_info[key] = value

    def describe_state(self) -> str:
        """Zwięzły opis stanu dla promptów (autorytatywny: liczony w kodzie, nie przez LLM)."""
        players = "; ".join(
            f"{p.name}: HP {p.hp}/100, {'aktywny' if p.active else 'nieprzytomny'}, "
            f"ekwipunek: {', '.join(p.inventory) or 'pusty'}"
            for p in self.players
        )
        return f"Tura {self.current_turn}; gracze: {players}"

    def get_public_state(self) -> dict:
        """Zwraca stan gry widoczny dla graczy (bez ukrytych informacji)."""
        return {
            "scenario": self.scenario,
            "vibe": self.vibe,
            "turn": self.current_turn,
            "difficulty": self.difficulty,
            "world_state": self.world_state,
            "active_npcs": [n.get("name") for n in self.active_npcs],
            "players": [
                {"name": p.name, "hp": p.hp, "active": p.active}
                for p in self.players
            ],
        }
