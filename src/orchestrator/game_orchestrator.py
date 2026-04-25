from src.rags.lore_rag import LoreRAG
from src.rags.npc_rag import NpcRAG
from src.rags.judge_rag import JudgeRAG
from src.rags.chronicle_rag import ChronicleRAG
from src.rags.reranker import Reranker
from src.agents.game_master_agent import GameMasterAgent
from src.game_state.game_state import GameState, GameVibe, ConversationMode


class GameOrchestrator:
    """
    Orkiestrator rozgrywki – główny kontroler sesji RPG.
    Odpowiada za:
    - Przetwarzanie akcji graczy i mistrza gry.
    - Zarządzanie stanem świata i turami.
    - Kierowanie zapytań do odpowiednich RAGów.
    - Wspólną szynę komunikacyjną między uczestnikami.
    """

    def __init__(self, llm, embed_model, vibe: str = "zrównoważona", scenario: str = ""):
        self.lore_rag = LoreRAG(llm=llm, embed_model=embed_model)
        self.npc_rag = NpcRAG(llm=llm, embed_model=embed_model)
        self.judge_rag = JudgeRAG(llm=llm, embed_model=embed_model)
        self.chronicle_rag = ChronicleRAG(llm=llm, embed_model=embed_model)
        self.reranker = Reranker(top_k=3)
        self.game_master = GameMasterAgent(llm=llm, vibe=vibe)
        self.game_state = GameState(
            scenario=scenario,
            vibe=GameVibe(vibe),
        )

    # ------------------------------------------------------------------
    # Akcje gracza
    # ------------------------------------------------------------------

    def process_player_action(self, action: str, player_name: str) -> str:
        """
        Przetwarza akcję gracza:
        1. Waliduje akcję przez Sędziego RAG (zasady).
        2. Rejestruje zdarzenie w Kronikarzу.
        3. Mistrz Gry reaguje i opisuje konsekwencje.
        """
        rules_context = self.judge_rag.query(f"Czy ta akcja jest zgodna z zasadami: {action}")
        state_summary = str(self.game_state.get_public_state())
        response = self.game_master.react_to_player_action(action, state_summary)
        self.chronicle_rag.add_entry(f"[Tura {self.game_state.current_turn}] {player_name}: {action}")
        self.chronicle_rag.add_entry(f"[GM]: {response}")
        return response

    def describe_situation(self, extra_context: str = "") -> str:
        """Mistrz Gry opisuje aktualną sytuację graczom."""
        state_summary = str(self.game_state.get_public_state())
        lore_context = self.lore_rag.query(self.game_state.world_state or "świat gry")
        full_context = f"{state_summary}\n{lore_context}\n{extra_context}"
        return self.game_master.narrate(self.game_state.world_state, full_context)

    # ------------------------------------------------------------------
    # Akcje mistrza gry
    # ------------------------------------------------------------------

    def add_npc(self, name: str, description: str) -> None:
        """Orkiestracja NPC – dodaje postać do świata."""
        self.game_state.add_npc({"name": name, "description": description})

    def remove_npc(self, name: str) -> None:
        """Usuwa NPC ze świata."""
        self.game_state.remove_npc(name)

    def next_turn(self) -> int:
        """Przechodzi do następnej tury."""
        self.game_state.next_turn()
        return self.game_state.current_turn

    def adjust_difficulty(self, delta: float) -> float:
        """Dynamicznie dostosowuje poziom trudności."""
        self.game_state.adjust_difficulty(delta)
        return self.game_state.difficulty

    # ------------------------------------------------------------------
    # RAG query routing
    # ------------------------------------------------------------------

    def query(self, question: str, context: str = "auto") -> str:
        """
        Wysyła zapytanie do odpowiedniego RAG na podstawie kontekstu.

        Args:
            question: Pytanie gracza lub zdarzenie w grze.
            context: 'lore' | 'npc' | 'rules' | 'chronicle' | 'auto'
        """
        if context == "auto":
            context = self._detect_context(question)

        if context == "lore":
            return self.lore_rag.query(question)
        elif context == "npc":
            return self.npc_rag.query(question)
        elif context == "rules":
            return self.judge_rag.query(question)
        elif context == "chronicle":
            return self.chronicle_rag.query(question)
        else:
            return "Nieznany kontekst. Użyj: 'lore', 'npc', 'rules' lub 'chronicle'."

    def _detect_context(self, question: str) -> str:
        """Heurystyka do wykrywania kontekstu na podstawie słów kluczowych."""
        question_lower = question.lower()
        rules_keywords = ["zasada", "walka", "atak", "combat", "bitwa", "obrona", "hp", "dmg", "rzut", "kostka"]
        npc_keywords = ["postać", "npc", "rozmowa", "dialog", "kupiec", "strażnik"]
        chronicle_keywords = ["historia", "poprzednio", "pamiętasz", "było", "wydarzyło", "przeszłość"]

        if any(kw in question_lower for kw in chronicle_keywords):
            return "chronicle"
        elif any(kw in question_lower for kw in rules_keywords):
            return "rules"
        elif any(kw in question_lower for kw in npc_keywords):
            return "npc"
        else:
            return "lore"
