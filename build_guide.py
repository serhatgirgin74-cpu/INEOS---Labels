"""Build the manufacturers' guide index + per-page JPEG renders.

Requires ``poppler-utils`` (pdftoppm, pdftotext).

Outputs:
    data/guide_pages_jpg/page-NN.jpg   one image per PDF page
    data/guide_index.json              {part_number: [page numbers, ...]}
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
PDF = ROOT / "manufacturers_guide.pdf"
OUT_DIR = ROOT / "data" / "guide_pages_jpg"
OUT_INDEX = ROOT / "data" / "guide_index.json"
LABELS_CSV = ROOT / "data" / "labels.csv"


def render_pages(pdf: Path, out_dir: Path, dpi: int = 85, quality: int = 70) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    subprocess.run(
        ["pdftoppm", "-jpeg", "-jpegopt", f"quality={quality}", "-r", str(dpi),
         str(pdf), str(out_dir / "page")],
        check=True,
    )
    return len(list(out_dir.glob("page-*.jpg")))


def page_count(pdf: Path) -> int:
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True)
    for line in info.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise RuntimeError("pdfinfo did not return a page count")


def page_text(pdf: Path, n_pages: int) -> dict[int, str]:
    out = {}
    for i in range(1, n_pages + 1):
        r = subprocess.run(
            ["pdftotext", "-layout", "-f", str(i), "-l", str(i), str(pdf), "-"],
            capture_output=True, text=True, check=True,
        )
        out[i] = r.stdout
    return out


def part_variants(raw: str) -> set[str]:
    out: set[str] = set()
    for p in re.split(r"[\s,;\n/]+", str(raw)):
        p = p.strip()
        if not p:
            continue
        out.add(p)
        m = re.match(r"([A-Za-z]+)-0*(\d+)$", p)
        if m:
            prefix, num = m.group(1), m.group(2)
            out.add(f"{prefix}-{num}")
            out.add(f"{prefix}-{int(num)}")
            if prefix.upper() == "EI":
                out.add(f"El-{num}")
                out.add(f"El-{int(num)}")
    return out


def build_index(pages: dict[int, str], df: pd.DataFrame) -> dict[str, list[int]]:
    idx: dict[str, list[int]] = {}
    for _, row in df.iterrows():
        part = str(row["Part number"])
        cat = str(row["Catalogue number"]).strip()
        matched: set[int] = set()
        for v in part_variants(part):
            pat = re.compile(r"(?<![A-Za-z0-9-])" + re.escape(v) + r"(?![A-Za-z0-9])")
            for p, txt in pages.items():
                if pat.search(txt):
                    matched.add(p)
        if not matched and cat and cat != "nan":
            pat = re.compile(r"(?<![\d.])" + re.escape(cat) + r"(?![\d.])")
            for p, txt in pages.items():
                if pat.search(txt):
                    matched.add(p)
        idx[part] = sorted(matched)
    return idx


def main() -> None:
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF}. Place the manufacturers' guide PDF here.")
    if not LABELS_CSV.exists():
        raise SystemExit("Run extract_data.py first to produce data/labels.csv.")
    n_pages = page_count(PDF)
    rendered = render_pages(PDF, OUT_DIR)
    print(f"Rendered {rendered} pages → {OUT_DIR}")
    texts = page_text(PDF, n_pages)
    df = pd.read_csv(LABELS_CSV).fillna("")
    idx = build_index(texts, df)
    OUT_INDEX.write_text(json.dumps(idx, indent=2))
    matched = sum(1 for v in idx.values() if v)
    print(f"Indexed {matched}/{len(idx)} parts → {OUT_INDEX}")


if __name__ == "__main__":
    main()
