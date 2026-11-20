import argparse
import os
import webbrowser
from pathlib import Path
from dotenv import load_dotenv
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from src.orchestrator import GameOrchestrator
from src.game_state.game_state import ConversationMode
from src.image_gen import ImageGenConfig

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def parse_args():
    parser = argparse.ArgumentParser(description="RPGGame - AI vs AI Game Engine")
    parser.add_argument("--illustrate", choices=["off", "inline", "deferred"], default=None,
                        help="Generowanie ilustracji: inline (od razu) lub deferred (po sesji, oszczędza VRAM)")
    parser.add_argument("--lora", action="append", default=None,
                        help="Ścieżka do wag LoRA (można podać wielokrotnie)")
    parser.add_argument("--turns", type=int, default=10, help="Maksymalna liczba tur")
    parser.add_argument("--open-gallery", action="store_true",
                        help="Po sesji otwórz galerię ilustracji w domyślnej przeglądarce")
    return parser.parse_args()


def main():
    args = parse_args()
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

    image_config = ImageGenConfig()
    if args.illustrate is not None:
        image_config.mode = args.illustrate
    if args.lora:
        image_config.lora_paths = args.lora

    # Inicjalizacja z 2 graczami AI
    orchestrator = GameOrchestrator(
        llm=llm, 
        embed_model=embed_model, 
        vibe="zrównoważona",
        num_players=2,
        image_config=image_config,
    )

    # GM rozpoczyna przygodę
    print("\n" + "="*60)
    intro = orchestrator.start_adventure()
    print(f"GM: {intro}")
    print("="*60 + "\n")

    for turn in range(args.turns):
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

    gallery = orchestrator.finish_illustrations()
    if gallery:
        print(f"\nGaleria ilustracji: {gallery}")
        if args.open_gallery:
            webbrowser.open(Path(gallery).resolve().as_uri())


if __name__ == "__main__":
    main()
