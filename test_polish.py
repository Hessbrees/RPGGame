"""
Krótki test czy agenci odpowiadają po polsku
"""
import os
from dotenv import load_dotenv
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from src.orchestrator import GameOrchestrator

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def test_polish_language():
    print("=== Test języka polskiego ===\n")

    llm = Ollama(
        model=OLLAMA_MODEL, 
        base_url=OLLAMA_BASE_URL,
        request_timeout=120.0
    )
    embed_model = OllamaEmbedding(
        model_name=OLLAMA_EMBEDDING_MODEL, 
        base_url=OLLAMA_BASE_URL
    )

    orchestrator = GameOrchestrator(
        llm=llm, 
        embed_model=embed_model, 
        vibe="zrównoważona",
        num_players=2
    )

    # Test 1: GM narrate
    print("\n--- Test 1: GM narrate ---")
    intro = orchestrator.start_adventure()
    print(f"GM: {intro[:200]}...")
    
    # Test 2: Player action (Arin)
    print("\n--- Test 2: Arin decision ---")
    arin = orchestrator.players[0]
    arin_action = arin.decide_action("Widzisz ciemny las przed sobą.", None)
    print(f"Arin: {arin_action[:200]}...")
    
    # Test 3: Player action (Theron)
    print("\n--- Test 3: Theron decision ---")
    theron = orchestrator.players[1]
    theron_action = theron.decide_action("Widzisz ciemny las przed sobą.", None)
    print(f"Theron: {theron_action[:200]}...")
    
    print("\n=== Test zakończony ===")


if __name__ == "__main__":
    test_polish_language()
