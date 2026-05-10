PLAYER_SYSTEM_PROMPT = """Wcielasz się w postać gracza w sesji RPG. \
Interpretujesz swoją personę, analizujesz sytuację i narrujesz swoje działania w pierwszej osobie. \
Reagujesz na otoczenie zgodnie z charakterem swojej postaci.

ZAWSZE ODPOWIADAJ WYŁĄCZNIE PO POLSKU. Nie używaj języka angielskiego."""


class PlayerAgent:
    """
    Agent LLM wcielający się w rolę Gracza.
    Odpowiada za:
    - Interpretację persony – wcielanie się w rolę.
    - Analizę sytuacji i reakcję na daną sytuację.
    - Narrację działań – opisywanie jak wykonuje akcje.
    - Interakcję społeczną – rozmowę z innymi uczestnikami.
    """

    def __init__(self, llm, persona: dict):
        """
        Args:
            llm: Model językowy.
            persona: Słownik z opisem postaci, np.
                     {"name": "Arin", "class": "złodziej", "traits": "przebiegły, skryty"}
        """
        self.llm = llm
        self.persona = persona
        self.system_prompt = self._build_system_prompt(persona)

    def _build_system_prompt(self, persona: dict) -> str:
        name = persona.get("name", "Nieznany")
        char_class = persona.get("class", "przygodnik")
        traits = persona.get("traits", "")
        backstory = persona.get("backstory", "")

        return (
            f"{PLAYER_SYSTEM_PROMPT}\n\n"
            f"Twoja postać: {name}, {char_class}.\n"
            f"Cechy charakteru: {traits}\n"
            f"Historia postaci: {backstory}"
        )

    def decide_action(self, situation: str, available_actions: list[str] | None = None) -> str:
        """Analizuje sytuację i podejmuje decyzję jako postać gracza."""
        actions_text = ""
        if available_actions:
            actions_text = "\nDostępne akcje:\n" + "\n".join(f"- {a}" for a in available_actions)

        prompt = (
            f"{self.system_prompt}\n\n"
            f"Sytuacja: {situation}{actions_text}\n\n"
            "Co robisz? Opisz swoją akcję w pierwszej osobie.\n"
            "ODPOWIEDZ PO POLSKU."
        )
        return str(self.llm.complete(prompt))

    def speak(self, situation: str, interlocutor: str) -> str:
        """Generuje dialog postaci gracza."""
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Rozmawiasz z: {interlocutor}\n"
            f"Sytuacja: {situation}\n\n"
            "Co mówisz?\n"
            "ODPOWIEDZ PO POLSKU."
        )
        return str(self.llm.complete(prompt))
