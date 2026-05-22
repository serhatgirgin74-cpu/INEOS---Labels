# INEOS Label Catalogue Dashboard

Interactive dashboard for managing the INEOS label catalogue: complexity,
markets, lifecycle, and images. First iteration — designed to be refined.

## Contents

| Path | Purpose |
| --- | --- |
| `Label_Catalog_Rev03.xlsx` | Source workbook (Rev03) |
| `extract_data.py` | Parses workbook → `data/labels.csv`, `data/labels.json`, `data/images/*.png` |
| `app.py` | Streamlit dashboard (interactive) |
| `build_html.py` | Builds a single-file HTML dashboard with embedded data + images |
| `dist/labels_dashboard.html` | Portable HTML dashboard output |

## Quick start

```bash
pip install -r requirements.txt
python extract_data.py        # regenerate data/ if the workbook changes
streamlit run app.py          # interactive app at http://localhost:8501
python build_html.py          # rebuild dist/labels_dashboard.html
```

The HTML build is fully self-contained (data + base64 images embedded) so it
can be emailed or hosted anywhere — no server required.

## Features

- **Filters** — search, markets (any / all), complexity, module, lifecycle
  (PTO / SOP / ECO)
- **Gallery** — label thumbnails with market and complexity chips
- **Table** — sortable, exportable as filtered CSV
- **Group / isolate** — pick any dimension (module, prio, market, complexity…),
  see counts and drill into one group
- **Market matrix** — Module × Market heatmap

## Data extraction note

The workbook uses Excel's *image-in-cell* (rich data) feature. openpyxl does
not surface these images, so `extract_data.py` parses the underlying XML
(`xl/richData/*`, `xl/metadata.xml`, `xl/worksheets/sheet1.xml`) to map each
row to its embedded PNG.
