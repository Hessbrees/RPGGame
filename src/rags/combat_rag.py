from .base_rag import BaseRAG


class CombatRAG(BaseRAG):
    """RAG odpowiedzialny za mechaniki walki: zasady, czary, statystyki."""

    COLLECTION_NAME = "combat"
    DATA_DIR = "./data/combat"
