from src.rags.lore_rag import LoreRAG
from src.rags.npc_rag import NpcRAG
from src.rags.judge_rag import JudgeRAG
from src.rags.chronicle_rag import ChronicleRAG
from src.rags.reranker import Reranker
from src.agents.game_master_agent import GameMasterAgent
from src.agents.player_agent import PlayerAgent
from src.game_state.game_state import GameState, GameVibe, ConversationMode, PlayerState
from src.game_state.state_updater import apply_state_update
from src.image_gen import ImageGenConfig, IllustrationPipeline

# Po tylu rundach turowych GM wraca do rozmowy swobodnej (inaczej tryb turowy trwałby do końca sesji).
TURN_ROUNDS_BEFORE_FREE = 3
# Powyżej tylu wpisów dziennik jest kompresowany przez Kronikarza.
JOURNAL_COMPRESS_THRESHOLD = 40


class GameOrchestrator:
    """
    Orkiestrator rozgrywki – główny kontroler sesji RPG.
    Odpowiada za:
    - Przetwarzanie akcji graczy i mistrza gry.
    - Zarządzanie stanem świata i turami.
    - Kierowanie zapytań do odpowiednich RAGów.
    - Wspólną szynę komunikacyjną między uczestnikami.
    """

    def __init__(self, llm, embed_model, vibe: str = "zrównoważona", scenario: str = "", num_players: int = 2,
                 image_config: ImageGenConfig | None = None, gm_llm=None, player_llms: list | None = None,
                 new_session: bool = True):
        self.llm = llm
        if new_session:
            ChronicleRAG.start_session()
        self.lore_rag = LoreRAG(llm=llm, embed_model=embed_model)
        self.npc_rag = NpcRAG(llm=llm, embed_model=embed_model)
        self.judge_rag = JudgeRAG(llm=llm, embed_model=embed_model)
        self.chronicle_rag = ChronicleRAG(llm=llm, embed_model=embed_model)
        self.reranker = Reranker(top_k=3)
        self.game_master = GameMasterAgent(llm=gm_llm or llm, vibe=vibe)
        self.game_state = GameState(
            scenario=scenario,
            vibe=GameVibe(vibe),
        )
        
        # ✨ MODUŁ 1: Gracze AI
        self.players: list[PlayerAgent] = []
        self._initialize_players(llm, num_players, player_llms)
        
        # ✨ MODUŁ 2: Wspólna szyna komunikacyjna (Message Bus)
        self.message_history: list[dict] = []
        
        # Indeks aktywnego gracza (dla TURN_BASED)
        self.active_player_index = 0

        # Przełączanie trybów: licznik rund turowych i początek bieżącej rozmowy swobodnej w historii
        self._turn_rounds = 0
        self._free_conv_start = 0
        self.last_state_changes: dict[str, list[str]] = {}

        # MODUŁ 6: Ilustracje (modele dyfuzyjne) – opcjonalne
        self.illustrator: IllustrationPipeline | None = (
            IllustrationPipeline(llm, image_config) if image_config and image_config.enabled else None
        )

    # ------------------------------------------------------------------
    # MODUŁ 1: Inicjalizacja graczy AI
    # ------------------------------------------------------------------
    
    def _initialize_players(self, llm, num_players: int, player_llms: list | None = None):
        """Tworzy graczy AI z predefiniowanymi personami (opcjonalnie z osobnym modelem dla każdego)."""
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
            agent_llm = player_llms[i] if player_llms and i < len(player_llms) and player_llms[i] else llm
            player_agent = PlayerAgent(agent_llm, persona)
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
        1. Pobiera z Sędziego RAG zasady istotne dla akcji.
        2. Mistrz Gry reaguje (zna gracza, zasady i aktualny stan) i opisuje konsekwencje.
        3. Skutki (HP, ekwipunek) są ustalane i stosowane w kodzie, nie tylko opisane w narracji.
        4. Zdarzenie i skutki trafiają do Kronikarza.
        """
        player_state = next((p for p in self.game_state.players if p.name == player_name), None)
        rules_context = self.judge_rag.query(f"Czy ta akcja jest zgodna z zasadami: {action}")
        response = self.game_master.react_to_player_action(
            action,
            self.game_state.describe_state(),
            player_name=player_name,
            persona=player_state.persona if player_state else None,
            rules=rules_context[:600],
        )
        self.chronicle_rag.add_entry(f"[Tura {self.game_state.current_turn}] {player_name}: {action}")
        self.chronicle_rag.add_entry(f"[GM]: {response}")

        self.last_state_changes = {}
        updates = self.game_master.extract_state_updates(
            response, [p for p in self.game_state.players if p.active]
        )
        for state in self.game_state.players:
            changes = apply_state_update(state, updates[state.name]) if state.name in updates else []
            if changes:
                self.last_state_changes[state.name] = changes
                self.chronicle_rag.add_entry(
                    f"[Tura {self.game_state.current_turn}] Stan {state.name}: {', '.join(changes)}"
                )
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
        """Dodaje wiadomość do wspólnej szyny komunikacyjnej i (opcjonalnie) zleca ilustrację sceny."""
        self.message_history.append(message)
        self._maybe_illustrate(message)

    def _maybe_illustrate(self, message: dict) -> None:
        if self.illustrator is None or message.get("type") != "narration":
            return
        events = [f"{m['speaker']}: {m['content']}" for m in self.message_history[-4:]]
        try:
            lore_context = self.lore_rag.query(message["content"][:300])
        except Exception:
            lore_context = ""
        self.illustrator.on_event(message, self.game_state, events, lore_context)

    def finish_illustrations(self):
        """Kończy sesję ilustracji (render zaległych scen, galeria HTML). Zwraca ścieżkę galerii lub None."""
        return self.illustrator.close() if self.illustrator else None
    
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
            
            # GM sprawdza czy zakończyć rozmowę (oceniamy tylko wiadomości z bieżącej rozmowy swobodnej)
            if self.game_master.should_end_free_conversation(self.message_history[self._free_conv_start:]):
                print("\n[GM kończy rozmowę swobodną]\n")
                self.game_state.conversation_mode = ConversationMode.TURN_BASED
                self._turn_rounds = 0
                break

        self.game_state.next_turn()
        self._maybe_compress_journal()

    def _player_status(self, player_state: PlayerState) -> str:
        return f"Twój stan: HP {player_state.hp}/100, ekwipunek: {', '.join(player_state.inventory) or 'pusty'}."

    def _maybe_compress_journal(self) -> None:
        """Kronikarz podsumowuje starsze wpisy, gdy dziennik robi się zbyt długi."""
        if self.chronicle_rag.entry_count() > JOURNAL_COMPRESS_THRESHOLD:
            self.chronicle_rag.compress_journal()
    
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
            
            # Gracz AI podejmuje decyzję (zna swój aktualny stan; status na końcu, żeby nie został ucięty)
            context = self.get_visible_history(player_state.name)
            situation = context[-500:] if context else "Jesteś w walce..."
            action = player_agent.decide_action(
                situation=f"{situation}\n\n{self._player_status(player_state)}",
                available_actions=["Atak", "Obrona", "Użyj przedmiotu", "Uciekaj"]
            )
            
            print(f"\n{player_state.name}: {action}")
            
            # GM przetwarza akcję
            result = self.process_player_action(action, player_state.name)
            print(f"GM: {result}\n")
            for name, changes in self.last_state_changes.items():
                print(f"[Stan] {name}: {', '.join(changes)}")
            if self.last_state_changes:
                print()

            # Broadcast: najpierw akcja gracza, potem narracja GM (to ona jest ilustrowana)
            self.broadcast_message({
                "turn": self.game_state.current_turn,
                "speaker": player_state.name,
                "type": "action",
                "content": action,
                "visible_to": ["all"]
            })
            self.broadcast_message({
                "turn": self.game_state.current_turn,
                "speaker": "GM",
                "type": "narration",
                "content": result,
                "visible_to": ["all"]
            })
        
        # Następna tura
        self.game_state.next_turn()
        self._maybe_compress_journal()

        # Po kilku rundach turowych GM kończy scenę i wraca do rozmowy swobodnej
        self._turn_rounds += 1
        if self._turn_rounds >= TURN_ROUNDS_BEFORE_FREE and not self.is_game_over():
            print("\n[GM kończy scenę - wrócicie do swobodnej rozmowy]\n")
            self.game_state.conversation_mode = ConversationMode.FREE
            self._free_conv_start = len(self.message_history)
            self._turn_rounds = 0
    
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

