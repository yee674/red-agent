# -*- coding: utf-8 -*-
"""知识图谱可视化：不依赖任何外部库的力导向图 + 时间轴。

之所以自己写 canvas 力导图而不用 ECharts/pyvis：
1) 离线可用，答辩现场断网也不会白屏；
2) 不增加依赖，页面不用加载 1MB 的 JS 库；
3) 数据量（30~100 个实体）完全够用。
"""
from __future__ import annotations

import json

TYPE_COLORS = {
    "PERSON": "#e0b354",
    "PLACE": "#7fb069",
    "EVENT": "#d95d39",
    "ORG": "#6c9bd1",
    "CONCEPT": "#b07cc6",
    "WORK": "#c98474",
}


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def graph_component(nodes: list[dict], edges: list[dict], legend: dict,
                    hint: str = "", height: int = 620) -> str:
    """生成力导向图的 HTML。

    nodes: [{id, label, type}]
    edges: [{s, t, rel}]     s/t 为 id
    legend: {type: 中文标签}
    """
    payload = json.dumps({"nodes": nodes, "edges": edges,
                          "colors": TYPE_COLORS, "legend": legend},
                         ensure_ascii=False)
    return f"""
<div class="kg-wrap">
  <canvas id="kg" height="{height - 40}"></canvas>
  <div id="kg-tip" class="kg-tip"></div>
  <div id="kg-legend" class="kg-legend"></div>
  <div id="kg-info" class="kg-info"></div>
</div>
<style>
  .kg-wrap {{ position: relative; width: 100%; height: {height - 40}px;
             background: rgba(18,8,10,.35); border: 1px solid rgba(232,192,125,.18);
             border-radius: 16px; overflow: hidden; }}
  #kg {{ width: 100%; height: 100%; display: block; cursor: grab; }}
  .kg-tip {{ position: absolute; pointer-events: none; padding: 4px 9px;
            background: rgba(20,8,10,.94); border: 1px solid rgba(232,192,125,.45);
            border-radius: 8px; color: #f5ebe6; font: 13px/1.4 "Microsoft YaHei", sans-serif;
            opacity: 0; transition: opacity .12s; white-space: nowrap; z-index: 5; }}
  .kg-legend {{ position: absolute; left: 10px; bottom: 8px; display: flex;
               flex-wrap: wrap; gap: 8px; font: 12px/1 "Microsoft YaHei", sans-serif;
               color: #d7bdb6; z-index: 4; }}
  .kg-legend span {{ display: inline-flex; align-items: center; gap: 4px; }}
  .kg-legend i {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
  .kg-info {{ position: absolute; right: 10px; top: 10px; max-width: 260px;
             font: 13px/1.6 "Microsoft YaHei", sans-serif; color: #f5ebe6;
             background: rgba(20,8,10,.9); border: 1px solid rgba(232,192,125,.35);
             border-radius: 12px; padding: 8px 12px; opacity: 0; transition: opacity .15s;
             z-index: 4; }}
</style>
<script>
(function () {{
  const DATA = {payload};
  const cv = document.getElementById("kg");
  const ctx = cv.getContext("2d");
  const tip = document.getElementById("kg-tip");
  const info = document.getElementById("kg-info");
  const legend = document.getElementById("kg-legend");
  let W = 0, H = 0, dpr = window.devicePixelRatio || 1;

  // ---- 图例 ----
  legend.innerHTML = Object.entries(DATA.legend).map(([k, v]) =>
    `<span><i style="background:${{DATA.colors[k] || '#888'}}"></i>${{v}}</span>`).join("");

  // ---- 节点 / 边 ----
  const idx = {{}};
  const nodes = DATA.nodes.map((n, i) => {{
    idx[n.id] = i;
    const a = (i / DATA.nodes.length) * Math.PI * 2;
    return {{ ...n, x: Math.cos(a) * 220 + (Math.random() - .5) * 40,
              y: Math.sin(a) * 220 + (Math.random() - .5) * 40,
              vx: 0, vy: 0, deg: 0 }};
  }});
  const links = DATA.edges
    .map(e => ({{ a: idx[e.s], b: idx[e.t], rel: e.rel }}))
    .filter(l => l.a !== undefined && l.b !== undefined);
  links.forEach(l => {{ nodes[l.a].deg++; nodes[l.b].deg++; }});

  function resize() {{
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }}
  window.addEventListener("resize", () => {{ resize(); }});

  // ---- 力导向：斥力 + 弹簧 + 向心 ----
  let alpha = 1;
  function tick() {{
    for (let i = 0; i < nodes.length; i++) {{
      const n = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {{
        const m = nodes[j];
        let dx = n.x - m.x, dy = n.y - m.y;
        let d2 = dx * dx + dy * dy || 0.01;
        if (d2 < 90000) {{
          const f = 1600 / d2;
          const d = Math.sqrt(d2);
          const fx = dx / d * f, fy = dy / d * f;
          n.vx += fx; n.vy += fy; m.vx -= fx; m.vy -= fy;
        }}
      }}
      n.vx -= n.x * 0.0022; n.vy -= n.y * 0.0022;   // 向心
    }}
    links.forEach(l => {{
      const a = nodes[l.a], b = nodes[l.b];
      let dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const target = 130;
      const f = (d - target) * 0.012;
      const fx = dx / d * f, fy = dy / d * f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }});
    nodes.forEach(n => {{
      n.vx *= 0.82; n.vy *= 0.82;
      n.x += n.vx * alpha; n.y += n.vy * alpha;
      const pad = 46;
      n.x = Math.max(-W / 2 + pad, Math.min(W / 2 - pad, n.x));
      n.y = Math.max(-H / 2 + pad, Math.min(H / 2 - pad, n.y));
    }});
    alpha = Math.max(alpha * 0.995, 0.22);
  }}

  // ---- 绘制 ----
  let hover = -1, selected = -1, drag = null, moved = false;
  const neighbors = {{}};
  links.forEach(l => {{
    (neighbors[l.a] = neighbors[l.a] || new Set()).add(l.b);
    (neighbors[l.b] = neighbors[l.b] || new Set()).add(l.a);
  }});

  function draw() {{
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2, H / 2);
    const active = selected >= 0 ? selected : hover;
    const focus = active >= 0 ? new Set([active, ...(neighbors[active] || [])]) : null;

    links.forEach(l => {{
      const a = nodes[l.a], b = nodes[l.b];
      const on = !focus || (focus.has(l.a) && focus.has(l.b));
      ctx.strokeStyle = on ? "rgba(232,192,125,.55)" : "rgba(232,192,125,.12)";
      ctx.lineWidth = on ? 1.4 : 1;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }});

    nodes.forEach((n, i) => {{
      const on = !focus || focus.has(i);
      const r = 9 + Math.min(n.deg, 12) * 0.9 + (i === active ? 3 : 0);
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = on ? (DATA.colors[n.type] || "#999") : "rgba(160,140,130,.35)";
      ctx.fill();
      ctx.strokeStyle = i === selected ? "#fff3d8" : "rgba(20,8,10,.85)";
      ctx.lineWidth = i === selected ? 2.4 : 1.2;
      ctx.stroke();

      ctx.font = (i === active ? "600 14px" : "13px") + " 'Microsoft YaHei', sans-serif";
      ctx.fillStyle = on ? "#f7efe8" : "rgba(215,189,182,.4)";
      ctx.textAlign = "center";
      ctx.fillText(n.label, n.x, n.y + r + 15);
    }});
    ctx.restore();
  }}

  function loop() {{ tick(); draw(); requestAnimationFrame(loop); }}

  // ---- 交互 ----
  function pos(ev) {{
    const r = cv.getBoundingClientRect();
    return {{ x: ev.clientX - r.left - W / 2, y: ev.clientY - r.top - H / 2 }};
  }}
  function pick(p) {{
    for (let i = nodes.length - 1; i >= 0; i--) {{
      const n = nodes[i];
      const r = 12 + Math.min(n.deg, 12) * 0.9;
      if ((p.x - n.x) ** 2 + (p.y - n.y) ** 2 <= r * r) return i;
    }}
    return -1;
  }}

  cv.addEventListener("mousemove", ev => {{
    const p = pos(ev);
    if (drag !== null) {{
      const n = nodes[drag]; n.x = p.x; n.y = p.y; n.vx = n.vy = 0; moved = true;
      draw(); return;
    }}
    hover = pick(p);
    cv.style.cursor = hover >= 0 ? "pointer" : "grab";
    if (hover >= 0) {{
      const n = nodes[hover];
      tip.style.opacity = 1;
      tip.innerHTML = `<b>${{n.label}}</b> · ${{n.deg}} 条关系`;
      tip.style.left = (ev.clientX - cv.getBoundingClientRect().left + 14) + "px";
      tip.style.top = (ev.clientY - cv.getBoundingClientRect().top + 10) + "px";
    }} else {{
      tip.style.opacity = 0;
    }}
    draw();
  }});

  cv.addEventListener("mousedown", ev => {{
    const p = pos(ev); const i = pick(p);
    if (i >= 0) {{ drag = i; moved = false; }}
  }});
  window.addEventListener("mouseup", () => {{
    if (drag !== null && !moved) {{
      selected = (selected === drag) ? -1 : drag;
      if (selected >= 0) {{
        const n = nodes[selected];
        const rels = links.filter(l => l.a === selected || l.b === selected)
          .map(l => `${{nodes[l.a].label}} —${{l.rel}}→ ${{nodes[l.b].label}}`);
        info.style.opacity = 1;
        info.innerHTML = `<b>${{n.label}}</b><br><span style="color:#d7bdb6">${{n.deg}} 条关系</span><br>` +
          rels.slice(0, 6).join("<br>") + (rels.length > 6 ? "<br>…" : "");
      }} else {{
        info.style.opacity = 0;
      }}
      draw();
    }}
    drag = null;
  }});

  resize(); loop();
  setTimeout(() => {{ alpha = 0.6; }}, 1200);
}})();
</script>
"""


