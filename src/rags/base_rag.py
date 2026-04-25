import os
from pathlib import Path
import chromadb
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore


class BaseRAG:
    """Klasa bazowa dla wszystkich modułów RAG."""

    COLLECTION_NAME: str = "base"
    DATA_DIR: str = "./data"

    def __init__(self, llm, embed_model):
        self.llm = llm
        self.embed_model = embed_model
        self.index = self._build_index()

    def _build_index(self) -> VectorStoreIndex:
        chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection(self.COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        data_path = Path(self.DATA_DIR)
        if data_path.exists() and any(data_path.iterdir()):
            documents = SimpleDirectoryReader(str(data_path)).load_data()
            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=self.embed_model,
            )
        else:
            index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=self.embed_model,
            )

        return index

    def query(self, question: str) -> str:
        engine = self.index.as_query_engine(llm=self.llm)
        response = engine.query(question)
        return str(response)
