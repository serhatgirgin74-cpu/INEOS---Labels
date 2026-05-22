"""INEOS Label Catalogue — Streamlit dashboard.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import ast
import base64
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
IMG_DIR = DATA_DIR / "images"

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
def img_b64(filename: str) -> str | None:
    if not filename:
        return None
    p = IMG_DIR / filename
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode("ascii")


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

# Gallery — visual cards
with tab_gallery:
    if f.empty:
        st.info("No labels match the current filters.")
    else:
        cols_per_row = 3
        rows = [f.iloc[i : i + cols_per_row] for i in range(0, len(f), cols_per_row)]
        for chunk in rows:
            cols = st.columns(cols_per_row)
            for col, (_, row) in zip(cols, chunk.iterrows()):
                with col:
                    with st.container(border=True):
                        b64 = img_b64(row["image"])
                        if b64:
                            st.markdown(
                                f'<img src="data:image/png;base64,{b64}" '
                                f'style="width:100%;max-height:160px;object-fit:contain;'
                                f'background:#f7f7f9;border-radius:6px;" />',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                '<div style="height:160px;display:flex;align-items:center;'
                                'justify-content:center;background:#f0f0f3;color:#999;'
                                'border-radius:6px;">no image</div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(f"**{row['Part number']}**")
                        st.caption(row["ITEM Name"][:80])
                        chips = "".join(
                            f'<span style="display:inline-block;background:#0b3d91;color:white;'
                            f'border-radius:10px;padding:2px 8px;font-size:0.7rem;margin:2px;">{m}</span>'
                            for m in row["markets"]
                        )
                        if chips:
                            st.markdown(chips, unsafe_allow_html=True)
                        if row["complexity"]:
                            cchips = "".join(
                                f'<span style="display:inline-block;background:#e9ecef;color:#333;'
                                f'border-radius:10px;padding:2px 8px;font-size:0.7rem;margin:2px;">{c}</span>'
                                for c in row["complexity"]
                            )
                            st.markdown(cchips, unsafe_allow_html=True)
                        with st.expander("Details"):
                            st.write(f"**Module:** {row['MODULE'] or '—'}")
                            st.write(f"**Catalogue #:** {row['Catalogue number'] or '—'}")
                            st.write(f"**Quantity/vehicle:** {row['Quantity'] if pd.notna(row['Quantity']) else '—'}")
                            st.write(f"**Prio:** {row['Prio'] or '—'}")
                            st.write(f"**Drawings:** {row['Drawings chek'] or '—'}")
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
    st.dataframe(mat.style.background_gradient(cmap="Blues"), use_container_width=True)
