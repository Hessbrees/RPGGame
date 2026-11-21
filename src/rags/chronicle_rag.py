import json
from datetime import datetime
from pathlib import Path
from .base_rag import BaseRAG


class ChronicleRAG(BaseRAG):
    """
    Kronikarz RAG – pamięć całej opowieści.
    Odpowiada za:
    - Przeszłe wydarzenia, imiona NPC-ów spotkanych dawno temu, sojusze i zdrady.
    - Cykliczne kompresowanie dziennika i wyszukiwanie danych.
    - Toolcalling do zapisu nowych wpisów w historii rozgrywki.
    """

    COLLECTION_NAME = "chronicle"
    DATA_DIR = "./data/chronicle"
    JOURNAL_FILE = "./data/chronicle/journal.json"

    @classmethod
    def start_session(cls) -> Path | None:
        """Archiwizuje dziennik poprzedniej sesji (data/chronicle/archive/) i zaczyna z pustym. Zwraca ścieżkę archiwum."""
        journal_path = Path(cls.JOURNAL_FILE)
        if not journal_path.exists():
            return None
        archived = None
        try:
            has_entries = bool(json.loads(journal_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            has_entries = True  # uszkodzony plik też archiwizujemy, nie kasujemy
        if has_entries:
            archive_dir = journal_path.parent / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archived = archive_dir / f"journal_{datetime.now():%Y%m%d_%H%M%S}.json"
            journal_path.replace(archived)
        journal_path.write_text("[]", encoding="utf-8")
        return archived

    def entry_count(self) -> int:
        journal_path = Path(self.JOURNAL_FILE)
        if not journal_path.exists():
            return 0
        return len(json.loads(journal_path.read_text(encoding="utf-8")))

    def add_entry(self, entry: str) -> None:
        """Zapisuje nowe zdarzenie do dziennika rozgrywki."""
        journal_path = Path(self.JOURNAL_FILE)
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        entries: list = []
        if journal_path.exists():
            with open(journal_path, "r", encoding="utf-8") as f:
                entries = json.load(f)

        entries.append(entry)

        with open(journal_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def compress_journal(self) -> str:
        """
        Kompresuje dziennik – podsumowuje starsze wpisy za pomocą LLM,
        aby ograniczyć zużycie tokenów przy długich rozgrywkach.
        """
        journal_path = Path(self.JOURNAL_FILE)
        if not journal_path.exists():
            return "Brak wpisów do skompresowania."

        with open(journal_path, "r", encoding="utf-8") as f:
            entries: list = json.load(f)

        if len(entries) < 10:
            return "Za mało wpisów do kompresji."

        old_entries = entries[:-5]
        recent_entries = entries[-5:]

        summary_prompt = (
            "Podsumuj zwięźle poniższe zdarzenia z rozgrywki RPG w maksymalnie 3 zdaniach:\n\n"
            + "\n".join(old_entries)
        )
        summary = str(self.llm.complete(summary_prompt))

        compressed = [f"[PODSUMOWANIE] {summary}"] + recent_entries
        with open(journal_path, "w", encoding="utf-8") as f:
            json.dump(compressed, f, ensure_ascii=False, indent=2)

        return summary
