import html
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ImageRecord:
    """Metadane pojedynczej ilustracji – zapewniają powtarzalność (prompt, seed, model, LoRA)."""

    index: int
    turn: int
    prompt: str
    negative_prompt: str
    seed: int
    model_id: str
    loras: list[str] = field(default_factory=list)
    scene: dict = field(default_factory=dict)
    image_file: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class Gallery:
    """Zapisuje obrazy wraz z metadanymi (index.jsonl) i buduje prostą galerię HTML."""

    def __init__(self, output_dir: str):
        self.dir = Path(output_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.jsonl"

    def __len__(self) -> int:
        return len(self.records())

    def records(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        with open(self.index_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def save(self, image, record: ImageRecord) -> Path:
        record.image_file = f"turn_{record.turn:03d}_{record.index:03d}.png"
        path = self.dir / record.image_file
        image.save(path)
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return path

    def build_html(self) -> Path:
        """Generuje galerię HTML w kolejności tur (kronika w obrazach)."""
        cards = []
        for rec in self.records():
            scene = rec.get("scene", {})
            cards.append(
                "<figure>"
                f"<img src='{html.escape(rec['image_file'])}' width='384'>"
                f"<figcaption><b>Tura {rec['turn']}</b> (ważność {scene.get('importance', '?')})<br>"
                f"{html.escape(scene.get('source_text', '')[:300])}</figcaption>"
                "</figure>"
            )
        page = (
            "<!doctype html><meta charset='utf-8'><title>RPGGame - galeria</title>"
            "<style>body{background:#111;color:#ddd;font-family:sans-serif}"
            "figure{display:inline-block;width:384px;margin:12px;vertical-align:top}"
            "figcaption{font-size:13px}</style><h1>RPGGame - ilustrowana kronika</h1>"
            + "".join(cards)
        )
        path = self.dir / "gallery.html"
        path.write_text(page, encoding="utf-8")
        return path
