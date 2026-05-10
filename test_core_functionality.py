"""
Test core functionality - mistrz gry, RAG-i, rozmowa między graczami
"""
import os
from dotenv import load_dotenv
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from src.orchestrator import GameOrchestrator
from src.agents.game_master_agent import GameMasterAgent
from src.agents.player_agent import PlayerAgent

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def test_rags(orchestrator):
    """Test czy RAG-i zwracają sensowne odpowiedzi"""
    print_section("TEST 1: RAG-i (Retrieval Augmented Generation)")
    
    print("1.1. LoreRAG - pytanie o świat:")
    lore_response = orchestrator.query("Opowiedz mi o Królestwie Arendor", context="lore")
    print(f"Odpowiedź: {lore_response[:300]}...\n")
    
    print("1.2. JudgeRAG - pytanie o zasady walki:")
    rules_response = orchestrator.query("Jak działa atak w walce?", context="rules")
    print(f"Odpowiedź: {rules_response[:300]}...\n")
    
    print("1.3. NpcRAG - pytanie o postacie:")
    npc_response = orchestrator.query("Jakie są frakcje w grze?", context="npc")
    print(f"Odpowiedź: {npc_response[:300]}...\n")
    
    print("1.4. ChronicleRAG - dodanie wpisu i odczyt:")
    orchestrator.chronicle_rag.add_entry("[Tura 1] Gracze weszli do ciemnej piwnicy")
    orchestrator.chronicle_rag.add_entry("[Tura 2] Natknęli się na goblinów")
    chronicle_response = orchestrator.query("Co się wydarzyło wcześniej?", context="chronicle")
    print(f"Odpowiedź: {chronicle_response[:300]}...\n")
    
    return True

def test_game_master(llm):
    """Test GameMasterAgent - czy generuje narrację"""
    print_section("TEST 2: GameMasterAgent - Narracja i reakcje")
    
    gm = GameMasterAgent(llm=llm, vibe="zrównoważona")
    
    print("2.1. GM opisuje sytuację:")
    narration = gm.narrate(
        situation="Gracze stoją przed wejściem do ciemnej jaskini",
        context="Las Szeptów, noc, słychać dziwne dźwięki z głębi jaskini"
    )
    print(f"Narracja GM: {narration[:400]}...\n")
    
    print("2.2. GM reaguje na akcję gracza:")
    reaction = gm.react_to_player_action(
        action="Próbuję zapalić pochodnię i wejść do jaskini",
        game_state="Tura 1, HP: 100, Ekwipunek: miecz, pochodnia"
    )
    print(f"Reakcja GM: {reaction[:400]}...\n")
    
    print("2.3. GM odgrywa NPC:")
    npc_dialog = gm.play_npc(
        npc_name="Stary Kupiec",
        npc_description="Podejrzany kupiec sprzedający dziwne artefakty",
        player_input="Witaj, co masz na sprzedaż?"
    )
    print(f"NPC odpowiada: {npc_dialog[:300]}...\n")
    
    return True

def test_player_agent(llm):
    """Test PlayerAgent - czy AI gracz podejmuje decyzje"""
    print_section("TEST 3: PlayerAgent - AI jako gracz")
    
    persona = {
        "name": "Arin",
        "class": "złodziej",
        "traits": "przebiegły, skryty, nie ufa obcym",
        "backstory": "Wychował się na ulicach wielkiego miasta"
    }
    
    player = PlayerAgent(llm=llm, persona=persona)
    
    print("3.1. Gracz AI podejmuje decyzję:")
    decision = player.decide_action(
        situation="Stoisz przed zamkniętymi drzwiami. Słyszysz kroki zbliżających się strażników.",
        available_actions=["Otwórz zamek wytrychami", "Ukryj się w cieniu", "Wyjdź bronią"]
    )
    print(f"Decyzja gracza ({persona['name']}): {decision[:400]}...\n")
    
    print("3.2. Gracz AI rozmawia:")
    dialog = player.speak(
        situation="Kupiec oferuje ci podejrzany amulet za 50 złotych",
        interlocutor="Stary Kupiec"
    )
    print(f"Gracz mówi: {dialog[:300]}...\n")
    
    return True

def test_orchestrator_routing(orchestrator):
    """Test czy orchestrator właściwie kieruje zapytania do RAG-ów"""
    print_section("TEST 4: Orchestrator - Auto-routing zapytań")
    
    print("4.1. Auto-detect context dla pytania o historię:")
    response1 = orchestrator.query("Co wydarzyło się poprzednio w naszej przygodzie?")
    print(f"Wykryty kontekst: {orchestrator._detect_context('Co wydarzyło się poprzednio?')}")
    print(f"Odpowiedź: {response1[:200]}...\n")
    
    print("4.2. Auto-detect context dla pytania o walkę:")
    response2 = orchestrator.query("Ile obrażeń zadaje miecz długi?")
    print(f"Wykryty kontekst: {orchestrator._detect_context('Ile obrażeń zadaje miecz długi?')}")
    print(f"Odpowiedź: {response2[:200]}...\n")
    
    print("4.3. Auto-detect context dla pytania o lore:")
    response3 = orchestrator.query("Opowiedz o Zakonie Srebrnego Ostrza")
    print(f"Wykryty kontekst: {orchestrator._detect_context('Opowiedz o Zakonie Srebrnego Ostrza')}")
    print(f"Odpowiedź: {response3[:200]}...\n")
    
    return True

