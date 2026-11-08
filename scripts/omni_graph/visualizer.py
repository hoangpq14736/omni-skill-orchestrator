"""Graphify-Official HTML Topology Visualizer for Omni-Graph.

Adapted directly from Graphify-Labs/graphify (graphify/exporters/html.py).
Features:
- vis-network@9.1.6 with forceAtlas2Based solver & Fermat spiral seed positions.
- Freezes physics after 200 stabilization iterations (ZERO perpetual jitter/vibration).
- Sidebar with Theme Toggle (Light/Dark/System, persisted in localStorage).
- Live Search with autocomplete dropdown and smooth animated focus.
- Node Inspector panel with degree, source file, type, community, and clickable neighbor pills.
- Community Clustering (directory/module partitioning or NetworkX Louvain fallback) with Tableau 10 palette.
- Interactive community checkboxes with Select-All and indeterminate states.
- Re-stabilize / Unfreeze toggle for optional dynamic adjustments.
- 100% Python standard library for core operation (zero required external dependencies).
"""

from __future__ import annotations

import html as _html
import json
import math
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence, Union, Dict, Any, Optional

# Tableau 10 color palette (verbatim from Graphify-Labs/graphify)
COMMUNITY_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]

def sanitize_label(s: str) -> str:
    """Sanitize labels to prevent control characters or ill-formed strings."""
    if not s:
        return ""
    # Strip null bytes and non-printable control characters except newline/tab
    return "".join(ch for ch in str(s) if ch == "\n" or ch == "\t" or ord(ch) >= 32)

def _js_safe(obj: Any) -> str:
    """Escape < as \\u003c so embedded JSON cannot break out of <script> tag."""
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")

def _html_styles() -> str:
    return """<style>
  :root {
    --bg: #0f0f1a; --panel: #1a1a2e; --border: #2a2a4e; --input-border: #3a3a5e;
    --text: #e0e0e0; --text-2: #aaa; --text-3: #ccc; --muted: #555; --count: #666;
    --neighbor-border: #333; --node-label: #ffffff; --btn-bg: #252542; --btn-hover: #35355e;
  }
  [data-theme="light"] {
    --bg: #ffffff; --panel: #f8f9fa; --border: #d9dee5; --input-border: #c3cad4;
    --text: #222222; --text-2: #666666; --text-3: #333333; --muted: #888888; --count: #777777;
    --neighbor-border: #ccc; --node-label: #222222; --btn-bg: #e2e8f0; --btn-hover: #cbd5e1;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; height: 100vh; overflow: hidden; }
  #graph { flex: 1; height: 100%; position: relative; }
  #sidebar { width: 300px; background: var(--panel); border-left: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden; z-index: 10; }
  #theme-wrap { display: flex; gap: 6px; padding: 10px 12px; border-bottom: 1px solid var(--border); }
  #theme-wrap button, .action-btn { flex: 1; background: var(--btn-bg); color: var(--text-2); border: 1px solid var(--input-border); border-radius: 4px; padding: 5px 0; font-size: 11px; cursor: pointer; font-weight: 500; transition: background 0.15s; }
  #theme-wrap button:hover, .action-btn:hover { background: var(--btn-hover); color: var(--text); }
  #theme-wrap button[aria-pressed="true"] { background: #4E79A7; border-color: #4E79A7; color: #fff; }
  #actions-wrap { display: flex; gap: 6px; padding: 8px 12px; border-bottom: 1px solid var(--border); }
  #search-wrap { padding: 10px 12px; border-bottom: 1px solid var(--border); position: relative; }
  #search { width: 100%; background: var(--bg); border: 1px solid var(--input-border); color: var(--text); padding: 7px 10px; border-radius: 6px; font-size: 12px; outline: none; }
  #search:focus { border-color: #4E79A7; }
  #search-results { max-height: 160px; overflow-y: auto; padding: 4px 12px; border-bottom: 1px solid var(--border); display: none; background: var(--panel); }
  .search-item { padding: 5px 6px; cursor: pointer; border-radius: 4px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .search-item:hover { background: var(--border); }
  #info-panel { padding: 14px; border-bottom: 1px solid var(--border); max-height: 280px; overflow-y: auto; }
  #info-panel h3 { font-size: 12px; color: var(--text-2); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
  #info-content { font-size: 12px; color: var(--text-3); line-height: 1.6; }
  #info-content .field { margin-bottom: 4px; word-break: break-word; }
  #info-content .field b { color: var(--text); }
  #info-content .empty { color: var(--muted); font-style: italic; }
  .neighbor-link { display: block; padding: 3px 6px; margin: 2px 0; border-radius: 3px; cursor: pointer; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-left: 3px solid var(--neighbor-border); background: var(--bg); }
  .neighbor-link:hover { background: var(--border); }
  #neighbors-list { max-height: 130px; overflow-y: auto; margin-top: 4px; }
  #legend-wrap { flex: 1; overflow-y: auto; padding: 12px; }
  #legend-wrap h3 { font-size: 12px; color: var(--text-2); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
  #legend-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding: 4px 0; }
  #legend-controls label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px; color: var(--text-2); user-select: none; }
  #legend-controls label:hover { color: var(--text); }
  .legend-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; border-radius: 4px; font-size: 12px; }
  .legend-item:hover { background: var(--border); padding-left: 4px; }
  .legend-item.dimmed { opacity: 0.35; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .legend-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .legend-count { color: var(--count); font-size: 11px; }
  .legend-cb, #select-all-cb { appearance: none; -webkit-appearance: none; width: 14px; height: 14px; border: 1.5px solid var(--input-border); border-radius: 3px; background: var(--bg); cursor: pointer; position: relative; flex-shrink: 0; }
  .legend-cb:checked, #select-all-cb:checked { background: #4E79A7; border-color: #4E79A7; }
  .legend-cb:checked::after, #select-all-cb:checked::after { content: ''; position: absolute; left: 3.5px; top: 1px; width: 4px; height: 7px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
  #select-all-cb:indeterminate { background: #4E79A7; border-color: #4E79A7; }
  #select-all-cb:indeterminate::after { content: ''; position: absolute; left: 2px; top: 5px; width: 8px; height: 2px; background: #fff; border: none; transform: none; }
  #stats { padding: 10px 14px; border-top: 1px solid var(--border); font-size: 11px; color: var(--muted); }
  .vis-tooltip { position: absolute; visibility: hidden; background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 5px 8px; border-radius: 4px; font-size: 11px; pointer-events: none; z-index: 1000; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
</style>"""

