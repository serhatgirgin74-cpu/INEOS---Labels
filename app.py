"""INEOS Label Catalogue — Streamlit dashboard.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import ast
import base64
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
IMG_DIR = DATA_DIR / "images"
GUIDE_DIR = DATA_DIR / "guide_pages_jpg"
GUIDE_INDEX = DATA_DIR / "guide_index.json"

MARKETS = ["PU", "Chassis-Cab", "ROW", "GCC", "Australia", "Canada / Mexico", "US", "EU"]
COMPLEXITY = ["Procured", "Print in house", "Engraving or riveting", "Self destructive", "Removable"]
QTY_COL = "Quantity per           vehicle"

st.set_page_config(page_title="INEOS Label Catalogue", page_icon="🏷️", layout="wide")


@st.cache_data
def load() -> pd.DataFrame:
    csv_path = DATA_DIR / "labels.csv"
    if not csv_path.exists():
        st.error(
            "Catalogue data not found. Run `python extract_data.py` to "
            "regenerate `data/labels.csv` and `data/images/`."
        )
        st.stop()
    df = pd.read_csv(csv_path).fillna("")
    for c in ["markets", "complexity"]:
        df[c] = df[c].apply(lambda v: ast.literal_eval(v) if isinstance(v, str) and v.startswith("[") else [])
    for c in MARKETS + COMPLEXITY + ['PTO "engineering vehicle"', 'SOP "saleable vehicle"', "Release started (only ECO)"]:
        if c in df.columns:
            df[c] = df[c].astype(str).isin({"True", "true", "1"})
    df["Quantity"] = pd.to_numeric(df[QTY_COL], errors="coerce")
    return df


@st.cache_data
def guide_index() -> dict[str, list[int]]:
    if not GUIDE_INDEX.exists():
        return {}
    return json.loads(GUIDE_INDEX.read_text())


@st.cache_data
def img_b64(filename: str) -> str | None:
    if not filename:
        return None
    p = IMG_DIR / filename
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode("ascii")


@st.cache_data
def guide_page_b64(page: int) -> tuple[str, str] | None:
    """Return (mime, b64) for a guide page, or None."""
    for ext, mime in [("jpg", "image/jpeg"), ("png", "image/png")]:
        p = GUIDE_DIR / f"page-{page:02d}.{ext}"
        if p.exists():
            return mime, base64.b64encode(p.read_bytes()).decode("ascii")
    return None


def fallback_image_src(part: str) -> str | None:
    """For rows with no embedded label image, use a guide page as a stand-in."""
    pages = guide_index().get(part, [])
    detail = [p for p in pages if p > 7]
    candidate = detail[0] if detail else (pages[0] if pages else None)
    if candidate is None:
        return None
    page = guide_page_b64(candidate)
    if page is None:
        return None
    mime, b64 = page
    return f"data:{mime};base64,{b64}"



df = load()

# ─── Header ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:space-between;
                border-bottom:3px solid #0b3d91;padding-bottom:.5rem;margin-bottom:1rem;">
      <div>
        <h1 style="margin:0;color:#0b3d91;">INEOS Label Catalogue</h1>
        <div style="color:#666;font-size:0.9rem;">Rev03 — interactive dashboard for label managment</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar filters ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    search = st.text_input("Search (part number, name, notes)", "")

    sel_markets = st.multiselect("Markets", MARKETS, default=[])
    market_logic = st.radio("Market match", ["Any selected", "All selected"], horizontal=True, index=0)

    sel_complexity = st.multiselect("Complexity / process", COMPLEXITY, default=[])

    modules = sorted([m for m in df["MODULE"].unique() if m])
    sel_modules = st.multiselect("Module", modules, default=[])

    st.divider()
    st.caption("Lifecycle")
    only_pto = st.checkbox('PTO ("engineering vehicle")', value=False)
    only_sop = st.checkbox('SOP ("saleable vehicle")', value=False)
    only_eco = st.checkbox("Release started (ECO)", value=False)

# ─── Apply filters ─────────────────────────────────────────────────────────
f = df.copy()

if search:
    s = search.lower()
    mask = (
        f["Part number"].str.lower().str.contains(s, na=False)
        | f["ITEM Name"].str.lower().str.contains(s, na=False)
        | f["notes"].str.lower().str.contains(s, na=False)
        | f["Catalogue number"].astype(str).str.lower().str.contains(s, na=False)
    )
    f = f[mask]

if sel_markets:
    if market_logic == "All selected":
        f = f[f["markets"].apply(lambda lst: all(m in lst for m in sel_markets))]
    else:
        f = f[f["markets"].apply(lambda lst: any(m in lst for m in sel_markets))]

if sel_complexity:
    f = f[f["complexity"].apply(lambda lst: any(c in lst for c in sel_complexity))]

if sel_modules:
    f = f[f["MODULE"].isin(sel_modules)]

if only_pto:
    f = f[f['PTO "engineering vehicle"']]
if only_sop:
    f = f[f['SOP "saleable vehicle"']]
if only_eco:
    f = f[f["Release started (only ECO)"]]

# ─── KPIs ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Labels (filtered)", f"{len(f)} / {len(df)}")
k2.metric("Modules", f["MODULE"].replace("", pd.NA).nunique())
k3.metric("Markets covered", len({m for lst in f["markets"] for m in lst}))
k4.metric("SOP-ready", int(f['SOP "saleable vehicle"'].sum()))
k5.metric("Self-destructive", int(f["Self destructive"].sum()))

# ─── Tabs ─────────────────────────────────────────────────────────────────
tab_gallery, tab_table, tab_group, tab_matrix = st.tabs(["Gallery", "Table", "Group / isolate", "Market matrix"])

# ─── Installation-guide dialog (modal) ────────────────────────────────────
@st.dialog("Installation guide", width="large")
def show_guide(part: str, name: str):
    pages = guide_index().get(part, [])
    st.markdown(f"**{part}** — {name}")
    if not pages:
        st.info(
            "No matching page found in the manufacturers' guide for this label. "
            "It may be a deprecated part or a label without a fitment guide entry."
        )
        return
    st.caption(f"Found on {len(pages)} guide page(s): {', '.join(str(p) for p in pages)}")
    tabs = st.tabs([f"Page {p}" for p in pages])
    for t, p in zip(tabs, pages):
        with t:
            page = guide_page_b64(p)
            if page:
                mime, b64 = page
                st.markdown(
                    f'<img src="data:{mime};base64,{b64}" '
                    f'style="width:100%;border:1px solid #e3e7ef;border-radius:6px;" />',
                    unsafe_allow_html=True,
                )
            else:
                st.warning(f"Page {p} not rendered.")


# Compact-card CSS — applied once
st.markdown(
    """
    <style>
      .lbl-card { background:#fff; border:1px solid #e3e7ef; border-radius:8px; padding:.45rem;
                  margin-bottom:.45rem; box-shadow:0 1px 2px rgba(0,0,0,0.03); }
      .lbl-img { width:100%; height:90px; object-fit:contain; background:#f7f7f9;
                 border-radius:4px; display:block; }
      .lbl-img-empty { height:90px; display:flex; align-items:center; justify-content:center;
                       background:#f0f0f3; color:#aaa; font-size:.7rem; border-radius:4px; }
      .lbl-part { font-weight:600; color:#0b3d91; font-size:.78rem; margin-top:.3rem; line-height:1.15; }
      .lbl-name { color:#444; font-size:.7rem; line-height:1.2; margin-top:.1rem;
                  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
      .lbl-chips { margin-top:.25rem; }
      .lbl-chip  { display:inline-block; background:#0b3d91; color:#fff; border-radius:8px;
                   padding:1px 6px; font-size:.6rem; margin:1px 2px 1px 0; }
      .lbl-chip.gray { background:#eef0f4; color:#4a5266; }
      .lbl-meta { color:#888; font-size:.65rem; margin-top:.2rem; }
      div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
          padding: .15rem .4rem; font-size:.7rem; min-height: 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# Gallery — compact visual cards
with tab_gallery:
    if f.empty:
        st.info("No labels match the current filters.")
    else:
        cols_per_row = st.select_slider("Cards per row", options=[3, 4, 5, 6], value=5)
        rows = [f.iloc[i : i + cols_per_row] for i in range(0, len(f), cols_per_row)]
        for ri, chunk in enumerate(rows):
            cols = st.columns(cols_per_row)
            for ci, (col, (_, row)) in enumerate(zip(cols, chunk.iterrows())):
                with col:
                    b64 = img_b64(row["image"])
                    img_src = (
                        f"data:image/png;base64,{b64}" if b64 else fallback_image_src(row["Part number"])
                    )
                    img_html = (
                        f'<img class="lbl-img" src="{img_src}" />'
                        if img_src
                        else '<div class="lbl-img-empty">no image</div>'
                    )
                    chips = "".join(
                        f'<span class="lbl-chip">{m}</span>' for m in row["markets"]
                    )
                    cchips = "".join(
                        f'<span class="lbl-chip gray">{c}</span>' for c in row["complexity"]
                    )
                    cat = row["Catalogue number"]
                    meta = f"Cat {cat} · {row['MODULE']}" if cat or row["MODULE"] else ""
                    st.markdown(
                        f'<div class="lbl-card">{img_html}'
                        f'<div class="lbl-part">{row["Part number"]}</div>'
                        f'<div class="lbl-name">{row["ITEM Name"]}</div>'
                        f'<div class="lbl-chips">{chips}{cchips}</div>'
                        f'<div class="lbl-meta">{meta}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    bcols = st.columns(2)
                    has_guide = bool(guide_index().get(row["Part number"]))
                    if bcols[0].button(
                        "📖 Guide" if has_guide else "📖 —",
                        key=f"g_{ri}_{ci}",
                        use_container_width=True,
                        disabled=not has_guide,
                    ):
                        show_guide(row["Part number"], row["ITEM Name"])
                    with bcols[1].popover("ℹ️", use_container_width=True):
                        st.markdown(f"**{row['Part number']}**")
                        st.caption(row["ITEM Name"])
                        st.write(f"**Module:** {row['MODULE'] or '—'}")
                        st.write(f"**Catalogue #:** {row['Catalogue number'] or '—'}")
                        st.write(f"**Qty/vehicle:** {row['Quantity'] if pd.notna(row['Quantity']) else '—'}")
                        st.write(f"**Prio:** {row['Prio'] or '—'}")
                        st.write(f"**Drawings:** {row['Drawings chek'] or '—'}")
                        life = [k for k, v in [("PTO", row['PTO "engineering vehicle"']),
                                              ("SOP", row['SOP "saleable vehicle"']),
                                              ("ECO", row['Release started (only ECO)'])] if v]
                        st.write(f"**Lifecycle:** {', '.join(life) or '—'}")
                        if row["notes"]:
                            st.write(f"**Notes:** {row['notes']}")

# Table — sortable / exportable
with tab_table:
    cols = [
        "Part number", "ITEM Name", "MODULE", "Catalogue number", "Quantity",
        "markets", "complexity", "Prio",
        'PTO "engineering vehicle"', 'SOP "saleable vehicle"', "Release started (only ECO)",
        "Drawings chek", "notes",
    ]
    view = f[[c for c in cols if c in f.columns]].copy()
    view["markets"] = view["markets"].apply(lambda lst: ", ".join(lst))
    view["complexity"] = view["complexity"].apply(lambda lst: ", ".join(lst))
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered CSV",
        view.to_csv(index=False).encode("utf-8"),
        file_name="labels_filtered.csv",
        mime="text/csv",
    )

# Group / isolate — pick a grouping dimension and see counts + drill-down
with tab_group:
    dim = st.selectbox(
        "Group by",
        ["MODULE", "Prio", "Catalogue number", "Drawings chek"]
        + [f"Market: {m}" for m in MARKETS]
        + [f"Complexity: {c}" for c in COMPLEXITY],
    )

    if dim.startswith("Market: "):
        m = dim.split(": ", 1)[1]
        agg = f.assign(_g=f["markets"].apply(lambda lst: "Yes" if m in lst else "No")).groupby("_g").size()
    elif dim.startswith("Complexity: "):
        c = dim.split(": ", 1)[1]
        agg = f.assign(_g=f["complexity"].apply(lambda lst: "Yes" if c in lst else "No")).groupby("_g").size()
    else:
        agg = f[dim].replace("", "(blank)").groupby(f[dim].replace("", "(blank)")).size()

    agg = agg.sort_values(ascending=False).rename("count").to_frame()
    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(agg, use_container_width=True)
    with c2:
        st.bar_chart(agg)

    pick = st.selectbox("Isolate group", ["(none)"] + agg.index.astype(str).tolist())
    if pick != "(none)":
        if dim.startswith("Market: "):
            m = dim.split(": ", 1)[1]
            sub = f[f["markets"].apply(lambda lst: (m in lst) == (pick == "Yes"))]
        elif dim.startswith("Complexity: "):
            c = dim.split(": ", 1)[1]
            sub = f[f["complexity"].apply(lambda lst: (c in lst) == (pick == "Yes"))]
        else:
            sub = f[f[dim].replace("", "(blank)") == pick]
        st.caption(f"{len(sub)} labels in group **{pick}**")
        st.dataframe(
            sub[["Part number", "ITEM Name", "MODULE", "markets", "complexity"]].assign(
                markets=lambda d: d["markets"].apply(", ".join),
                complexity=lambda d: d["complexity"].apply(", ".join),
            ),
            hide_index=True,
            use_container_width=True,
        )

# Market matrix — module × market heatmap
with tab_matrix:
    mat = pd.DataFrame(0, index=sorted(f["MODULE"].replace("", "(blank)").unique()), columns=MARKETS, dtype=int)
    for _, row in f.iterrows():
        mod = row["MODULE"] or "(blank)"
        for m in row["markets"]:
            mat.at[mod, m] += 1
    st.caption("Number of labels per Module × Market")
    max_v = max(int(mat.values.max()), 1)

    def shade(v):
        if not isinstance(v, (int, float)) or v <= 0:
            return ""
        a = 0.15 + 0.75 * (v / max_v)
        text = "white" if a > 0.55 else "#1a2233"
        return f"background-color: rgba(11,61,145,{a:.2f}); color: {text};"

    st.dataframe(mat.style.map(shade), use_container_width=True)