def timeline_html(items: list[dict], title: str = "") -> str:
    """时间轴：items = [{year, label, text, entity}]"""
    rows = []
    last_year = None
    for it in items:
        year = it["year"]
        show_year = year != last_year
        last_year = year
        rows.append(
            f'<div class="tl-row">'
            f'<div class="tl-year">{year if show_year else ""}</div>'
            f'<div class="tl-dot"></div>'
            f'<div class="tl-card"><div class="tl-label">{_esc(it["label"])}</div>'
            f'<div class="tl-text">{_esc(it.get("text", ""))}</div></div>'
            f'</div>'
        )
    return f"""
<div class="tl-wrap">
  {f'<div class="tl-title">{_esc(title)}</div>' if title else ''}
  <div class="tl-body">{''.join(rows)}</div>
</div>
<style>
  .tl-wrap {{ margin-top: .4rem; }}
  .tl-title {{ font: 600 15px/1.6 "Microsoft YaHei", sans-serif; color: #e8c07d; margin-bottom: .6rem; }}
  .tl-body {{ position: relative; padding-left: 8px; }}
  .tl-body::before {{ content: ""; position: absolute; left: 74px; top: 6px; bottom: 6px;
                     width: 2px; background: linear-gradient(180deg, rgba(232,192,125,.65), rgba(232,192,125,.12)); }}
  .tl-row {{ display: grid; grid-template-columns: 62px 18px 1fr; align-items: start;
            gap: 6px; margin-bottom: .55rem; }}
  .tl-year {{ font: 600 15px/1.5 "Microsoft YaHei", sans-serif; color: #e8c07d; text-align: right; }}
  .tl-dot {{ width: 9px; height: 9px; border-radius: 50%; background: #e8c07d;
            margin: 6px auto 0; box-shadow: 0 0 0 3px rgba(232,192,125,.16); }}
  .tl-card {{ background: rgba(255,255,255,.045); border: 1px solid rgba(232,192,125,.2);
             border-radius: 12px; padding: .5rem .75rem; }}
  .tl-label {{ font: 600 13.5px/1.5 "Microsoft YaHei", sans-serif; color: #f5ebe6; }}
  .tl-text {{ font: 12.5px/1.65 "Microsoft YaHei", sans-serif; color: #cdb7af; margin-top: 2px; }}
</style>
"""
