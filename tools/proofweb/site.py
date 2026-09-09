"""A single self-contained HTML file showing the graph and every proof.

Why this exists: the claim "edges are derived from proof steps" is abstract
until you click a step and watch exactly one edge light up. This is the smallest
artefact that makes the claim inspectable by someone who will not install Python.

Constraints, deliberately: one file, no build step, no network, no dependencies.
It must open from a filesystem path on a machine with nothing installed. If this
file ever needs npm, something has gone wrong.

Layout is a layered DAG — depth on the vertical axis, assumptions at the bottom —
rather than a force-directed cloud. Force layouts look impressive and tell you
nothing; the whole content of a proof graph is *what rests on what*, and that is
exactly what a layered layout shows.
"""

from __future__ import annotations

import json

from .model import Graph

_COLOURS = {
    "axiom": "#b45309",
    "background": "#64748b",
    "definition": "#0f766e",
    "theorem": "#1d4ed8",
}


def _payload(graph: Graph) -> dict:
    nodes = []
    for n in sorted(graph, key=lambda n: n.id):
        nodes.append({
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "statement": n.statement_natural,
            "latex": n.statement_latex or "",
            "module": n.module,
            "status": n.status,
            "strategy": n.strategy or "",
            "depth": graph.depth(n.id),
            "context": list(n.context),
            "formalization": n.formalization,
            "source": n.source_path,
            "steps": [
                {"n": s.n, "id": s.sid or "", "claim": s.claim,
                 "by": list(s.by), "note": s.note or ""}
                for s in n.steps
            ],
        })
    edges = [
        {"src": e.src, "dst": e.dst, "kind": e.kind, "step": e.step,
         "step_id": e.step_id}
        for e in graph.edges()
    ]
    return {"nodes": nodes, "edges": edges}


_CSS = """
:root{--bg:#ffffff;--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--panel:#f8fafc;
--hl:#dc2626;--accent:#1d4ed8}
@media (prefers-color-scheme:dark){:root{--bg:#0b1120;--fg:#e2e8f0;--muted:#94a3b8;
--line:#1e293b;--panel:#111827;--hl:#f87171;--accent:#60a5fa}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;
align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:650;letter-spacing:-.01em}
header p{margin:0;color:var(--muted);font-size:12.5px}
label{font-size:12.5px;color:var(--muted);cursor:pointer;user-select:none}
main{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,420px);
height:calc(100vh - 58px)}
@media (max-width:860px){main{grid-template-columns:1fr;height:auto}
#panel{border-left:none;border-top:1px solid var(--line)}}
#canvas{overflow:auto;background:var(--bg)}
#panel{border-left:1px solid var(--line);background:var(--panel);overflow-y:auto;
padding:18px 20px}
.node rect{stroke-width:1.5px;fill:var(--bg);cursor:pointer;rx:5}
.node text{font-size:11px;pointer-events:none;fill:var(--fg)}
.node .sub{font-size:9.5px;fill:var(--muted)}
.node.sel rect{stroke-width:2.5px}
.node.dim{opacity:.22}
path.edge{fill:none;stroke:var(--line);stroke-width:1.4px}
path.edge.vocab{stroke-dasharray:3 3;opacity:.55}
path.edge.lit{stroke:var(--hl);stroke-width:2.6px;opacity:1}
path.edge.dim{opacity:.07}
.layerlabel{font-size:10px;fill:var(--muted)}
h2{font-size:15px;margin:0 0 2px}
.kindtag{display:inline-block;font-size:10px;text-transform:uppercase;
letter-spacing:.07em;padding:2px 7px;border-radius:99px;border:1px solid currentColor}
.stmt{margin:12px 0;padding:11px 13px;background:var(--bg);border:1px solid var(--line);
border-radius:6px}
.strategy{color:var(--muted);font-style:italic;margin:10px 0}
ol.steps{list-style:none;padding:0;margin:12px 0 0;counter-reset:s}
ol.steps li{padding:8px 10px;border-left:2px solid var(--line);margin-bottom:5px;
cursor:pointer;border-radius:0 4px 4px 0}
ol.steps li:hover,ol.steps li.active{border-left-color:var(--hl);background:var(--bg)}
.stepno{color:var(--muted);font-variant-numeric:tabular-nums;margin-right:7px}
.by{margin-top:5px;font-size:12px;color:var(--muted)}
.cite{display:inline-block;padding:0 5px;margin-right:4px;border-radius:3px;
border:1px solid var(--line);cursor:pointer;font-family:ui-monospace,monospace;font-size:11px}
.cite.node{color:var(--accent);border-color:currentColor}
.cite.local{color:var(--muted)}
.cite.ext{color:var(--muted);border-style:dashed;opacity:.85}
.note{font-size:12px;color:var(--muted);margin-top:5px}
.addr{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--muted);
margin-top:4px;opacity:.75}
.meta{margin-top:16px;padding-top:12px;border-top:1px solid var(--line);
font-size:12px;color:var(--muted)}
.meta code{font-family:ui-monospace,monospace;font-size:11.5px}
.empty{color:var(--muted);margin-top:30vh;text-align:center}
"""

