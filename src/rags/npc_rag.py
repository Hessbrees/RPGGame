from .base_rag import BaseRAG


class NpcRAG(BaseRAG):
    """RAG odpowiedzialny za postacie NPC: osobowości, dialogi, questy."""

    COLLECTION_NAME = "npcs"
    DATA_DIR = "./data/npcs"
