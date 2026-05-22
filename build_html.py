"""Build a single-file HTML dashboard (dist/labels_dashboard.html).

All data + images are embedded as JSON / base64 so the file is portable.
"""
from __future__ import annotations

import ast
import base64
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
IMG_DIR = DATA_DIR / "images"
OUT = ROOT / "dist" / "labels_dashboard.html"

MARKETS = ["PU", "Chassis-Cab", "ROW", "GCC", "Australia", "Canada / Mexico", "US", "EU"]
COMPLEXITY = ["Procured", "Print in house", "Engraving or riveting", "Self destructive", "Removable"]
QTY_COL = "Quantity per           vehicle"


def main() -> None:
    df = pd.read_csv(DATA_DIR / "labels.csv").fillna("")
    for c in ["markets", "complexity"]:
        df[c] = df[c].apply(lambda v: ast.literal_eval(v) if isinstance(v, str) and v.startswith("[") else [])
    for c in MARKETS + COMPLEXITY + ['PTO "engineering vehicle"', 'SOP "saleable vehicle"', "Release started (only ECO)"]:
        if c in df.columns:
            df[c] = df[c].astype(str).isin({"True", "true", "1"})

    records = []
    for _, r in df.iterrows():
        img_data = ""
        if r["image"]:
            p = IMG_DIR / r["image"]
            if p.exists():
                img_data = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
        records.append({
            "part": str(r["Part number"]),
            "name": str(r["ITEM Name"]),
            "module": str(r["MODULE"]),
            "catalogue": str(r["Catalogue number"]),
            "qty": str(r.get(QTY_COL, "")),
            "prio": str(r["Prio"]),
            "drawings": str(r["Drawings chek"]),
            "notes": str(r["notes"]),
            "markets": list(r["markets"]),
            "complexity": list(r["complexity"]),
            "pto": bool(r['PTO "engineering vehicle"']),
            "sop": bool(r['SOP "saleable vehicle"']),
            "eco": bool(r["Release started (only ECO)"]),
            "image": img_data,
        })

    payload = json.dumps({"records": records, "markets": MARKETS, "complexity": COMPLEXITY})

    html = HTML_TEMPLATE.replace("__DATA__", payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>INEOS Label Catalogue — Rev03</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  :root {
    --primary:#0b3d91; --primary-2:#1759c8; --bg:#f5f7fb; --card:#fff;
    --muted:#667085; --border:#e3e7ef; --chip:#eef2ff; --chip-text:#1e3a8a;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:#1a2233; }
  header { background:#fff; border-bottom:3px solid var(--primary); padding:.9rem 1.4rem;
           display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; color:var(--primary); font-size:1.35rem; }
  header .sub { color:var(--muted); font-size:.85rem; }
  .layout { display:grid; grid-template-columns:280px 1fr; gap:0; min-height:calc(100vh - 64px); }
  aside { background:#fff; border-right:1px solid var(--border); padding:1rem; overflow-y:auto; }
  aside h3 { margin:.6rem 0 .3rem; font-size:.85rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  main { padding:1.2rem 1.4rem; overflow-y:auto; }
  input[type=text], select { width:100%; padding:.45rem .6rem; border:1px solid var(--border);
                             border-radius:6px; font:inherit; background:#fff; }
  .check { display:block; padding:.18rem 0; font-size:.88rem; cursor:pointer; }
  .check input { margin-right:.45rem; }
  .kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:.8rem; margin-bottom:1rem; }
  .kpi { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:.7rem .9rem; }
  .kpi .v { font-size:1.4rem; font-weight:600; color:var(--primary); }
  .kpi .l { font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .tabs { display:flex; gap:0; border-bottom:1px solid var(--border); margin-bottom:1rem; }
  .tab { padding:.55rem 1rem; cursor:pointer; border-bottom:2px solid transparent; color:var(--muted); font-weight:500; }
  .tab.active { color:var(--primary); border-bottom-color:var(--primary); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:1rem; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; overflow:hidden;
          display:flex; flex-direction:column; transition:box-shadow .15s; }
  .card:hover { box-shadow:0 4px 14px rgba(11,61,145,0.10); }
  .card .img { aspect-ratio:16/9; background:#f7f7f9; display:flex; align-items:center; justify-content:center; }
  .card .img img { max-width:100%; max-height:100%; object-fit:contain; }
  .card .img.empty { color:#bbb; font-size:.85rem; }
  .card .body { padding:.6rem .8rem; flex:1; display:flex; flex-direction:column; gap:.35rem; }
  .card .part { font-weight:600; font-size:.92rem; color:var(--primary); }
  .card .name { font-size:.82rem; color:#333; line-height:1.3; }
  .chips { display:flex; flex-wrap:wrap; gap:.25rem; margin-top:.3rem; }
  .chip { background:var(--chip); color:var(--chip-text); border-radius:10px; padding:.1rem .55rem;
          font-size:.7rem; font-weight:500; }
  .chip.gray { background:#eef0f4; color:#4a5266; }
  .meta { font-size:.75rem; color:var(--muted); margin-top:.4rem; }
  table { width:100%; border-collapse:collapse; background:#fff; font-size:.85rem; }
  th, td { padding:.45rem .55rem; text-align:left; border-bottom:1px solid var(--border); vertical-align:top; }
  th { background:#f0f3f9; font-weight:600; color:#2c3650; position:sticky; top:0; cursor:pointer; }
  th:hover { background:#e6ecf7; }
  tr:hover td { background:#fafbfd; }
  .matrix td { text-align:center; }
  .matrix td.has { color:var(--primary); font-weight:600; }
  .hbar { display:flex; align-items:center; gap:.4rem; }
  .hbar .bar { height:14px; background:var(--primary-2); border-radius:3px; }
  .empty { padding:3rem; text-align:center; color:var(--muted); }
  .btn { display:inline-block; padding:.4rem .8rem; background:var(--primary); color:#fff;
         border:none; border-radius:6px; cursor:pointer; font:inherit; }
  .btn:hover { background:var(--primary-2); }
  .toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:.7rem; }
  details summary { cursor:pointer; color:var(--primary); font-size:.8rem; padding:.3rem 0; }
  details .det { font-size:.78rem; color:#444; line-height:1.5; }
</style>
</head>
<body>
<header>
  <div>
    <h1>INEOS Label Catalogue</h1>
    <div class="sub">Rev03 — interactive dashboard for label management</div>
  </div>
  <div class="sub" id="count-pill"></div>
</header>

<div class="layout">
  <aside>
    <h3>Search</h3>
    <input type="text" id="search" placeholder="Part number, name, notes…" />

    <h3>Markets</h3>
    <div id="markets"></div>
    <label class="check"><input type="radio" name="mlogic" value="any" checked /> Any selected</label>
    <label class="check"><input type="radio" name="mlogic" value="all" /> All selected</label>

    <h3>Complexity / process</h3>
    <div id="complexity"></div>

    <h3>Module</h3>
    <select id="module"><option value="">(all)</option></select>

    <h3>Lifecycle</h3>
    <label class="check"><input type="checkbox" id="pto" /> PTO (engineering vehicle)</label>
    <label class="check"><input type="checkbox" id="sop" /> SOP (saleable vehicle)</label>
    <label class="check"><input type="checkbox" id="eco" /> Release started (ECO)</label>

    <div style="margin-top:1rem;">
      <button class="btn" id="reset">Reset filters</button>
    </div>
  </aside>

  <main>
    <div class="kpis" id="kpis"></div>

    <div class="tabs">
      <div class="tab active" data-tab="gallery">Gallery</div>
      <div class="tab" data-tab="table">Table</div>
      <div class="tab" data-tab="group">Group / isolate</div>
      <div class="tab" data-tab="matrix">Market matrix</div>
    </div>

    <section id="view-gallery"></section>
    <section id="view-table" style="display:none;"></section>
    <section id="view-group" style="display:none;"></section>
    <section id="view-matrix" style="display:none;"></section>
  </main>
</div>

<script id="payload" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const state = {
  search: '', markets: new Set(), complexity: new Set(),
  mlogic: 'any', module: '', pto: false, sop: false, eco: false,
  sort: {col:null, dir:1}, groupBy: 'module', isolate: '',
};

// Build market + complexity checkboxes
const mEl = document.getElementById('markets');
DATA.markets.forEach(m => {
  const l = document.createElement('label'); l.className = 'check';
  l.innerHTML = `<input type="checkbox" value="${m}" /> ${m}`;
  l.querySelector('input').addEventListener('change', e => {
    e.target.checked ? state.markets.add(m) : state.markets.delete(m); render();
  });
  mEl.appendChild(l);
});
const cEl = document.getElementById('complexity');
DATA.complexity.forEach(c => {
  const l = document.createElement('label'); l.className = 'check';
  l.innerHTML = `<input type="checkbox" value="${c}" /> ${c}`;
  l.querySelector('input').addEventListener('change', e => {
    e.target.checked ? state.complexity.add(c) : state.complexity.delete(c); render();
  });
  cEl.appendChild(l);
});

// Module dropdown
const modSel = document.getElementById('module');
[...new Set(DATA.records.map(r => r.module).filter(Boolean))].sort().forEach(m => {
  const o = document.createElement('option'); o.value = m; o.textContent = m; modSel.appendChild(o);
});

// Input bindings
document.getElementById('search').addEventListener('input', e => { state.search = e.target.value.toLowerCase(); render(); });
document.getElementById('module').addEventListener('change', e => { state.module = e.target.value; render(); });
document.querySelectorAll('input[name=mlogic]').forEach(r =>
  r.addEventListener('change', e => { state.mlogic = e.target.value; render(); }));
['pto','sop','eco'].forEach(k =>
  document.getElementById(k).addEventListener('change', e => { state[k] = e.target.checked; render(); }));
document.getElementById('reset').addEventListener('click', () => {
  state.search = ''; state.markets.clear(); state.complexity.clear();
  state.module = ''; state.pto = state.sop = state.eco = false;
  document.querySelectorAll('aside input[type=checkbox]').forEach(c => c.checked = false);
  document.querySelector('aside input[name=mlogic][value=any]').checked = true;
  state.mlogic = 'any';
  document.getElementById('search').value = '';
  document.getElementById('module').value = '';
  render();
});

// Tabs
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  ['gallery','table','group','matrix'].forEach(v =>
    document.getElementById('view-'+v).style.display = (v === t.dataset.tab ? '' : 'none'));
}));

function applyFilters() {
  return DATA.records.filter(r => {
    if (state.search) {
      const s = state.search;
      const hay = (r.part + ' ' + r.name + ' ' + r.notes + ' ' + r.catalogue).toLowerCase();
      if (!hay.includes(s)) return false;
    }
    if (state.markets.size) {
      const arr = [...state.markets];
      if (state.mlogic === 'all') { if (!arr.every(m => r.markets.includes(m))) return false; }
      else { if (!arr.some(m => r.markets.includes(m))) return false; }
    }
    if (state.complexity.size) {
      const arr = [...state.complexity];
      if (!arr.some(c => r.complexity.includes(c))) return false;
    }
    if (state.module && r.module !== state.module) return false;
    if (state.pto && !r.pto) return false;
    if (state.sop && !r.sop) return false;
    if (state.eco && !r.eco) return false;
    return true;
  });
}

function renderKPIs(rows) {
  const modules = new Set(rows.map(r => r.module).filter(Boolean)).size;
  const mkts = new Set(rows.flatMap(r => r.markets)).size;
  const sop = rows.filter(r => r.sop).length;
  const sd = rows.filter(r => r.complexity.includes('Self destructive')).length;
  document.getElementById('kpis').innerHTML = `
    <div class="kpi"><div class="v">${rows.length} / ${DATA.records.length}</div><div class="l">Labels</div></div>
    <div class="kpi"><div class="v">${modules}</div><div class="l">Modules</div></div>
    <div class="kpi"><div class="v">${mkts}</div><div class="l">Markets covered</div></div>
    <div class="kpi"><div class="v">${sop}</div><div class="l">SOP-ready</div></div>
    <div class="kpi"><div class="v">${sd}</div><div class="l">Self-destructive</div></div>
  `;
  document.getElementById('count-pill').textContent = `${rows.length} of ${DATA.records.length} labels`;
}

function renderGallery(rows) {
  const v = document.getElementById('view-gallery');
  if (!rows.length) { v.innerHTML = '<div class="empty">No labels match the current filters.</div>'; return; }
  v.innerHTML = '<div class="grid">' + rows.map(r => `
    <div class="card">
      <div class="img ${r.image ? '' : 'empty'}">
        ${r.image ? `<img src="${r.image}" alt="${r.part}" />` : 'no image'}
      </div>
      <div class="body">
        <div class="part">${r.part}</div>
        <div class="name">${r.name}</div>
        <div class="chips">
          ${r.markets.map(m => `<span class="chip">${m}</span>`).join('')}
          ${r.complexity.map(c => `<span class="chip gray">${c}</span>`).join('')}
        </div>
        <details><summary>Details</summary>
          <div class="det">
            <b>Module:</b> ${r.module || '—'}<br>
            <b>Catalogue #:</b> ${r.catalogue || '—'}<br>
            <b>Quantity/vehicle:</b> ${r.qty || '—'}<br>
            <b>Prio:</b> ${r.prio || '—'}<br>
            <b>Drawings:</b> ${r.drawings || '—'}<br>
            <b>Lifecycle:</b> ${[r.pto?'PTO':null,r.sop?'SOP':null,r.eco?'ECO':null].filter(Boolean).join(', ')||'—'}<br>
            ${r.notes ? `<b>Notes:</b> ${r.notes}` : ''}
          </div>
        </details>
      </div>
    </div>`).join('') + '</div>';
}

function renderTable(rows) {
  const cols = [
    ['part','Part #'], ['name','Item name'], ['module','Module'],
    ['catalogue','Catalogue #'], ['qty','Qty'],
    ['markets','Markets'], ['complexity','Complexity'],
    ['prio','Prio'], ['drawings','Drawings'],
  ];
  if (state.sort.col) {
    const k = state.sort.col, d = state.sort.dir;
    rows = [...rows].sort((a,b) => {
      const va = Array.isArray(a[k]) ? a[k].join(',') : (a[k] || '');
      const vb = Array.isArray(b[k]) ? b[k].join(',') : (b[k] || '');
      return va > vb ? d : va < vb ? -d : 0;
    });
  }
  const head = cols.map(([k,l]) =>
    `<th data-col="${k}">${l}${state.sort.col===k ? (state.sort.dir>0?' ▲':' ▼') : ''}</th>`).join('');
  const body = rows.map(r => `<tr>` + cols.map(([k]) => {
    let v = r[k]; if (Array.isArray(v)) v = v.join(', ');
    return `<td>${v ?? ''}</td>`;
  }).join('') + `</tr>`).join('');
  const v = document.getElementById('view-table');
  v.innerHTML = `
    <div class="toolbar">
      <div></div>
      <button class="btn" id="dl">Download CSV</button>
    </div>
    <div style="background:#fff;border:1px solid var(--border);border-radius:8px;overflow:auto;max-height:70vh;">
      <table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
    </div>`;
  v.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.col;
    state.sort = state.sort.col === k ? {col:k, dir:-state.sort.dir} : {col:k, dir:1};
    renderTable(applyFilters());
  }));
  v.querySelector('#dl').addEventListener('click', () => {
    const csv = [cols.map(c=>c[1]).join(',')].concat(rows.map(r =>
      cols.map(([k]) => {
        let v = r[k]; if (Array.isArray(v)) v = v.join('; ');
        return '"' + String(v ?? '').replace(/"/g,'""') + '"';
      }).join(','))).join('\n');
    const blob = new Blob([csv], {type:'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'labels_filtered.csv'; a.click();
  });
}

function renderGroup(rows) {
  const opts = [
    ['module','Module'], ['prio','Prio'], ['catalogue','Catalogue #'], ['drawings','Drawings check'],
    ...DATA.markets.map(m => ['mkt:'+m, 'Market: '+m]),
    ...DATA.complexity.map(c => ['cpx:'+c, 'Complexity: '+c]),
  ];
  const v = document.getElementById('view-group');
  v.innerHTML = `
    <div class="toolbar">
      <div>Group by
        <select id="groupBy" style="display:inline-block;width:auto;margin-left:.5rem;">
          ${opts.map(([k,l]) => `<option value="${k}" ${state.groupBy===k?'selected':''}>${l}</option>`).join('')}
        </select>
      </div>
    </div>
    <div id="group-body"></div>`;
  v.querySelector('#groupBy').addEventListener('change', e => { state.groupBy = e.target.value; state.isolate=''; renderGroup(applyFilters()); });

  // Compute counts
  const k = state.groupBy;
  const counts = {};
  rows.forEach(r => {
    let g;
    if (k.startsWith('mkt:')) { g = r.markets.includes(k.slice(4)) ? 'Yes' : 'No'; }
    else if (k.startsWith('cpx:')) { g = r.complexity.includes(k.slice(4)) ? 'Yes' : 'No'; }
    else { g = r[k] || '(blank)'; }
    counts[g] = (counts[g]||0)+1;
  });
  const entries = Object.entries(counts).sort((a,b) => b[1]-a[1]);
  const max = Math.max(1, ...entries.map(e=>e[1]));
  const body = document.getElementById('group-body');
  body.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
      <div style="background:#fff;border:1px solid var(--border);border-radius:8px;padding:.4rem;">
        <table><thead><tr><th>Group</th><th>Count</th><th>Distribution</th></tr></thead><tbody>
          ${entries.map(([g,c]) =>
            `<tr class="grow" data-g="${g}" style="cursor:pointer;${state.isolate===g?'background:#eef2ff':''}">
              <td>${g}</td><td>${c}</td>
              <td><div class="hbar"><div class="bar" style="width:${(c/max)*100}%;"></div></div></td>
            </tr>`).join('')}
        </tbody></table>
      </div>
      <div id="isolate-pane" style="background:#fff;border:1px solid var(--border);border-radius:8px;padding:.6rem;max-height:65vh;overflow:auto;">
        <div class="empty">Click a group to isolate</div>
      </div>
    </div>`;
  body.querySelectorAll('tr.grow').forEach(tr => tr.addEventListener('click', () => {
    state.isolate = tr.dataset.g;
    let sub;
    if (k.startsWith('mkt:')) { const m=k.slice(4); sub = rows.filter(r => (r.markets.includes(m)?'Yes':'No') === state.isolate); }
    else if (k.startsWith('cpx:')) { const x=k.slice(4); sub = rows.filter(r => (r.complexity.includes(x)?'Yes':'No') === state.isolate); }
    else { sub = rows.filter(r => (r[k]||'(blank)') === state.isolate); }
    document.getElementById('isolate-pane').innerHTML = `
      <div style="margin-bottom:.5rem;color:var(--muted);font-size:.85rem;">${sub.length} labels in group <b>${state.isolate}</b></div>
      <table><thead><tr><th>Part #</th><th>Item</th><th>Markets</th></tr></thead><tbody>
      ${sub.map(r => `<tr><td>${r.part}</td><td>${r.name}</td><td>${r.markets.join(', ')}</td></tr>`).join('')}
      </tbody></table>`;
    renderGroup(rows);
  }));
}

function renderMatrix(rows) {
  const modules = [...new Set(rows.map(r => r.module || '(blank)'))].sort();
  const cells = {};
  modules.forEach(m => { cells[m] = {}; DATA.markets.forEach(k => cells[m][k] = 0); });
  rows.forEach(r => {
    const m = r.module || '(blank)';
    r.markets.forEach(k => { if (cells[m]) cells[m][k]++; });
  });
  const maxV = Math.max(1, ...modules.flatMap(m => DATA.markets.map(k => cells[m][k])));
  const head = '<th>Module</th>' + DATA.markets.map(k => `<th>${k}</th>`).join('') + '<th>Total</th>';
  const body = modules.map(m => {
    const total = DATA.markets.reduce((s,k) => s + cells[m][k], 0);
    return `<tr><td><b>${m}</b></td>` + DATA.markets.map(k => {
      const v = cells[m][k];
      const a = v ? (0.15 + 0.85 * v/maxV) : 0;
      return `<td class="${v?'has':''}" style="background:rgba(11,61,145,${a});color:${v && a>0.5?'#fff':''};">${v||''}</td>`;
    }).join('') + `<td><b>${total}</b></td></tr>`;
  }).join('');
  document.getElementById('view-matrix').innerHTML = `
    <div style="color:var(--muted);font-size:.85rem;margin-bottom:.5rem;">Number of labels per Module × Market</div>
    <div style="background:#fff;border:1px solid var(--border);border-radius:8px;overflow:auto;">
      <table class="matrix"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
    </div>`;
}

function render() {
  const rows = applyFilters();
  renderKPIs(rows);
  renderGallery(rows);
  renderTable(rows);
  renderGroup(rows);
  renderMatrix(rows);
}
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
