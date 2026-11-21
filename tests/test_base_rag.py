import chromadb
from llama_index.core.embeddings import MockEmbedding

from src.rags.base_rag import BaseRAG


def make_rag(tmp_path, monkeypatch, text="Pierwszy dokument o świecie gry."):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    (data / "a.md").write_text(text, encoding="utf-8")
    monkeypatch.setenv("CHROMA_DB_PATH", str(tmp_path / "chroma"))

    class Rag(BaseRAG):
        COLLECTION_NAME = "test_rag"
        DATA_DIR = str(data)

    return Rag(llm=None, embed_model=MockEmbedding(embed_dim=8))


def stored(tmp_path):
    collection = chromadb.PersistentClient(path=str(tmp_path / "chroma")).get_collection("test_rag")
    return collection.get(include=["documents"])["documents"]


def test_restart_does_not_duplicate(tmp_path, monkeypatch):
    make_rag(tmp_path, monkeypatch)
    first = len(stored(tmp_path))
    for _ in range(3):
        make_rag(tmp_path, monkeypatch)
    assert len(stored(tmp_path)) == first


def test_changed_data_is_reindexed_without_leftovers(tmp_path, monkeypatch):
    make_rag(tmp_path, monkeypatch, "Stara treść.")
    make_rag(tmp_path, monkeypatch, "Nowa treść.")
    docs = stored(tmp_path)
    assert any("Nowa treść." in d for d in docs)
    assert not any("Stara treść." in d for d in docs)


def test_legacy_duplicates_are_cleaned(tmp_path, monkeypatch):
    make_rag(tmp_path, monkeypatch)
    clean = len(stored(tmp_path))
    # Stan sprzed poprawki: te same fragmenty zaindeksowane wielokrotnie i brak odcisku.
    collection = chromadb.PersistentClient(path=str(tmp_path / "chroma")).get_collection("test_rag")
    collection.add(ids=["x1", "x2"], documents=["Pierwszy dokument o świecie gry."] * 2, embeddings=[[0.1] * 8] * 2)
    (tmp_path / "chroma" / "rag_fingerprints.json").unlink()
    make_rag(tmp_path, monkeypatch)
    assert len(stored(tmp_path)) == clean


def test_ignores_subdirectories(tmp_path, monkeypatch):
    rag = make_rag(tmp_path, monkeypatch)
    (tmp_path / "data" / "archive").mkdir()
    (tmp_path / "data" / "archive" / "old.md").write_text("zarchiwizowane", encoding="utf-8")
    make_rag(tmp_path, monkeypatch)
    assert not any("zarchiwizowane" in d for d in stored(tmp_path))
    assert rag.index is not None
