from .base_rag import BaseRAG


class JudgeRAG(BaseRAG):
    """
    Sędzia RAG – odpowiada za zasady gry i profil preferencji gracza (vibe rozgrywki).
    Przeszukuje podręcznik zasad tylko wtedy, gdy są potrzebne.
    """

    COLLECTION_NAME = "judge"
    DATA_DIR = "./data/rules"
