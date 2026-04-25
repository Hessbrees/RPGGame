from typing import List
from llama_index.core.schema import NodeWithScore


class Reranker:
    """
    Reranker – zmniejsza halucynacje poprzez ponowne rangowanie wyników RAG.
    Obsługuje wyszukiwanie BM25 oraz semantyczne.
    """

    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def rerank_bm25(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """
        Prosta implementacja BM25 – ranguje węzły na podstawie częstości słów kluczowych z zapytania.
        """
        query_terms = set(query.lower().split())

        scored: List[tuple] = []
        for node in nodes:
            text = node.node.get_content().lower()
            score = sum(text.count(term) for term in query_terms)
            scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in scored[: self.top_k]]

    def rerank_semantic(
        self, nodes: List[NodeWithScore], threshold: float = 0.0
    ) -> List[NodeWithScore]:
        """
        Ranguje semantycznie na podstawie istniejącego score z wektora podobieństwa.
        """
        filtered = [n for n in nodes if (n.score or 0.0) >= threshold]
        filtered.sort(key=lambda n: n.score or 0.0, reverse=True)
        return filtered[: self.top_k]
