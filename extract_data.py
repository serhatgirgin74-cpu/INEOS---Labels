"""Extract label catalogue data + per-row images from the Excel workbook.

The workbook uses Excel's "image-in-cell" rich data feature. openpyxl does
not surface those images, so we parse the XML directly.

Outputs:
    data/labels.csv         - flat catalogue
    data/labels.json        - same data + image filename per row
    data/images/<part>.png  - extracted per-label image

Run ``python build_guide.py`` separately to (re)build the manufacturers'
guide index (``data/guide_index.json``) and per-page JPEGs
(``data/guide_pages_jpg/``).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

ROOT = Path(__file__).parent
XLSX = ROOT / "Label_Catalog_Rev03.xlsx"
DATA_DIR = ROOT / "data"
IMG_DIR = DATA_DIR / "images"

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rvr": "http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

MARKETS = ["PU", "Chassis-Cab", "ROW", "GCC", "Australia", "Canada / Mexico", "US", "EU"]
COMPLEXITY = ["Procured", "Print in house", "Engraving or riveting", "Self destructive", "Removable"]


def col_letter_to_index(letters: str) -> int:
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n


def cell_ref(ref: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def extract_images(zf: zipfile.ZipFile) -> dict[int, bytes]:
    """Return {rv_index (0-based) -> image bytes}."""
    # rId -> media path, from richValueRel rels
    rels_xml = ET.fromstring(zf.read("xl/richData/_rels/richValueRel.xml.rels"))
    rid_to_media: dict[str, str] = {}
    for rel in rels_xml.findall("pkg:Relationship", NS):
        rid_to_media[rel.attrib["Id"]] = rel.attrib["Target"].replace("../", "xl/")

    # rv index (0-based) -> rId, from richValueRel sequence order
    rvr_xml = ET.fromstring(zf.read("xl/richData/richValueRel.xml"))
    rels_in_order = [el.attrib[f"{{{NS['r']}}}id"] for el in rvr_xml.findall("rvr:rel", NS)]

    out: dict[int, bytes] = {}
    for idx, rid in enumerate(rels_in_order):
        path = rid_to_media.get(rid)
        if path:
            out[idx] = zf.read(path)
    return out


def cell_vm_map(zf: zipfile.ZipFile) -> dict[str, int]:
    """Return {cellRef -> vm value} on sheet1."""
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    pairs = re.findall(r'<c[^>]*r="([A-Z]+\d+)"[^>]*\bvm="(\d+)"', sheet)
    return {ref: int(vm) for ref, vm in pairs}


def vm_to_rv_index(zf: zipfile.ZipFile) -> dict[int, int]:
    """vm (1-based) -> rv index referenced by that metadata block."""
    md = ET.fromstring(zf.read("xl/metadata.xml"))
    mapping: dict[int, int] = {}
    fm = md.find("main:futureMetadata", NS)
    if fm is None:
        return mapping
    for i, bk in enumerate(fm.findall("main:bk", NS), start=1):
        rvb = bk.find(".//{http://schemas.microsoft.com/office/spreadsheetml/2017/richdata}rvb")
        if rvb is not None:
            mapping[i] = int(rvb.attrib["i"])
    return mapping


def clean_header(h):
    if h is None:
        return ""
    return str(h).replace("\n", " ").strip()


def main() -> None:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    IMG_DIR.mkdir(parents=True)

    # Read tabular data with pandas (header row 2)
    df = pd.read_excel(XLSX, sheet_name="Tabelle1", header=1)
    df.columns = [clean_header(c) for c in df.columns]
    # Drop rows without a part number
    df = df[df["Part number"].notna()].reset_index(drop=True)

    # Normalise market / complexity columns to bool
    for col in MARKETS + COMPLEXITY:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().isin({"x", "1", "true", "yes"})

    # PTO / SOP / Release flags - normalise to bool
    for col in ["PTO \"engineering vehicle\"", "SOP \"saleable vehicle\"", "Release started (only ECO)"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().isin({"x", "1", "true", "yes"})

    # Tidy strings
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).where(df[c].notna(), "").str.strip()
        df[c] = df[c].replace({"nan": "", "#VALUE!": ""})

    # Extract images and attach
    with zipfile.ZipFile(XLSX) as zf:
        images = extract_images(zf)
        cell_vm = cell_vm_map(zf)
        vm_rv = vm_to_rv_index(zf)

    # Build cell-row -> image bytes (column Z = Label)
    row_to_img: dict[int, bytes] = {}
    for ref, vm in cell_vm.items():
        col, row = cell_ref(ref)
        if col != "Z":
            continue
        rv_idx = vm_rv.get(vm)
        if rv_idx is None:
            continue
        img = images.get(rv_idx)
        if img is not None:
            row_to_img[row] = img

    # Sheet row 3 is df row 0 (header at row 2)
    image_filenames: list[str] = []
    for i, part in enumerate(df["Part number"].tolist()):
        sheet_row = i + 3
        img = row_to_img.get(sheet_row)
        if img is None:
            image_filenames.append("")
            continue
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(part)) or f"row_{sheet_row}"
        fname = f"{safe}.png"
        (IMG_DIR / fname).write_bytes(img)
        image_filenames.append(fname)

    df["image"] = image_filenames

    # Add derived columns
    df["markets"] = df[MARKETS].apply(
        lambda r: [m for m in MARKETS if r.get(m)], axis=1
    )
    df["complexity"] = df[COMPLEXITY].apply(
        lambda r: [c for c in COMPLEXITY if r.get(c)], axis=1
    )
    df["market_count"] = df["markets"].apply(len)
    df["complexity_count"] = df["complexity"].apply(len)

    # Persist
    df.to_csv(DATA_DIR / "labels.csv", index=False)
    records = df.to_dict(orient="records")
    (DATA_DIR / "labels.json").write_text(json.dumps(records, indent=2, default=str))

    print(f"Wrote {len(df)} rows, {sum(1 for f in image_filenames if f)} images to {DATA_DIR}")


if __name__ == "__main__":
    main()
