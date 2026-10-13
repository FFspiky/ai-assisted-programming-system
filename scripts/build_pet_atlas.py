"""Compile existing upstream sprite cells, without changing their artwork.

Usage: python scripts/build_pet_atlas.py /path/to/codex-deepseek-pet
The source checkout must be at the revision documented in ATTRIBUTION.md.
"""

import argparse
import json
from pathlib import Path

from PIL import Image

# Frame order follows the upstream motion timelines, keeping complete characters.
CLIPS = {
    "idle": ("idle-front", [0, 1], [4800, 180], True),
    "drag": ("inbetween-jump", [13], [1000], True),
    "fall": ("inbetween-jump", [19], [1000], True),
    "land": (
        "inbetween-jump",
        [21, 23, 25, 45, 27, 46, 29, 47, 31],
        [80, 90, 70, 60, 70, 60, 80, 80, 180],
        False,
    ),
    "wave": ("dense-wave", list(range(1, 32, 2)), [90] * 16, False),
    "think": ("story-token", [0, 1, 2, 1], [650, 300, 650, 300], True),
    "talk": ("dense-wave", [9, 11, 13, 15, 13, 11, 9], [500, 160, 180, 300, 180, 160, 500], True),
    "dance": ("dense-dance", list(range(1, 32, 2)), [110] * 16, False),
    "eat": ("story-token", list(range(0, 16)), [160] * 16, False),
    "sleep": (
        "inbetween-sleep",
        [1, 3, 5, 7, 35, 9, 11, 37, 13, 38, 17, 39, 19, 21, 23, 25, 27, 29, 31],
        [160] * 19,
        False,
    ),
    "wake": (
        "inbetween-sleep",
        [31, 29, 27, 25, 23, 21, 19, 39, 17, 38, 13, 37, 11, 9, 7, 1],
        [100] * 16,
        False,
    ),
    "jump": (
        "inbetween-jump",
        [0, 1, 3, 34, 5, 35, 7, 36, 9, 11, 13, 15, 17, 19, 21, 23, 25, 45, 27, 46, 29, 47, 31],
        [75] * 23,
        False,
    ),
}


def build(source, destination):
    cells = []
    indexes = {}
    images = {}
    clips = {}
    size, columns = 256, 8
    for name, (atlas, frames, durations, loop) in CLIPS.items():
        if atlas not in images:
            with Image.open(source / "assets" / "whale" / f"{atlas}.png") as original:
                images[atlas] = original.convert("RGBA")
        image = images[atlas]
        source_columns = 2 if atlas == "idle-front" else 4
        cell = image.width // source_columns
        packed = []
        for frame in frames:
            key = (atlas, frame)
            if key not in indexes:
                x, y = frame % source_columns * cell, frame // source_columns * cell
                assert y + cell <= image.height
                tile = image.crop((x, y, x + cell, y + cell)).convert("RGBA")
                indexes[key] = len(cells)
                cells.append(tile.resize((size, size), Image.Resampling.LANCZOS))
            packed.append(indexes[key])
        clips[name] = {"frames": packed, "durations": durations, "loop": loop}
    rows = (len(cells) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * size, rows * size))
    for i, tile in enumerate(cells):
        sheet.paste(tile, (i % columns * size, i // columns * size))
    destination.mkdir(parents=True, exist_ok=True)
    sheet.save(destination / "actions.webp", lossless=True, method=6)
    manifest = {"cell": size, "columns": columns, "rows": rows, "clips": clips}
    (destination / "actions.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"Compiled {len(cells)} frames, {len(clips)} actions: {(destination / 'actions.webp').stat().st_size:,} bytes"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    build(args.source, Path(__file__).resolve().parents[1] / "static/images/dafeiyu")