def _build_dataset(conn: sqlite3.Connection) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract and format nodes, edges, and community legend data from SQLite."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, qualified_name, file_path, display_path, node_type, line_number
        FROM nodes
        """
    )
    nodes_rows = cur.fetchall()

    # Load edges
    cur.execute(
        """
        SELECT source_id, target_id, relation_type, line_number
        FROM edges
        """
    )
    edge_rows = cur.fetchall()

    # Calculate degrees
    in_degrees: dict[str, int] = {}
    out_degrees: dict[str, int] = {}
    for src, tgt, rel, lno in edge_rows:
        src_s = str(src)
        tgt_s = str(tgt)
        out_degrees[src_s] = out_degrees.get(src_s, 0) + 1
        in_degrees[tgt_s] = in_degrees.get(tgt_s, 0) + 1

    # Extract directory-based community partition (100% stdlib, deterministic)
    # Group by top-level or module directory from display_path
    community_map: dict[str, int] = {}
    community_names: list[str] = []
    
    # Optional networkx Louvain clustering if networkx is available
    use_nx_louvain = False
    try:
        import networkx as nx
        if len(nodes_rows) > 0 and len(edge_rows) > 0:
            G = nx.Graph()
            for r in nodes_rows:
                G.add_node(str(r[0]))
            for src, tgt, rel, lno in edge_rows:
                G.add_edge(str(src), str(tgt))
            # Run Louvain community detection
            import networkx.algorithms.community as nx_comm
            communities_sets = list(nx_comm.louvain_communities(G, seed=42))
            for cid, c_nodes in enumerate(communities_sets):
                c_name = f"Cluster {cid + 1}"
                # Derive a meaningful name from the most common directory in this community
                dir_counts: dict[str, int] = {}
                for r in nodes_rows:
                    if str(r[0]) in c_nodes:
                        dp = r[4] or r[3] or "root"
                        parts = Path(dp).parts
                        d_name = parts[0] if len(parts) > 1 else (parts[0] if parts else "root")
                        dir_counts[d_name] = dir_counts.get(d_name, 0) + 1
                if dir_counts:
                    top_dir = max(dir_counts.items(), key=lambda x: x[1])[0]
                    c_name = f"{top_dir} (C{cid + 1})"
                community_names.append(c_name)
                for nid in c_nodes:
                    community_map[nid] = cid
            use_nx_louvain = True
    except Exception:
        use_nx_louvain = False

    if not use_nx_louvain:
        # Fallback: Partition by parent directory / module
        for r in nodes_rows:
            nid = str(r[0])
            dp = r[4] or r[3] or "root"
            parts = Path(dp).parts
            if len(parts) > 1:
                group_key = parts[0]
                if parts[0] in ("scripts", "src", "pkg", "specs") and len(parts) > 2:
                    group_key = f"{parts[0]}/{parts[1]}"
            else:
                group_key = "(root)"
            
            if group_key not in community_names:
                community_names.append(group_key)
            community_map[nid] = community_names.index(group_key)

    total_communities = len(community_names) if community_names else 1

    # Max degree for relative sizing
    all_degrees = {
        str(r[0]): (in_degrees.get(str(r[0]), 0) + out_degrees.get(str(r[0]), 0))
        for r in nodes_rows
    }
    max_deg = max(all_degrees.values(), default=1) or 1

    # Build vis_nodes
    vis_nodes: list[dict] = []
    community_member_counts: dict[int, int] = {}
    
    for r in nodes_rows:
        nid = str(r[0])
        name = r[1]
        qname = r[2]
        file_path = r[3]
        display_path = r[4] or file_path
        node_type = r[5]
        line_number = r[6]

        deg = all_degrees.get(nid, 0)
        cid = community_map.get(nid, 0)
        community_member_counts[cid] = community_member_counts.get(cid, 0) + 1
        comm_color = COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)]
        comm_name = community_names[cid] if cid < len(community_names) else f"Community {cid}"

        # Size scaled by degree (Graphify formula: 10 + 30 * (deg / max_deg))
        size = round(10.0 + 30.0 * (deg / max_deg), 1)
        # Only show labels for high-degree nodes by default to prevent visual clutter
        font_size = 12 if deg >= (max_deg * 0.15) or len(nodes_rows) < 50 else 0
        display_label = sanitize_label(name)

        vis_nodes.append({
            "id": nid,
            "label": display_label,
            "qualified_name": sanitize_label(qname),
            "color": {
                "background": comm_color,
                "border": comm_color,
                "highlight": {"background": "#ffffff", "border": comm_color},
            },
            "size": size,
            "font": {"size": font_size, "color": "#ffffff"},
            "title": f"{display_label} ({node_type})\n{display_path}:{line_number}\nDegree: {deg}",
            "community": cid,
            "community_name": sanitize_label(comm_name),
            "source_file": sanitize_label(display_path),
            "file_type": node_type,
            "degree": deg,
            "line_number": line_number,
        })

    # Build vis_edges
    vis_edges: list[dict] = []
    for src, tgt, rel, lno in edge_rows:
        src_s = str(src)
        tgt_s = str(tgt)
        is_call = (rel == "call")
        vis_edges.append({
            "from": src_s,
            "to": tgt_s,
            "label": "",
            "title": sanitize_label(f"{rel} [line {lno}]"),
            "dashes": not is_call,
            "width": 2 if is_call else 1,
            "color": {"opacity": 0.7 if is_call else 0.35},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
            "relation": rel,
        })

    # Build legend data
    legend_data: list[dict] = []
    for cid, c_name in enumerate(community_names):
        count = community_member_counts.get(cid, 0)
        if count > 0:
            legend_data.append({
                "cid": cid,
                "color": COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)],
                "label": sanitize_label(c_name),
                "count": count,
            })

    # Sort legend by node count descending
    legend_data.sort(key=lambda x: x["count"], reverse=True)

    return vis_nodes, vis_edges, legend_data

def generate_graph_html(
    conn: sqlite3.Connection,
    output_path: Union[str, Path, None] = None,
    title: str = "Omni-Graph Topology",
) -> str:
    """Generate an interactive vis-network HTML visualization matching official Graphify.
    
    Guarantees:
    - 200 stabilization iterations + immediate physics freezing (ZERO perpetual movement/jitter).
    - Fermat spiral seed positions.
    - Theme toggle (Light/Dark/System).
    - Search with autocomplete and animated focus.
    - Click-to-inspect node info and clickable neighbor links.
    - Community visibility checkboxes.
    """
    nodes, edges, legend = _build_dataset(conn)
    nodes_json = _js_safe(nodes)
    edges_json = _js_safe(edges)
    legend_json = _js_safe(legend)
    title_escaped = _html.escape(title)
    stats_str = f"{len(nodes)} nodes &middot; {len(edges)} edges &middot; {len(legend)} communities"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_escaped}</title>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"
        integrity="sha384-Ux6phic9PEHJ38YtrijhkzyJ8yQlH8i/+buBR8s3mAZOJrP1gwyvAcIYl3GWtpX1"
        crossorigin="anonymous"></script>
{_html_styles()}
<script id="graphify-theme-init">
// Pre-paint theme restoration
(function () {{
  var pref = null;
  try {{ pref = localStorage.getItem('graphify-theme'); }} catch (e) {{}}
  var t = pref === 'light' ? 'light'
    : pref === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light'
    : 'dark';
  document.documentElement.setAttribute('data-theme', t);
}})();
</script>
</head>
<body>
<div id="graph"></div>
<div id="sidebar">
  <div id="theme-wrap" role="group" aria-label="Theme">
    <button type="button" data-theme-choice="light">Light</button>
    <button type="button" data-theme-choice="dark">Dark</button>
    <button type="button" data-theme-choice="system">System</button>
  </div>
  <div id="actions-wrap">
    <button type="button" class="action-btn" id="btn-fit">Fit View</button>
    <button type="button" class="action-btn" id="btn-toggle-physics">Unlock Physics</button>
  </div>
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Search nodes..." autocomplete="off">
    <div id="search-results"></div>
  </div>
  <div id="info-panel">
    <h3>Node Info</h3>
    <div id="info-content"><span class="empty">Click a node to inspect details</span></div>
  </div>
  <div id="legend-wrap">
    <h3>Communities</h3>
    <div id="legend-controls">
      <label><input type="checkbox" id="select-all-cb" checked> Select All</label>
    </div>
    <div id="legend"></div>
  </div>
  <div id="stats">{stats_str}</div>
</div>

<script>
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};
const LEGEND = {legend_json};

function esc(s) {{
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

// Fermat/golden-angle spiral seed positions: avoids near-zero initial repulsion stack overflows
const nodesDS = new vis.DataSet(RAW_NODES.map((n, i) => ({{
  id: n.id,
  label: n.label,
  color: n.color,
  size: n.size,
  font: n.font,
  title: n.title,
  x: 35 * Math.sqrt(i) * Math.cos(i * 2.4),
  y: 35 * Math.sqrt(i) * Math.sin(i * 2.4),
  community: n.community,
  community_name: n.community_name,
  source_file: n.source_file,
  file_type: n.file_type,
  degree: n.degree,
  qualified_name: n.qualified_name,
  line_number: n.line_number
}})));

const edgesDS = new vis.DataSet(RAW_EDGES.map((e, i) => ({{
  id: i,
  from: e.from,
  to: e.to,
  label: '',
  title: e.title,
  dashes: e.dashes,
  width: e.width,
  color: e.color,
  arrows: e.arrows,
  relation: e.relation
}})));

const container = document.getElementById('graph');
let physicsEnabled = true;

const network = new vis.Network(container, {{ nodes: nodesDS, edges: edgesDS }}, {{
  physics: {{
    enabled: true,
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {{
      gravitationalConstant: -60,
      centralGravity: 0.005,
      springLength: 120,
      springConstant: 0.08,
      damping: 0.4,
      avoidOverlap: 0.8,
    }},
    stabilization: {{ iterations: 200, fit: true }},
  }},
  interaction: {{
    hover: true,
    tooltipDelay: 100,
    hideEdgesOnDrag: true,
    navigationButtons: false,
    keyboard: false,
  }},
  nodes: {{ shape: 'dot', borderWidth: 1.5 }},
  edges: {{ smooth: {{ type: 'continuous', roundness: 0.2 }}, selectionWidth: 3 }},
}});

// CRITICAL FIX: Freeze physics immediately after stabilization to prevent perpetual jitter/shaking!
network.once('stabilizationIterationsDone', () => {{
  network.setOptions({{ physics: {{ enabled: false }} }});
  physicsEnabled = false;
  const btn = document.getElementById('btn-toggle-physics');
  if (btn) btn.textContent = 'Unlock Physics';
}});

// Toggle physics button for user flexibility
const togglePhysicsBtn = document.getElementById('btn-toggle-physics');
if (togglePhysicsBtn) {{
  togglePhysicsBtn.addEventListener('click', () => {{
    physicsEnabled = !physicsEnabled;
    network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
    togglePhysicsBtn.textContent = physicsEnabled ? 'Freeze Physics' : 'Unlock Physics';
  }});
}}

// Fit View button
const fitBtn = document.getElementById('btn-fit');
if (fitBtn) {{
  fitBtn.addEventListener('click', () => {{
    network.fit({{ animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }} }});
  }});
}}

// Theme toggle
const THEME_KEY = 'graphify-theme';
const themeMQ = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
let themeLabelColor = '#ffffff';

function themePref() {{
  let p = null;
  try {{ p = localStorage.getItem(THEME_KEY); }} catch (e) {{}}
  return (p === 'light' || p === 'dark' || p === 'system') ? p : null;
}}

function applyTheme(pref) {{
  const t = pref === 'light' ? 'light' : (pref === 'system' && themeMQ && themeMQ.matches) ? 'light' : 'dark';
  const root = document.documentElement;
  if (!root) return;
  root.setAttribute('data-theme', t);
  document.querySelectorAll('[data-theme-choice]').forEach(b => {{
    b.setAttribute('aria-pressed', String(b.dataset.themeChoice === (pref || 'dark')));
  }});
  const labelColor = getComputedStyle(root).getPropertyValue('--node-label').trim();
  if (labelColor && labelColor !== themeLabelColor) {{
    themeLabelColor = labelColor;
    nodesDS.update(nodesDS.get().map(n => ({{ id: n.id, font: Object.assign({{}}, n.font, {{ color: labelColor }}) }})));
  }}
}}

document.querySelectorAll('[data-theme-choice]').forEach(b => {{
  b.addEventListener('click', () => {{
    const pref = b.dataset.themeChoice;
    try {{ localStorage.setItem(THEME_KEY, pref); }} catch (e) {{}}
    applyTheme(pref);
  }});
}});

if (themeMQ) {{
  const onSchemeChange = () => {{ if (themePref() === 'system') applyTheme('system'); }};
  if (themeMQ.addEventListener) themeMQ.addEventListener('change', onSchemeChange);
  else if (themeMQ.addListener) themeMQ.addListener(onSchemeChange);
}}
applyTheme(themePref());

// Node inspection
function showInfo(nodeId) {{
  const n = nodesDS.get(nodeId);
  if (!n) return;
  const neighborIds = network.getConnectedNodes(nodeId);
  const neighborItems = neighborIds.map(nid => {{
    const nb = nodesDS.get(nid);
    const color = nb ? (nb.color && nb.color.background ? nb.color.background : '#555') : '#555';
    return `<span class="neighbor-link" style="border-left-color:${{esc(color)}}" data-nid="${{esc(nid)}}">${{esc(nb ? nb.label : nid)}}</span>`;
  }}).join('');

  let html = `<div class="field"><b>${{esc(n.label)}}</b></div>`;
  html += `<div class="field"><span style="color:var(--text-2)">Qualified:</span> ${{esc(n.qualified_name || n.label)}}</div>`;
  html += `<div class="field"><span style="color:var(--text-2)">Type:</span> <code>${{esc(n.file_type || 'unknown')}}</code></div>`;
  html += `<div class="field"><span style="color:var(--text-2)">Community:</span> ${{esc(n.community_name || '')}}</div>`;
  html += `<div class="field"><span style="color:var(--text-2)">Location:</span> ${{esc(n.source_file)}}:${{n.line_number || 1}}</div>`;
  html += `<div class="field"><span style="color:var(--text-2)">Degree:</span> ${{n.degree}}</div>`;
  if (neighborIds.length) {{
    html += `<div class="field" style="margin-top:8px;color:var(--text-2);font-weight:600">Neighbors (${{neighborIds.length}})</div><div id="neighbors-list">${{neighborItems}}</div>`;
  }}
  document.getElementById('info-content').innerHTML = html;
}}

function focusNode(nodeId) {{
  network.focus(nodeId, {{ scale: 1.4, animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }} }});
  network.selectNodes([nodeId]);
  showInfo(nodeId);
}}

// Delegated neighbor link clicks
document.addEventListener('click', e => {{
  const el = e.target.closest('.neighbor-link');
  if (el && el.dataset.nid !== undefined) focusNode(el.dataset.nid);
}});

// Node selection events
network.on('click', params => {{
  if (params.nodes.length > 0) {{
    showInfo(params.nodes[0]);
  }} else {{
    document.getElementById('info-content').innerHTML = '<span class="empty">Click a node to inspect details</span>';
  }}
}});

// Search box logic
const searchInput = document.getElementById('search');
const searchResults = document.getElementById('search-results');

searchInput.addEventListener('input', () => {{
  const q = searchInput.value.toLowerCase().trim();
  searchResults.innerHTML = '';
  if (!q) {{ searchResults.style.display = 'none'; return; }}
  const matches = RAW_NODES.filter(n => 
    n.label.toLowerCase().includes(q) || (n.qualified_name && n.qualified_name.toLowerCase().includes(q))
  ).slice(0, 20);

  if (!matches.length) {{ searchResults.style.display = 'none'; return; }}
  searchResults.style.display = 'block';
  matches.forEach(n => {{
    const el = document.createElement('div');
    el.className = 'search-item';
    el.textContent = `${{n.label}} (${{n.file_type}})`;
    el.style.borderLeft = `3px solid ${{n.color.background}}`;
    el.onclick = () => {{
      focusNode(n.id);
      searchResults.style.display = 'none';
      searchInput.value = '';
    }};
    searchResults.appendChild(el);
  }});
}});

document.addEventListener('click', e => {{
  if (!searchResults.contains(e.target) && e.target !== searchInput)
    searchResults.style.display = 'none';
}});

// Community filtering
const hiddenCommunities = new Set();
const selectAllCb = document.getElementById('select-all-cb');

function updateSelectAllState() {{
  const total = LEGEND.length;
  const hidden = hiddenCommunities.size;
  selectAllCb.checked = (hidden === 0);
  selectAllCb.indeterminate = (hidden > 0 && hidden < total);
}}

selectAllCb.addEventListener('change', () => {{
  const hide = !selectAllCb.checked;
  document.querySelectorAll('.legend-item').forEach(item => {{
    hide ? item.classList.add('dimmed') : item.classList.remove('dimmed');
  }});
  document.querySelectorAll('.legend-cb').forEach(cb => {{
    cb.checked = !hide;
  }});
  LEGEND.forEach(c => {{
    if (hide) hiddenCommunities.add(c.cid); else hiddenCommunities.delete(c.cid);
  }});
  const updates = RAW_NODES.map(n => ({{ id: n.id, hidden: hide }}));
  nodesDS.update(updates);
  updateSelectAllState();
}});

const legendEl = document.getElementById('legend');
LEGEND.forEach(c => {{
  const item = document.createElement('div');
  item.className = 'legend-item';
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.className = 'legend-cb';
  cb.checked = true;
  cb.addEventListener('change', (e) => {{
    e.stopPropagation();
    if (cb.checked) {{
      hiddenCommunities.delete(c.cid);
      item.classList.remove('dimmed');
    }} else {{
      hiddenCommunities.add(c.cid);
      item.classList.add('dimmed');
    }}
    const updates = RAW_NODES
      .filter(n => n.community === c.cid)
      .map(n => ({{ id: n.id, hidden: !cb.checked }}));
    nodesDS.update(updates);
    updateSelectAllState();
  }});

  item.innerHTML = `<div class="legend-dot" style="background:${{c.color}}"></div>
    <span class="legend-label" title="${{esc(c.label)}}">${{esc(c.label)}}</span>
    <span class="legend-count">${{c.count}}</span>`;
  item.prepend(cb);
  item.onclick = (e) => {{
    if (e.target === cb) return;
    cb.checked = !cb.checked;
    cb.dispatchEvent(new Event('change'));
  }};
  legendEl.appendChild(item);
}});
</script>
</body>
</html>"""

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic file write
        tmp_p = out_p.with_suffix(out_p.suffix + ".tmp")
        tmp_p.write_text(html, encoding="utf-8")
        tmp_p.replace(out_p)

    return html
