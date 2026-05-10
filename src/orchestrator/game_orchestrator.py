from src.rags.lore_rag import LoreRAG
from src.rags.npc_rag import NpcRAG
from src.rags.judge_rag import JudgeRAG
from src.rags.chronicle_rag import ChronicleRAG
from src.rags.reranker import Reranker
from src.agents.game_master_agent import GameMasterAgent
from src.agents.player_agent import PlayerAgent
from src.game_state.game_state import GameState, GameVibe, ConversationMode, PlayerState


class GameOrchestrator:
    """
    Orkiestrator rozgrywki – główny kontroler sesji RPG.
    Odpowiada za:
    - Przetwarzanie akcji graczy i mistrza gry.
    - Zarządzanie stanem świata i turami.
    - Kierowanie zapytań do odpowiednich RAGów.
    - Wspólną szynę komunikacyjną między uczestnikami.
    """

    def __init__(self, llm, embed_model, vibe: str = "zrównoważona", scenario: str = "", num_players: int = 2):
        self.llm = llm
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
        
        # ✨ MODUŁ 1: Gracze AI
        self.players: list[PlayerAgent] = []
        self._initialize_players(llm, num_players)
        
        # ✨ MODUŁ 2: Wspólna szyna komunikacyjna (Message Bus)
        self.message_history: list[dict] = []
        
        # Indeks aktywnego gracza (dla TURN_BASED)
        self.active_player_index = 0

    # ------------------------------------------------------------------
    # MODUŁ 1: Inicjalizacja graczy AI
    # ------------------------------------------------------------------
    
    def _initialize_players(self, llm, num_players: int):
        """Tworzy graczy AI z predefiniowanymi personami."""
        personas = [
            {
                "name": "Arin",
                "class": "złodziej",
                "traits": "przebiegły, skryty, nie ufa obcym",
                "backstory": "Wychował się na ulicach wielkiego miasta"
            },
            {
                "name": "Theron",
                "class": "wojownik",
                "traits": "odważny, honorowy, lojalny",
                "backstory": "Były żołnierz Zakonu Srebrnego Ostrza"
            }
        ]
        
        for i in range(min(num_players, len(personas))):
            persona = personas[i]
            player_agent = PlayerAgent(llm, persona)
            self.players.append(player_agent)
            
            # Dodaj do GameState
            player_state = PlayerState(
                name=persona["name"],
                persona=persona,
                hp=100,
                inventory=["miecz krótki", "pochodnia", "prowiant"],
                active=True
            )
            self.game_state.players.append(player_state)

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
    
    # ------------------------------------------------------------------
    # MODUŁ 2: Message Bus - Wspólna szyna komunikacyjna
    # ------------------------------------------------------------------
    
    def broadcast_message(self, message: dict):
        """Dodaje wiadomość do wspólnej szyny komunikacyjnej."""
        self.message_history.append(message)
    
    def get_visible_history(self, player_name: str) -> str:
        """Zwraca historię wiadomości widoczną dla gracza."""
        visible = [
            f"{msg['speaker']}: {msg['content']}"
            for msg in self.message_history
            if "all" in msg.get("visible_to", []) or player_name in msg.get("visible_to", [])
        ]
        return "\n".join(visible[-10:])  # ostatnie 10 wiadomości
    
    # ------------------------------------------------------------------
    # MODUŁ 3: Tryby konwersacji
    # ------------------------------------------------------------------
    
    def start_adventure(self) -> str:
        """GM rozpoczyna przygodę."""
        intro_context = self.lore_rag.query("Las Szeptów")
        intro = self.game_master.narrate(
            situation="Początek przygody w Lesie Szeptów",
            context=intro_context
        )
        self.broadcast_message({
            "turn": 0,
            "speaker": "GM",
            "type": "narration",
            "content": intro,
            "visible_to": ["all"]
        })
        return intro
    
    def run_free_conversation(self, max_exchanges: int = 3):
        """Rozmowa swobodna - gracze AI rozmawiają między sobą."""
        for i in range(max_exchanges):
            # Każdy gracz po kolei (ale bez sztywnej tury bojowej)
            for player_agent in self.players:
                player_name = player_agent.persona["name"]
                
                # Gracz widzi co mówili inni
                context = self.get_visible_history(player_name)
                
                # Gracz AI decyduje co powiedzieć/zrobić
                action = player_agent.decide_action(
                    situation=context[-500:] if context else "Rozpoczynacie przygodę...",
                    available_actions=None
                )
                
                print(f"{player_name}: {action}\n")
                
                # Broadcast do wszystkich
                self.broadcast_message({
                    "turn": self.game_state.current_turn,
                    "speaker": player_name,
                    "type": "dialog",
                    "content": action,
                    "visible_to": ["all"]
                })
                
                # Zapisz w kronice
                self.chronicle_rag.add_entry(
                    f"[Tura {self.game_state.current_turn}] {player_name}: {action}"
                )
            
            # GM sprawdza czy zakończyć rozmowę
            if self.game_master.should_end_free_conversation(self.message_history):
                print("\n[GM kończy rozmowę swobodną]\n")
                self.game_state.conversation_mode = ConversationMode.TURN_BASED
                break
    
    def run_turn_based_round(self):
        """Jedna runda turowa - każdy gracz po kolei."""
        for player_state in self.game_state.players:
            if not player_state.active:
                print(f"[{player_state.name} jest nieprzytomny]\n")
                continue
            
            # Znajdź odpowiadającego PlayerAgent
            player_agent = next(
                (p for p in self.players if p.persona["name"] == player_state.name),
                None
            )
            
            if not player_agent:
                continue
            
            # Gracz AI podejmuje decyzję
            context = self.get_visible_history(player_state.name)
            action = player_agent.decide_action(
                situation=context[-500:] if context else "Jesteś w walce...",
                available_actions=["Atak", "Obrona", "Użyj przedmiotu", "Uciekaj"]
            )
            
            print(f"\n{player_state.name}: {action}")
            
            # GM przetwarza akcję
            result = self.process_player_action(action, player_state.name)
            print(f"GM: {result}\n")
            
            # Broadcast
            self.broadcast_message({
                "turn": self.game_state.current_turn,
                "speaker": player_state.name,
                "type": "action",
                "content": action,
                "visible_to": ["all"]
            })
        
        # Następna tura
        self.game_state.next_turn()
    
    def display_game_state(self):
        """Wyświetla aktualny stan gry."""
        print("\n--- STAN GRY ---")
        for player in self.game_state.players:
            status = "✅" if player.active else "❌"
            print(f"{status} {player.name}: HP {player.hp}/100, Ekwipunek: {len(player.inventory)} przedmiotów")
        print(f"Tura: {self.game_state.current_turn}")
        print(f"Trudność: {self.game_state.difficulty}")
        print(f"Tryb: {self.game_state.conversation_mode}")
        print("-----------------\n")
    
    def is_game_over(self) -> bool:
        """Sprawdza czy gra się skończyła."""
        # Gra kończy się jeśli wszyscy gracze są nieprzytomni
        return all(not player.active for player in self.game_state.players)
    
    def get_ending(self) -> str:
        """Zwraca zakończenie gry."""
        if self.is_game_over():
            return "Wszyscy gracze polegli. Przygoda zakończona porażką."
        return "Przygoda zakończona sukcesem!"

