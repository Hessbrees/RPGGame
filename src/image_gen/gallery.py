import base64
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
        """Generuje samodzielny plik HTML (obrazy osadzone jako base64), więc działa po otwarciu z dowolnego miejsca."""
        cards = []
        for rec in self.records():
            image_path = self.dir / rec["image_file"]
            if not image_path.exists():
                continue
            data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            scene = rec.get("scene", {})
            loras = ", ".join(Path(p).parent.name + "/" + Path(p).name for p in rec.get("loras", [])) or "brak"
            cards.append(
                "<figure>"
                f"<img src='data:image/png;base64,{data}' alt='Tura {rec['turn']}' onclick=\"this.classList.toggle('zoom')\">"
                f"<figcaption><b>Tura {rec['turn']}</b> (ważność {scene.get('importance', '?')})<br>"
                f"{html.escape(scene.get('source_text', '')[:300])}"
                f"<details><summary>Prompt</summary><small>{html.escape(rec.get('prompt', ''))}</small><br>"
                f"<small>seed {rec.get('seed', '?')}, LoRA: {html.escape(loras)}</small></details></figcaption>"
                "</figure>"
            )
        body = "".join(cards) or "<p>Brak obrazów w tej sesji.</p>"
        page = (
            "<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>RPGGame - galeria</title><style>"
            "body{background:#111;color:#ddd;font-family:sans-serif;margin:0;padding:16px}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}"
            "figure{margin:0}img{width:100%;height:auto;border-radius:6px;cursor:zoom-in}"
            "img.zoom{position:fixed;inset:0;z-index:10;width:100vw;height:100vh;object-fit:contain;"
            "background:rgba(0,0,0,.92);border-radius:0;cursor:zoom-out}"
            "figcaption{font-size:13px;margin-top:6px}details{margin-top:6px;color:#aaa}"
            "</style></head><body><h1>RPGGame - ilustrowana kronika</h1>"
            f"<div class='grid'>{body}</div></body></html>"
        )
        path = self.dir / "gallery.html"
        path.write_text(page, encoding="utf-8")
        return path
