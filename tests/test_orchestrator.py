import json

import pytest
from llama_index.core.embeddings import MockEmbedding

from src.game_state.game_state import ConversationMode
from src.orchestrator.game_orchestrator import TURN_ROUNDS_BEFORE_FREE, GameOrchestrator
from src.rags.base_rag import BaseRAG
from src.rags.chronicle_rag import ChronicleRAG


class ScriptedLLM:
    """Atrapa LLM: odpowiedź zależy od typu promptu; zapamiętuje wszystkie prompty."""

    def __init__(self, name="stub", hp_changes=None, incapacitated=()):
        self.name = name
        self.hp_changes = {"Arin": -20} if hp_changes is None else hp_changes
        self.incapacitated = incapacitated
        self.prompts: list[str] = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        if "jesteś arbitrem" in prompt.lower():
            names = ("Arin", "Theron")
            return json.dumps({
                n: {"hp_change": self.hp_changes.get(n, 0), "incapacitated": n in self.incapacitated,
                    "items_gained": [], "items_lost": []}
                for n in names
            })
        if "Akcja gracza:" in prompt:
            return "Cios trafia postać.\nStan gry: {'turn': 3, 'players': [{'hp': 10}]}\nCo dalej?"
        if "Podsumuj zwięźle" in prompt:
            return "Streszczenie sesji."
        return "Rozglądam się po okolicy."


@pytest.fixture
def make_game(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DB_PATH", str(tmp_path / "chroma"))
    chronicle_dir = tmp_path / "chronicle"
    chronicle_dir.mkdir()
    (chronicle_dir / "journal.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(ChronicleRAG, "JOURNAL_FILE", str(chronicle_dir / "journal.json"))
    monkeypatch.setattr(ChronicleRAG, "DATA_DIR", str(chronicle_dir))
    monkeypatch.setattr(BaseRAG, "query", lambda self, question: "Zasada: akcje bojowe rozstrzyga rzut k20.")

    def build(**kwargs):
        kwargs.setdefault("llm", ScriptedLLM())
        return GameOrchestrator(embed_model=MockEmbedding(embed_dim=8), **kwargs)

    return build


def player(game, name):
    return next(p for p in game.game_state.players if p.name == name)


def test_gm_prompt_names_the_acting_player_and_includes_rules(make_game):
    llm = ScriptedLLM()
    game = make_game(llm=llm)
    game.process_player_action("Atakuję goblina", "Theron")
    gm_prompt = next(p for p in llm.prompts if "Akcja gracza:" in p)
    assert "Akcję wykonuje gracz: Theron (wojownik)" in gm_prompt
    assert "rzut k20" in gm_prompt
    assert "Arin: HP 100/100" in gm_prompt


def test_action_updates_the_hit_player_and_cleans_narration(make_game):
    game = make_game()
    response = game.process_player_action("Atakuję goblina", "Theron")
    assert player(game, "Arin").hp == 80
    assert player(game, "Theron").hp == 100
    assert "{" not in response
    assert game.last_state_changes == {"Arin": ["HP 100 -> 80"]}


def test_incapacitated_player_is_set_to_zero_hp(make_game):
    game = make_game(llm=ScriptedLLM(hp_changes={}, incapacitated=("Theron",)))
    game.process_player_action("Atakuję", "Arin")
    assert player(game, "Theron").hp == 0 and not player(game, "Theron").active
    assert player(game, "Arin").active


def test_state_change_is_written_to_chronicle(make_game):
    game = make_game()
    game.process_player_action("Atakuję goblina", "Arin")
    entries = json.loads(open(ChronicleRAG.JOURNAL_FILE, encoding="utf-8").read())
    assert any("Stan Arin: HP 100 -> 80" in e for e in entries)


def test_game_over_when_all_players_reach_zero_hp(make_game):
    game = make_game(llm=ScriptedLLM(hp_changes={"Arin": -50, "Theron": -50}))
    assert not game.is_game_over()
    for _ in range(2):
        for name in ("Arin", "Theron"):
            game.process_player_action("Stoję w miejscu", name)
    assert game.is_game_over()


def test_turn_based_returns_to_free_conversation_and_advances_turns(make_game):
    game = make_game(llm=ScriptedLLM(hp_changes={}))
    game.game_state.conversation_mode = ConversationMode.TURN_BASED
    for i in range(TURN_ROUNDS_BEFORE_FREE):
        assert game.game_state.conversation_mode == ConversationMode.TURN_BASED
        game.run_turn_based_round()
    assert game.game_state.conversation_mode == ConversationMode.FREE
    assert game.game_state.current_turn == TURN_ROUNDS_BEFORE_FREE


def test_free_conversation_ignores_history_from_before_it_started(make_game):
    game = make_game(llm=ScriptedLLM(hp_changes={}))
    game.message_history = [{"speaker": "GM", "type": "narration", "content": "atak", "visible_to": ["all"]}] * 15
    game._free_conv_start = len(game.message_history)
    game.run_free_conversation(max_exchanges=2)
    assert game.game_state.conversation_mode == ConversationMode.FREE
    assert game.game_state.current_turn == 1


def test_free_conversation_ends_when_players_mention_action(make_game):
    llm = ScriptedLLM(hp_changes={})
    llm.complete = lambda prompt: "Wykonuję atak na wroga."
    game = make_game(llm=llm)
    game.run_free_conversation(max_exchanges=2)
    assert game.game_state.conversation_mode == ConversationMode.TURN_BASED


def test_separate_models_for_gm_and_players(make_game):
    default, gm, arin, theron = (ScriptedLLM(n) for n in ("default", "gm", "arin", "theron"))
    game = make_game(llm=default, gm_llm=gm, player_llms=[arin, theron])
    assert game.game_master.llm is gm
    assert [p.llm for p in game.players] == [arin, theron]


def test_default_model_is_used_for_every_role(make_game):
    default = ScriptedLLM("default")
    game = make_game(llm=default)
    assert game.game_master.llm is default
    assert all(p.llm is default for p in game.players)


def test_new_session_archives_previous_journal(make_game, tmp_path):
    journal = tmp_path / "chronicle" / "journal.json"
    journal.write_text(json.dumps(["[Tura 0] stary wpis"]), encoding="utf-8")
    make_game()
    assert json.loads(journal.read_text(encoding="utf-8")) == []
    archived = list((tmp_path / "chronicle" / "archive").glob("journal_*.json"))
    assert len(archived) == 1 and "stary wpis" in archived[0].read_text(encoding="utf-8")


def test_keep_journal_appends_to_existing_one(make_game, tmp_path):
    journal = tmp_path / "chronicle" / "journal.json"
    journal.write_text(json.dumps(["[Tura 0] stary wpis"]), encoding="utf-8")
    make_game(new_session=False)
    assert json.loads(journal.read_text(encoding="utf-8")) == ["[Tura 0] stary wpis"]


def test_journal_is_compressed_when_too_long(make_game, tmp_path):
    game = make_game()
    for i in range(45):
        game.chronicle_rag.add_entry(f"wpis {i}")
    game._maybe_compress_journal()
    entries = json.loads((tmp_path / "chronicle" / "journal.json").read_text(encoding="utf-8"))
    assert entries[0].startswith("[PODSUMOWANIE]") and len(entries) == 6
