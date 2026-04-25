import os
from dotenv import load_dotenv
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from src.orchestrator import GameOrchestrator

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def main():
    print("=== RPGGame - AI Game Engine ===\n")

    llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    embed_model = OllamaEmbedding(
        model_name=OLLAMA_EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL
    )

    orchestrator = GameOrchestrator(llm=llm, embed_model=embed_model, vibe="zrównoważona")

    print("Silnik gotowy. Wpisz pytanie lub 'exit' aby wyjść.\n")

    while True:
        question = input("Gracz > ").strip()
        if question.lower() in ("exit", "quit", "q"):
            print("Do zobaczenia!")
            break
        if not question:
            continue

        response = orchestrator.query(question)
        print(f"\nGM > {response}\n")


if __name__ == "__main__":
    main()
