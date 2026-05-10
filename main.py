import os
from dotenv import load_dotenv
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from src.orchestrator import GameOrchestrator
from src.game_state.game_state import ConversationMode

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def main():
    print("=== RPGGame - AI vs AI Game Engine ===\n")
    print("🎭 2 Graczy AI + Mistrz Gry")
    print("🤖 Arin (złodziej) + Theron (wojownik)\n")

    llm = Ollama(
        model=OLLAMA_MODEL, 
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0
    )
    embed_model = OllamaEmbedding(
        model_name=OLLAMA_EMBEDDING_MODEL, 
        base_url=OLLAMA_BASE_URL
    )

    # Inicjalizacja z 2 graczami AI
    orchestrator = GameOrchestrator(
        llm=llm, 
        embed_model=embed_model, 
        vibe="zrównoważona",
        num_players=2
    )

    # GM rozpoczyna przygodę
    print("\n" + "="*60)
    intro = orchestrator.start_adventure()
    print(f"GM: {intro}")
    print("="*60 + "\n")

    max_turns = 10  # Maksymalna liczba tur
    
    for turn in range(max_turns):
        orchestrator.display_game_state()
        
        # Sprawdź czy gra się skończyła
        if orchestrator.is_game_over():
            print(orchestrator.get_ending())
            break
        
        # Tryb konwersacji zależy od sytuacji
        if orchestrator.game_state.conversation_mode == ConversationMode.FREE:
            print("\n--- ROZMOWA SWOBODNA ---\n")
            orchestrator.run_free_conversation(max_exchanges=2)
        else:
            print("\n--- TRYB TUROWY ---\n")
            orchestrator.run_turn_based_round()
        
        print("\n" + "-"*60 + "\n")
    
    # Zakończenie
    print("\n" + "="*60)
    print("Koniec gry!")
    print(orchestrator.get_ending())
    print("="*60)


if __name__ == "__main__":
    main()
