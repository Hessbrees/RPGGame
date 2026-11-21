import hashlib
import json
import os
from pathlib import Path
import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore

FINGERPRINT_FILE = "rag_fingerprints.json"


class BaseRAG:
    """Klasa bazowa dla wszystkich modułów RAG."""

    COLLECTION_NAME: str = "base"
    DATA_DIR: str = "./data"

    def __init__(self, llm, embed_model):
        self.llm = llm
        self.embed_model = embed_model
        self.index = self._build_index()

    def _data_files(self) -> list[Path]:
        data_path = Path(self.DATA_DIR)
        if not data_path.is_dir():
            return []
        # SimpleDirectoryReader czyta nierekurencyjnie i pomija pliki ukryte.
        return sorted(f for f in data_path.iterdir() if f.is_file() and not f.name.startswith("."))

    def _data_fingerprint(self) -> str:
        """Odcisk zawartości plików i modelu embeddings; zmiana oznacza konieczność ponownego indeksowania."""
        digest = hashlib.sha1()
        digest.update(str(getattr(self.embed_model, "model_name", type(self.embed_model).__name__)).encode())
        for file in self._data_files():
            digest.update(file.name.encode())
            digest.update(file.read_bytes())
        return digest.hexdigest()

    def _build_index(self) -> VectorStoreIndex:
        chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection(self.COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=collection)

        if not self._data_files():
            return VectorStoreIndex.from_vector_store(vector_store, embed_model=self.embed_model)

        fingerprint_path = Path(chroma_path) / FINGERPRINT_FILE
        fingerprints = json.loads(fingerprint_path.read_text(encoding="utf-8")) if fingerprint_path.exists() else {}
        fingerprint = self._data_fingerprint()

        if collection.count() > 0 and fingerprints.get(self.COLLECTION_NAME) == fingerprint:
            return VectorStoreIndex.from_vector_store(vector_store, embed_model=self.embed_model)

        # Dane się zmieniły (lub kolekcja jest pusta/pochodzi sprzed odcisków): indeksujemy od zera, bez duplikatów.
        stale_ids = collection.get(include=[])["ids"]
        if stale_ids:
            collection.delete(ids=stale_ids)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        documents = SimpleDirectoryReader(input_files=[str(f) for f in self._data_files()]).load_data()
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=self.embed_model,
        )
        fingerprints[self.COLLECTION_NAME] = fingerprint
        fingerprint_path.write_text(json.dumps(fingerprints, indent=2), encoding="utf-8")
        return index

    def query(self, question: str) -> str:
        engine = self.index.as_query_engine(llm=self.llm)
        response = engine.query(question)
        return str(response)
