from src.game_state.state_updater import StateUpdate, parse_state_updates, strip_state_dump

GAME_MASTER_SYSTEM_PROMPT = """Jesteś bezlitosnym Mistrzem Gry. Twoim celem nie jest pomaganie graczowi, \
lecz sprawiedliwe, ale surowe egzekwowanie zasad świata. NPC są egoistyczni, świat jest niebezpieczny. \
Jeśli gracz popełni błąd, pozwól mu ponieść surowe konsekwencje, wliczając w to śmierć postaci.
NPC nie są Twoimi przyjaciółmi. Są przeszkodami. Walczą inteligentnie, uciekają, gdy przegrywają, \
i kłamią, jeśli to im pomoże.

ZAWSZE ODPOWIADAJ WYŁĄCZNIE PO POLSKU. Nie używaj języka angielskiego."""

ARBITER_PROMPT = """Jesteś arbitrem gry RPG. Na podstawie opisu zdarzenia ustal jego skutki dla KAŻDEJ z postaci graczy.

Postacie graczy:
{players}

Opis zdarzenia:
{narration}

Odpowiedz WYŁĄCZNIE jednym obiektem JSON, w którym kluczem jest imię postaci, a wartością obiekt z polami:
- "hp_change": liczba całkowita (ujemna = obrażenia, dodatnia = leczenie)
- "incapacitated": true tylko, gdy opis wprost mówi, że postać straciła przytomność lub zginęła, w przeciwnym razie false
- "items_gained": lista przedmiotów zdobytych przez postać
- "items_lost": lista przedmiotów straconych lub zużytych
ZASADA: hp_change różne od 0 ustawiaj tylko wtedy, gdy opis wprost podaje, że dana postać otrzymała obrażenia lub została uleczona. Groźba, zbliżający się wróg lub ostrzeżenie to hp_change = 0.

JSON:"""


class GameMasterAgent:
    """
    Agent LLM wcielający się w rolę Mistrza Gry.
    Odpowiada za:
    - Prowadzenie fabuły i reagowanie na nieprzewidziane pomysły graczy.
    - Kontrolowanie dialogu i zarządzanie tempem rozgrywki.
    - Inicjalizowanie sprawdzeń i rzutów kostką.
    - Odgrywanie postaci pobocznych (NPC).
    """

    def __init__(self, llm, vibe: str = "zrównoważona"):
        self.llm = llm
        self.vibe = vibe
        self.system_prompt = self._build_system_prompt(vibe)

    def _build_system_prompt(self, vibe: str) -> str:
        vibe_instructions = {
            "chaotyczna": "Rozgrywka jest chaotyczna i nieprzewidywalna. Wprowadzaj losowe zdarzenia często.",
            "trudna": "Rozgrywka jest trudna i bezlitosna. Nie dawaj graczom taryfy ulgowej.",
            "spokojna": "Rozgrywka jest spokojna i narracyjna. Dawaj graczom czas na eksplorację.",
            "zrównoważona": "Rozgrywka jest zrównoważona między akcją a narracją.",
        }
        vibe_text = vibe_instructions.get(vibe, vibe_instructions["zrównoważona"])
        return f"{GAME_MASTER_SYSTEM_PROMPT}\n\nStyl rozgrywki: {vibe_text}"

    def narrate(self, situation: str, context: str = "") -> str:
        """Opisuje sytuację i prowadzi fabułę."""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Kontekst: {context}\n\n"
            f"Sytuacja: {situation}\n\n"
            "Opisz co się dzieje i co gracze widzą.\n"
            "OPISZ PO POLSKU."
        )
        return str(self.llm.complete(prompt))

    def react_to_player_action(
        self,
        action: str,
        game_state: str,
        player_name: str = "",
        persona: dict | None = None,
        rules: str = "",
    ) -> str:
        """Reaguje na akcję gracza i dostosowuje fabułę."""
        who = ""
        if player_name:
            char_class = (persona or {}).get("class", "")
            who = (
                f"Akcję wykonuje gracz: {player_name}{f' ({char_class})' if char_class else ''}. "
                "Opisuj konsekwencje wyłącznie dla tej postaci i zwracaj się do niej po imieniu; "
                "pozostali gracze to odrębne postacie.\n\n"
            )
        rules_block = f"Zasady gry (z podręcznika): {rules}\n\n" if rules else ""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Stan gry (prowadzony przez system, jest wiążący): {game_state}\n\n"
            f"{rules_block}"
            f"{who}"
            f"Akcja gracza: {action}\n\n"
            "Zareaguj na tę akcję jako Mistrz Gry. Opisz konsekwencje. "
            "Nie wypisuj stanu gry, słowników w nawiasach klamrowych ani liczby punktów zdrowia graczy - stanem zarządza system.\n"
            "ODPOWIEDZ PO POLSKU."
        )
        return strip_state_dump(str(self.llm.complete(prompt)))

    def extract_state_updates(self, narration: str, players: list) -> dict[str, StateUpdate]:
        """Ustala skutki zdarzenia (HP, przedmioty) dla wszystkich aktywnych graczy na podstawie narracji GM."""
        if not players:
            return {}
        listing = "\n".join(
            f"- {p.name}: HP {p.hp}/100, ekwipunek: {', '.join(p.inventory) or 'pusty'}" for p in players
        )
        prompt = ARBITER_PROMPT.format(players=listing, narration=narration[:1500])
        return parse_state_updates(str(self.llm.complete(prompt)), [p.name for p in players])

    def play_npc(self, npc_name: str, npc_description: str, player_input: str) -> str:
        """Odgrywa postać NPC w odpowiedzi na gracza."""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Wciel się w NPC: {npc_name}. Opis: {npc_description}\n\n"
            f"Gracz mówi: {player_input}\n\n"
            f"Odpowiedz jako {npc_name}.\n"
            "ODPOWIEDZ PO POLSKU."
        )
        return str(self.llm.complete(prompt))
    
    def should_end_free_conversation(self, message_history: list) -> bool:
        """Decyduje czy zakończyć rozmowę swobodną."""
        # Proste heurystyki:
        # - Jeśli rozmowa trwa > 5 wymian
        # - Jeśli gracze wspominają o akcji/walce
        if len(message_history) > 10:
            return True
        
        recent = " ".join([msg.get("content", "") for msg in message_history[-3:]])
        action_keywords = ["atak", "walka", "idź", "otwórz", "przeszukaj", "użyj"]
        
        if any(kw in recent.lower() for kw in action_keywords):
            return True
        
        return False
