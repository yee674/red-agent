# -*- coding: utf-8 -*-
"""研学地图：把 Leaflet 内联进组件，离线也能显示地标（瓦片需要联网）。

点标签会弹出名片：名称 / 地址 / 简介 / 照片。
照片在服务端压成 260px 宽的小图后内联成 base64，避免 iframe 里的路径问题。
"""
from __future__ import annotations

import base64
import io
import json
import os
from functools import lru_cache

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")


@lru_cache(maxsize=2)
def _leaflet_assets() -> tuple[str, str]:
    css = ""
    js = ""
    try:
        with open(os.path.join(STATIC, "leaflet.css"), encoding="utf-8") as f:
            css = f.read()
        with open(os.path.join(STATIC, "leaflet.js"), encoding="utf-8") as f:
            js = f.read()
    except OSError:
        pass
    return css, js


@lru_cache(maxsize=64)
def _thumb_b64(path: str, mtime: float, width: int = 260) -> str:
    """把实体图片压成小图并转 base64（mtime 参与缓存键，换图后自动更新）。"""
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail((width, width * 2), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _image_for(poi: dict) -> str:
    fname = poi.get("image") or (poi.get("entity", "") + ".jpg")
    path = os.path.join(ROOT, "assets", fname)
    if not os.path.exists(path):
        return ""
    return _thumb_b64(path, os.path.getmtime(path))


def map_component(pois: list[dict], lang: str, height: int = 520,
                  route_title: str = "", offline_note: str = "") -> str:
    """pois 为已排好序的点位（含 name/addr/intro/lat/lng/image）。"""
    css, js = _leaflet_assets()
    data = []
    for i, p in enumerate(pois, 1):
        data.append({
            "i": i,
            "name": p["name"],
            "addr": p.get("addr", ""),
            "intro": p.get("intro", ""),
            "lat": p["lat"],
            "lng": p["lng"],
            "img": _image_for(p),
        })
    payload = json.dumps(data, ensure_ascii=False)

    return f"""
<div id="study-map" style="width:100%;height:{height}px;border-radius:16px;
     border:1px solid rgba(232,192,125,.25);background:#14080a;"></div>
<div class="map-foot">{_esc(offline_note)}</div>
<style>
  {css}
  .leaflet-container {{ background:#14080a; font-family:"Microsoft YaHei",sans-serif; }}
  .leaflet-popup-content-wrapper {{ background:#1d0f10; color:#f5ebe6;
      border:1px solid rgba(232,192,125,.4); border-radius:12px; }}
  .leaflet-popup-tip {{ background:#1d0f10; }}
  .leaflet-popup-content {{ margin: 10px 12px; width: 232px !important; }}
  .poi-img {{ width:100%; border-radius:8px; margin-bottom:6px; display:block; }}
  .poi-name {{ font-weight:600; font-size:14px; color:#e8c07d; }}
  .poi-addr {{ font-size:12px; color:#d7bdb6; margin:2px 0 5px; }}
  .poi-intro {{ font-size:12.5px; line-height:1.6; }}
  .poi-num {{ background:#e8c07d; color:#1a0b0c; border-radius:50%; width:26px; height:26px;
      display:flex; align-items:center; justify-content:center; font:600 13px/1 "Microsoft YaHei",sans-serif;
      border:2px solid rgba(20,8,10,.8); box-shadow:0 2px 6px rgba(0,0,0,.5); }}
  .map-foot {{ font-size:12px; color:#a08b83; margin-top:6px; }}
</style>
<script>
  {js}
</script>
<script>
(function () {{
  const POIS = {payload};
  const map = L.map('study-map', {{ zoomControl: true, attributionControl: true }})
               .setView([POIS[0].lat, POIS[0].lng], 17);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }}).addTo(map);

  const pts = [];
  POIS.forEach(p => {{
    const icon = L.divIcon({{ className: '', html: `<div class="poi-num">${{p.i}}</div>`,
                             iconSize: [26, 26], iconAnchor: [13, 13] }});
    const mark = L.marker([p.lat, p.lng], {{ icon, title: p.name }}).addTo(map);
    const img = p.img ? `<img class="poi-img" src="${{p.img}}" alt="">` : '';
    mark.bindPopup(`${{img}}<div class="poi-name">${{p.i}}. ${{p.name}}</div>
                    <div class="poi-addr">${{p.addr}}</div>
                    <div class="poi-intro">${{p.intro}}</div>`, {{ maxWidth: 260 }});
    pts.push([p.lat, p.lng]);
  }});
  if (pts.length > 1) {{
    L.polyline(pts, {{ color: '#d8452f', weight: 3, opacity: .8, dashArray: '6 6' }}).addTo(map);
    map.fitBounds(pts, {{ padding: [40, 40] }});
  }}
}})();
</script>
"""
