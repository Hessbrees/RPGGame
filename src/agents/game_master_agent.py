GAME_MASTER_SYSTEM_PROMPT = """Jesteś bezlitosnym Mistrzem Gry. Twoim celem nie jest pomaganie graczowi, \
lecz sprawiedliwe, ale surowe egzekwowanie zasad świata. NPC są egoistyczni, świat jest niebezpieczny. \
Jeśli gracz popełni błąd, pozwól mu ponieść surowe konsekwencje, wliczając w to śmierć postaci.
NPC nie są Twoimi przyjaciółmi. Są przeszkodami. Walczą inteligentnie, uciekają, gdy przegrywają, \
i kłamią, jeśli to im pomoże."""


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
            "Opisz co się dzieje i co gracze widzą."
        )
        return str(self.llm.complete(prompt))

    def react_to_player_action(self, action: str, game_state: str) -> str:
        """Reaguje na akcję gracza i dostosowuje fabułę."""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Stan gry: {game_state}\n\n"
            f"Akcja gracza: {action}\n\n"
            "Zareaguj na tę akcję jako Mistrz Gry. Opisz konsekwencje."
        )
        return str(self.llm.complete(prompt))

    def play_npc(self, npc_name: str, npc_description: str, player_input: str) -> str:
        """Odgrywa postać NPC w odpowiedzi na gracza."""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Wciel się w NPC: {npc_name}. Opis: {npc_description}\n\n"
            f"Gracz mówi: {player_input}\n\n"
            f"Odpowiedz jako {npc_name}."
        )
        return str(self.llm.complete(prompt))