def test_game_flow(orchestrator, llm):
    """Test przepływu gry - czy wszystkie elementy działają razem"""
    print_section("TEST 5: Pełny przepływ rozgrywki")
    
    # Utworzenie gracza AI
    persona = {
        "name": "Theron",
        "class": "wojownik",
        "traits": "odważny, honorowy",
        "backstory": "Były żołnierz Zakonu Srebrnego Ostrza"
    }
    player = PlayerAgent(llm=llm, persona=persona)
    
    print("5.1. GM rozpoczyna przygodę:")
    intro = orchestrator.describe_situation(
        extra_context="To pierwsza tura. Gracze dopiero zaczynają swoją przygodę."
    )
    print(f"GM: {intro[:400]}...\n")
    
    print("5.2. Gracz AI reaguje na sytuację:")
    player_action = player.decide_action(
        situation=intro[:200],
        available_actions=["Rozejrzyj się", "Porozmawiaj z towarzyszami", "Ruszaj w drogę"]
    )
    print(f"Gracz ({persona['name']}): {player_action[:300]}...\n")
    
    print("5.3. GM przetwarza akcję gracza:")
    gm_response = orchestrator.process_player_action(
        action=player_action[:200],
        player_name=persona['name']
    )
    print(f"GM reaguje: {gm_response[:400]}...\n")
    
    print("5.4. Stan gry:")
    game_state = orchestrator.game_state.get_public_state()
    print(f"Tura: {game_state['turn']}")
    print(f"Vibe: {game_state['vibe']}")
    print(f"Trudność: {game_state['difficulty']}\n")
    
    return True

def test_conversation_modes():
    """Test czy tryby konwersacji są zaimplementowane"""
    print_section("TEST 6: Tryby konwersacji (FREE vs TURN_BASED)")
    
    from src.game_state.game_state import ConversationMode
    
    print("6.1. ConversationMode.FREE istnieje:", ConversationMode.FREE)
    print("6.2. ConversationMode.TURN_BASED istnieje:", ConversationMode.TURN_BASED)
    
    # Sprawdź czy jest używany w orchestratorze
    print("\n❌ PROBLEM: ConversationMode jest zdefiniowany ale NIE JEST UŻYWANY")
    print("   - Brak przełączania między trybami")
    print("   - Brak logiki rozmowy swobodnej vs turowej")
    print("   - GM nie może zakończyć rozmowy")
    
    return False

def test_multi_player():
    """Test czy wieloosobowa rozgrywka działa"""
    print_section("TEST 7: Wieloosobowa rozgrywka")
    
    print("❌ PROBLEM: Wieloosobowa rozgrywka NIE JEST ZAIMPLEMENTOWANA")
    print("   - main.py obsługuje tylko jedno wejście od użytkownika")
    print("   - Brak mechanizmu tury między graczami")
    print("   - Brak 'wspólnej szyny komunikacyjnej' między AI-graczami")
    print("   - PlayerAgent istnieje ale nie jest używany w main.py")
    
    return False

def main():
    print("\n" + "="*80)
    print("  TEST CORE FUNCTIONALITY - RPG Game AI Engine")
    print("="*80)
    
    print("\nInicjalizacja LLM i Orchestratora...")
    llm = Ollama(
        model=OLLAMA_MODEL, 
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0
    )
    embed_model = OllamaEmbedding(
        model_name=OLLAMA_EMBEDDING_MODEL, 
        base_url=OLLAMA_BASE_URL
    )
    
    orchestrator = GameOrchestrator(llm=llm, embed_model=embed_model, vibe="zrównoważona")
    
    print("✅ Inicjalizacja zakończona\n")
    
    # Uruchom testy
    results = {}
    
    try:
        results['RAGs'] = test_rags(orchestrator)
    except Exception as e:
        print(f"❌ BŁĄD w teście RAG-ów: {e}\n")
        results['RAGs'] = False
    
    try:
        results['GameMaster'] = test_game_master(llm)
    except Exception as e:
        print(f"❌ BŁĄD w teście GameMaster: {e}\n")
        results['GameMaster'] = False
    
    try:
        results['PlayerAgent'] = test_player_agent(llm)
    except Exception as e:
        print(f"❌ BŁĄD w teście PlayerAgent: {e}\n")
        results['PlayerAgent'] = False
    
    try:
        results['Orchestrator'] = test_orchestrator_routing(orchestrator)
    except Exception as e:
        print(f"❌ BŁĄD w teście Orchestrator: {e}\n")
        results['Orchestrator'] = False
    
    try:
        results['GameFlow'] = test_game_flow(orchestrator, llm)
    except Exception as e:
        print(f"❌ BŁĄD w teście przepływu gry: {e}\n")
        results['GameFlow'] = False
    
    results['ConversationModes'] = test_conversation_modes()
    results['MultiPlayer'] = test_multi_player()
    
    # Podsumowanie
    print_section("PODSUMOWANIE TESTÓW")
    
    for test_name, passed in results.items():
        status = "✅ DZIAŁA" if passed else "❌ NIE DZIAŁA / NIEKOMPLETNE"
        print(f"{test_name:20s} : {status}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    percentage = (passed_count / total_count) * 100
    
    print(f"\nWynik: {passed_count}/{total_count} testów przeszło ({percentage:.0f}%)")
    
    if percentage < 50:
        print("\n⚠️  CORE funkcjonalność wymaga znaczącej pracy")
    elif percentage < 80:
        print("\n⚠️  Podstawy działają, ale brakuje kluczowych elementów")
    else:
        print("\n✅ Większość core funkcjonalności działa poprawnie")

if __name__ == "__main__":
    main()