_JS = r"""
const NODES = new Map(DATA.nodes.map(n => [n.id, n]));
const BOXW = 168, BOXH = 40, GAPX = 26, GAPY = 92, PADX = 34, PADY = 34;

// Layered layout: depth 0 (assumptions) at the bottom, so the picture reads the
// way a proof reads — you build upward from what you assumed.
const layers = new Map();
for (const n of DATA.nodes) {
  if (!layers.has(n.depth)) layers.set(n.depth, []);
  layers.get(n.depth).push(n);
}
const depths = [...layers.keys()].sort((a, b) => a - b);
const maxRow = Math.max(...depths.map(d => layers.get(d).length));
const W = PADX * 2 + maxRow * (BOXW + GAPX);
const H = PADY * 2 + depths.length * GAPY;
const pos = new Map();
depths.forEach((d, i) => {
  const row = layers.get(d);
  const y = H - PADY - i * GAPY - BOXH;
  const rowW = row.length * (BOXW + GAPX) - GAPX;
  row.forEach((n, j) => pos.set(n.id, { x: (W - rowW) / 2 + j * (BOXW + GAPX), y }));
});

const svgns = "http://www.w3.org/2000/svg";
const el = (t, a = {}) => { const e = document.createElementNS(svgns, t);
  for (const k in a) e.setAttribute(k, a[k]); return e; };

const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H });
document.getElementById("canvas").appendChild(svg);

// Edges first so nodes paint over them.
const edgeLayer = el("g"), nodeLayer = el("g");
svg.append(edgeLayer, nodeLayer);

const edgeEls = [];
for (const e of DATA.edges) {
  const a = pos.get(e.src), b = pos.get(e.dst);
  if (!a || !b) continue;
  const x1 = a.x + BOXW / 2, y1 = a.y + BOXH, x2 = b.x + BOXW / 2, y2 = b.y;
  const my = (y1 + y2) / 2;
  const p = el("path", {
    class: "edge" + (e.kind === "vocabulary" ? " vocab" : ""),
    d: `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`,
  });
  edgeEls.push({ p, e });
  edgeLayer.appendChild(p);
}

const nodeEls = new Map();
for (const n of DATA.nodes) {
  const { x, y } = pos.get(n.id);
  const g = el("g", { class: "node", transform: `translate(${x},${y})` });
  g.appendChild(el("rect", { width: BOXW, height: BOXH, stroke: COLOURS[n.kind] || "#000" }));
  const t = el("text", { x: 9, y: 16 }); t.textContent = n.id + "  " + n.title.slice(0, 22);
  const s = el("text", { x: 9, y: 30, class: "sub" });
  s.textContent = n.kind + (n.steps.length ? ` · ${n.steps.length} steps` : "");
  g.append(t, s);
  g.addEventListener("click", () => select(n.id));
  nodeEls.set(n.id, g);
  nodeLayer.appendChild(g);
}

let current = null, activeStep = null;

function paint() {
  const showVocab = document.getElementById("vocab").checked;
  const related = new Set();
  if (current) {
    related.add(current);
    for (const e of DATA.edges) {
      if (e.src === current) related.add(e.dst);
      if (e.dst === current) related.add(e.src);
    }
  }
  for (const [id, g] of nodeEls) {
    g.classList.toggle("sel", id === current);
    g.classList.toggle("dim", !!current && !related.has(id));
  }
  for (const { p, e } of edgeEls) {
    const vocabHidden = e.kind === "vocabulary" && !showVocab;
    p.style.display = vocabHidden ? "none" : "";
    const touches = current && (e.src === current || e.dst === current);
    // The point of the whole thing: when a step is selected, exactly the edges
    // that step created light up.
    const lit = activeStep !== null && e.src === current && e.step === activeStep;
    p.classList.toggle("lit", !!lit);
    p.classList.toggle("dim", !!current && !touches);
  }
}

function select(id, step = null) {
  current = id; activeStep = step;
  renderPanel(NODES.get(id));
  paint();
  nodeEls.get(id)?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
}

const esc = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function renderPanel(n) {
  const p = document.getElementById("panel");
  if (!n) { p.innerHTML = '<p class="empty">Select a node.</p>'; return; }

  const LOCAL = /^(?:hyp(?::.*)?|s\d+|s:.*|assumption)$/;
  const cite = tok => NODES.has(tok)
    ? `<span class="cite node" data-goto="${tok}" title="${esc(NODES.get(tok).title)}">${tok}</span>`
    : LOCAL.test(tok)
      ? `<span class="cite local" title="local to this proof — creates no edge">${esc(tok)}</span>`
      : `<span class="cite ext" title="cited, but outside this view">${esc(tok)}</span>`;

  const steps = n.steps.map(s => `
    <li data-step="${s.n}" class="${s.n === activeStep ? "active" : ""}">
      <span class="stepno">${s.n}.</span>${esc(s.claim)}
      ${s.id ? `<div class="addr" title="the stable address of this step — cite this, not the number">${n.id}#${esc(s.id)}</div>` : ""}
      <div class="by">by ${s.by.map(cite).join("")}</div>
      ${s.note ? `<div class="note">${esc(s.note)}</div>` : ""}
    </li>`).join("");

  const forms = Object.entries(n.formalization || {});
  p.innerHTML = `
    <span class="kindtag" style="color:${COLOURS[n.kind]}">${n.kind}</span>
    <h2 style="margin-top:8px">${n.id} — ${esc(n.title)}</h2>
    <div class="stmt">${esc(n.statement)}</div>
    ${n.strategy ? `<p class="strategy">${esc(n.strategy)}</p>` : ""}
    ${n.steps.length ? `<p style="color:var(--muted);font-size:12px;margin:14px 0 0">
        Click a step to light up the edges it creates.</p><ol class="steps">${steps}</ol>`
      : `<p class="strategy">Assumed, not proved.</p>`}
    <div class="meta">
      status <code>${n.status}</code>${n.depth >= 0 ? ` · depth <code>${n.depth}</code>` : ""}
      ${forms.length ? `<br>formalized as ${forms.map(([k, v]) =>
        `<code>${k}: ${esc(v)}</code>`).join(", ")}` : ""}
      <br><code>${esc(n.source)}</code>
    </div>`;

  p.querySelectorAll("[data-goto]").forEach(e =>
    e.addEventListener("click", ev => { ev.stopPropagation(); select(e.dataset.goto); }));
  p.querySelectorAll("[data-step]").forEach(e =>
    e.addEventListener("click", () => {
      const s = +e.dataset.step;
      activeStep = activeStep === s ? null : s;
      renderPanel(n); paint();
    }));
}

document.getElementById("vocab").addEventListener("change", paint);
renderPanel(null);
paint();
"""


def to_html(graph: Graph, title: str = "ProofWeb", subtitle: str | None = None) -> str:
    data = json.dumps(_payload(graph), ensure_ascii=False)
    colours = json.dumps(_COLOURS)
    n_theorems = sum(1 for n in graph if n.is_theorem)
    n_proof_edges = len(graph.edges("proof"))
    sub = f" — {subtitle}" if subtitle else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>{len(graph)} nodes · {n_theorems} theorems · {n_proof_edges} proof edges,
     each one derived from a single step of a single proof{sub}</p>
  <label><input type="checkbox" id="vocab"> show vocabulary edges</label>
</header>
<main>
  <div id="canvas"></div>
  <div id="panel"></div>
</main>
<script>
const DATA = {data};
const COLOURS = {colours};
{_JS}
</script>
</body>
</html>
"""
