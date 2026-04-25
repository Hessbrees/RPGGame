from .base_rag import BaseRAG


class LoreRAG(BaseRAG):
    """RAG odpowiedzialny za wiedzę o świecie gry: historia, miejsca, frakcje."""

    COLLECTION_NAME = "lore"
    DATA_DIR = "./data/lore"
