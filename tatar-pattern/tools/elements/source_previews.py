#!/usr/bin/env python3
"""Extract real embedded JPEGs from ARW; never develop, upscale or edit RAW/proxies."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Датасет/Элементы"


def largest_jpeg(data):
    candidates = []
    # Camera previews start with APP0, APP1, DQT or DHT. Validate each payload.
    for marker in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb", b"\xff\xd8\xff\xc4"):
        offset = data.find(marker)
        while offset >= 0:
            end = data.find(b"\xff\xd9", offset + 4)
            if end >= 0:
                payload = data[offset:end + 2]
                try:
                    with Image.open(io.BytesIO(payload)) as im:
                        size = im.size
                        im.verify()
                    candidates.append((size[0] * size[1], offset, payload, size))
                except (OSError, ValueError):
                    pass
            offset = data.find(marker, offset + 4)
    if not candidates:
        raise ValueError("No valid embedded JPEG in RAW")
    return max(candidates, key=lambda item: item[0])


def signature(im):
    a = np.asarray(im.convert("L").resize((64, 64)), dtype=float)
    return (a - a.mean()) / max(a.std(), 1.0)


def extract(raw, proxy, destination):
    data = raw.read_bytes()
    _, offset, payload, size = largest_jpeg(data)
    with Image.open(io.BytesIO(payload)) as original, Image.open(proxy) as small:
        small = ImageOps.exif_transpose(small)
        target = signature(small)
        distances = []
        for angle in (0, 90, 180, 270):
            rotated = original.rotate(angle, expand=True)
            if abs(rotated.width / rotated.height - small.width / small.height) > 0.03:
                continue
            distances.append((float(np.mean((signature(rotated) - target) ** 2)), angle))
        if not distances:
            raise ValueError(f"Preview/proxy aspect mismatch: {raw.name}")
        distance, angle = min(distances)
        if distance > 0.15:
            raise ValueError(f"Preview/proxy content mismatch: {raw.name}: {distance:.3f}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {"source_raw": str(raw.relative_to(ROOT)), "source_raw_sha256": hashlib.sha256(data).hexdigest(),
            "preview_file": str(destination.relative_to(ROOT)), "jpeg_offset": offset,
            "preview_sha256": hashlib.sha256(payload).hexdigest(), "native_size": list(size),
            "rotation_ccw": angle, "proxy_comparison_mse": round(distance, 6),
            "method": "largest verified camera JPEG embedded in ARW; no resampling or AI"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", nargs="+", help="Otherwise use current manual candidate frames")
    args = parser.parse_args()
    frames = set(args.frames or [r["frame"] for r in csv.DictReader((OUT / "manual_candidates.tsv").open(encoding="utf-8"), delimiter="\t")])
    sources = {}
    for path in (ROOT / "Датасет/Разметка/01.09.2026").glob("*/annotations.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8-sig")):
            sources[row["frame"]] = (row, path.parent.name)
    index_path = OUT / "source_previews/index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for frame in sorted(frames):
        row, location = sources[frame]
        index[frame] = extract(ROOT / "Датасет/Исходные изображения" / row["file"],
                               ROOT / "Датасет/Прокси/01.09.2026" / location / (frame + ".jpg"),
                               OUT / "source_previews" / (frame + ".jpg"))
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"extracted": len(frames), "indexed": len(index),
                      "native_sizes": sorted({str(index[f]["native_size"]) for f in frames}),
                      "maximum_proxy_mse": max(index[f]["proxy_comparison_mse"] for f in frames)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
