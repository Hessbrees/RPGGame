"""
Przygotowanie zbioru treningowego LoRA.

Wejście:  katalog z obrazami (jpg/png/webp). Opisy (po angielsku) wybierane są w kolejności:
          1) plik .txt o tej samej nazwie, 2) reguły z --caption_rules (pierwsze dopasowanie nazwy pliku),
          3) --default_caption.
Wyjście:  obrazy przeskalowane do kwadratu + metadata.jsonl
          ({"file_name", "text": "<trigger>, <opis>", "split": "train"|"val", "source"}).

Obrazy panoramiczne (np. 2304x1536) nie są tylko środkowo przycinane: z każdego powstaje --wide_crops
kwadratowych wycinków rozmieszczonych równomiernie (więcej materiału, mniej utraconej treści).
Wycinki jednego obrazu zawsze trafiają do tego samego podziału (brak wycieku train -> val).

Przykład:
  python -m scripts.prepare_dataset --src raw/style --dst data/training/style --trigger rpgstyle ^
         --caption_rules data/training/caption_rules.json
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MIN_RECOMMENDED = 15


def square_crops(image: Image.Image, size: int, n_wide: int) -> list[Image.Image]:
    """Zwraca kwadratowe wycinki: 1 (środek) dla obrazów kwadratowych, n_wide równomiernie dla panoram."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    side = min(image.size)
    long_side = max(image.size)
    count = n_wide if long_side > 1.2 * side and n_wide > 1 else 1

    crops = []
    for k in range(count):
        if count == 1:
            offset = (long_side - side) // 2
        else:
            offset = round(k * (long_side - side) / (count - 1))
        box = (offset, 0, offset + side, side) if image.width >= image.height else (0, offset, side, offset + side)
        crops.append(image.crop(box).resize((size, size), Image.Resampling.LANCZOS))
    return crops


def load_rules(path: str | None) -> list[dict]:
    if not path:
        return []
    return json.loads(Path(path).read_text(encoding="utf-8"))


def caption_for(path: Path, rules: list[dict], default: str) -> str:
    caption_file = path.with_suffix(".txt")
    if caption_file.exists():
        return caption_file.read_text(encoding="utf-8").strip()
    name = path.name.lower()
    for rule in rules:
        if rule["match"].lower() in name:
            return rule["caption"]
    return default


def main():
    parser = argparse.ArgumentParser(description="Przygotowanie zbioru treningowego LoRA")
    parser.add_argument("--src", required=True, help="Katalog z oryginalnymi obrazami")
    parser.add_argument("--dst", required=True, help="Katalog wyjściowy zbioru")
    parser.add_argument("--trigger", default="", help="Token aktywujący dodawany na początku opisu")
    parser.add_argument("--default_caption", default="", help="Opis użyty, gdy brak innych źródeł")
    parser.add_argument("--caption_rules", default=None, help='JSON: [{"match": ..., "caption": ...}]')
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--wide_crops", type=int, default=2, help="Liczba wycinków z obrazu panoramicznego")
    parser.add_argument("--val_every", type=int, default=10,
                        help="Co n-ty obraz w każdej grupie opisów trafia do walidacji (0 = brak walidacji)")
    args = parser.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    rules = load_rules(args.caption_rules)

    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTENSIONS)
    if not files:
        raise SystemExit(f"Brak obrazów w {src}")

    # Podział train/val na poziomie obrazu źródłowego, rozwarstwiony wg grup opisów.
    captions = {p: caption_for(p, rules, args.default_caption) for p in files}
    groups: dict[str, list[Path]] = defaultdict(list)
    for p, cap in captions.items():
        groups[cap].append(p)
    val_files: set[Path] = set()
    if args.val_every > 0:
        for members in groups.values():
            val_files.update(m for i, m in enumerate(members) if (i + 1) % args.val_every == 0)

    rows, index = [], 0
    for path in files:
        caption = captions[path]
        text = ", ".join(part for part in (args.trigger, caption) if part)
        if not text:
            raise SystemExit(f"Brak opisu dla {path.name}: podaj --caption_rules, --default_caption lub plik .txt")

        with Image.open(path) as image:
            for crop in square_crops(image, args.resolution, args.wide_crops):
                out_name = f"{index:04d}.png"
                crop.save(dst / out_name)
                rows.append({
                    "file_name": out_name,
                    "text": text,
                    "split": "val" if path in val_files else "train",
                    "source": path.name,
                })
                index += 1

    with open(dst / "metadata.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_val = sum(r["split"] == "val" for r in rows)
    print(f"Zapisano {len(rows)} obrazów do {dst} (train: {len(rows) - n_val}, val: {n_val})")
    for cap, members in groups.items():
        print(f"  {len(members):3d} źródłowych: {cap}")
    if len(rows) - n_val < MIN_RECOMMENDED:
        print(f"UWAGA: zalecane co najmniej {MIN_RECOMMENDED} obrazów treningowych; ryzyko przeuczenia.")


if __name__ == "__main__":
    main()
