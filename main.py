import argparse
import os
import sys
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
NUM_PLAYERS = 2


def parse_args():
    parser = argparse.ArgumentParser(description="RPGGame - AI vs AI Game Engine")
    parser.add_argument("--illustrate", choices=["off", "inline", "deferred"], default=None,
                        help="Generowanie ilustracji: inline (od razu) lub deferred (po sesji, oszczędza VRAM)")
    parser.add_argument("--lora", action="append", default=None,
                        help="Ścieżka do wag LoRA (można podać wielokrotnie)")
    parser.add_argument("--turns", type=int, default=10, help="Maksymalna liczba tur")
    parser.add_argument("--open-gallery", action="store_true",
                        help="Po sesji otwórz galerię ilustracji w domyślnej przeglądarce")
    parser.add_argument("--gm-model", default=None, help="Model Ollama dla Mistrza Gry (domyślnie OLLAMA_MODEL)")
    parser.add_argument("--player-model", nargs="+", default=None,
                        help="Model(e) Ollama dla graczy: jeden dla wszystkich albo po jednym na gracza (Arin Theron)")
    parser.add_argument("--keep-journal", action="store_true",
                        help="Nie archiwizuj dziennika z poprzedniej sesji, dopisuj do niego")
    return parser.parse_args()


def main():
    # Przy przekierowaniu do potoku Windows używa cp1250, który nie koduje emoji.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    print("=== RPGGame - AI vs AI Game Engine ===\n")
    print("🎭 2 Graczy AI + Mistrz Gry")
    print("🤖 Arin (złodziej) + Theron (wojownik)\n")

    def make_llm(model: str) -> Ollama:
        return Ollama(model=model, base_url=OLLAMA_BASE_URL, request_timeout=300.0)

    llm = make_llm(OLLAMA_MODEL)
    gm_llm = make_llm(args.gm_model) if args.gm_model else None
    player_llms = None
    if args.player_model:
        models = args.player_model * NUM_PLAYERS if len(args.player_model) == 1 else args.player_model
        player_llms = [make_llm(m) for m in models]
    embed_model = OllamaEmbedding(
        model_name=OLLAMA_EMBEDDING_MODEL, 
        base_url=OLLAMA_BASE_URL
    )

    image_config = ImageGenConfig()
    if args.illustrate is not None:
        image_config.mode = args.illustrate
    if args.lora:
        image_config.lora_paths = args.lora
    used_models = [args.gm_model, *(args.player_model or [])]
    image_config.ollama_extra_models = [m for m in dict.fromkeys(used_models) if m and m != OLLAMA_MODEL]

    # Inicjalizacja z 2 graczami AI
    orchestrator = GameOrchestrator(
        llm=llm, 
        embed_model=embed_model, 
        vibe="zrównoważona",
        num_players=NUM_PLAYERS,
        image_config=image_config,
        gm_llm=gm_llm,
        player_llms=player_llms,
        new_session=not args.keep_journal,
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
