# -*- coding: utf-8 -*-
"""一师红色文化智能研学 —— Streamlit 前端

数据全部来自项目目录里的文件，改完保存即可自动刷新（见 README.md）：
    kg.json            实体与关系（结构）
    materials/<id>.md  每个实体的详细资料（支持 .zh.md / .en.md 双语）
    assets/<id>.jpg    实体配图（也可以写在 kg.json 的 "image" 字段里）
    assets/bg.jpg      页面背景图（换成自己的照片即可）

C 语言部分（graph.c / graph.dll）负责邻接表的存储与一跳邻居查询，
Python 通过 ctypes 调用，见 c_core.py。
"""
from __future__ import annotations

import base64
import difflib
import hashlib
import itertools
import json
import os
import random
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import report as report_mod
import custom_route
import ui_graph
import ui_map

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
MATERIALS = os.path.join(ROOT, "materials")
KG_PATH = os.path.join(ROOT, "kg.json")

# 开发说明类面板（怎么加资料、C 语言内核详情）默认不在界面显示，
# 需要时设置环境变量 RED_AGENT_DEV=1 再启动即可调出。
DEV_PANELS = os.environ.get("RED_AGENT_DEV", "").strip().lower() in ("1", "true", "yes", "on")

BG_CANDIDATES = ("bg.jpg", "bg.jpeg", "bg.png", "bg.webp",
                 "background.jpg", "background.png")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP")

st.set_page_config(
    page_title="红脉智谱 RedTrace AI",
    page_icon="🚩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 1. 多语言文案
# ============================================================
TEXT = {
    "zh": {
        "app_title": "红脉智谱",
        "badge": "湖南第一师范 · 红色文化知识图谱",
        "subtitle": "一师红色文化知识图谱与智能研学平台",
        "tags": "关系挖掘 · 人物追踪 · AI 定制路线",
        "language": "语言 / Language",
        "settings": "设置",
        "nav": "页面",
        "page_chat": "问答",
        "page_graph": "知识图谱",
        "page_study": "研学",
        "graph_hint": "拖动节点可以调整布局，点击节点高亮它的关系；颜色代表实体类型。",
        "timeline_title": "一师求学时期大事时间轴",
        "view_entity": "选一个实体继续提问",
        "view_btn": "查看该实体",
        "choose_route": "选择研学路线",
        "duration": "建议时长",
        "pois_count": "个点位",
        "map_note": "地标坐标为近似位置，仅用于研学导览；地图瓦片来自 OpenStreetMap，离线时只显示地标与路线。",
        "poi_list": "点位讲解",
        "open_entity": "查看实体卡片",
        "tasks": "研学任务卡",
        "quiz": "随堂测评",
        "quiz_new": "换一组题",
        "quiz_submit": "提交答案",
        "quiz_score": "得分",
        "quiz_need_all": "还有题目没有作答。",
        "quiz_all_right": "全部答对，厉害！",
        "export": "导出研学小结（docx）",
        "export_ready": "小结已生成，点下面的按钮下载。",
        "download": "下载小结",
        "correct": "正确答案",
        "no_image": "（暂无图片）",
        "custom_route": "AI 定制路线",
        "custom_hint": "选兴趣主题和时长，系统按实体类型匹配 + C 语言 BFS 跳数就近排序，为你生成一条路线。",
        "interest": "兴趣主题",
        "interest_person": "人物",
        "interest_place": "旧址",
        "interest_event": "事件",
        "interest_concept": "精神理念",
        "hours": "计划时长",
        "hours_unit": "小时",
        "start_from": "从哪开始",
        "generate": "生成我的路线",
        "custom_match": "主题匹配",
        "custom_hops": "距上一点 {n} 跳",
        "export_custom": "导出这条路线的小结",
        "data_status": "数据状态",
        "entities": "实体",
        "relations": "关系",
        "rel_types": "关系类型",
        "updated": "最后更新",
        "auto_refresh": "自动刷新（保存文件后自动更新页面）",
        "reload_now": "立即重新加载",
        "reloaded": "已重新加载最新数据。",
        "data_changed": "检测到数据文件变化，已自动更新。",
        "placeholder": "试试问：毛泽东、冷水浴、一师水井……",
        "welcome": "随便问一位人物、一处旧址或一个事件，我来把它们之间的关系理清楚。",
        "examples": "可以这样问",
        "not_found": "知识库里暂时没有这个实体。",
        "try_these": "试试这些：",
        "no_relations": "暂无关联关系。",
        "out_relations": "直接关联（本实体 → 其他实体）",
        "in_relations": "反向关联（其他实体 → 本实体）",
        "more": "还有 {n} 条",
        "two_hop": "间接关联（两跳路径）",
        "sources": "资料来源",
        "raw_c": "查看 C 层原始返回",
        "path_tool": "两点关系查询（C 语言 BFS 最短路径）",
        "path_from": "从",
        "path_to": "到",
        "path_btn": "查找关联路径",
        "path_hops": "{n} 跳",
        "path_same": "两个实体相同。",
        "path_none": "这两个实体之间没有连通路径。",
        "path_time": "C 语言 BFS 耗时",
        "path_time_py": "Python BFS 耗时",
        "engine": "内核引擎",
        "engine_c": "C 内核（graph.dll）",
        "engine_py": "Python 兜底（未编译 C）",
        "path_unsupported": "当前图形内核不支持路径查询。",
        "path_caption": "路径由 graph.c 中的 BFS 计算，反向边标为 ←。",
        "material_missing": "还没有为这个实体准备详细资料。在 `materials/{id}.md` 里写下内容即可自动显示。",
        "c_core": "C 语言内核",
        "c_core_info": "邻接表 + `query_neighbors()`，由 `graph.c` 编译为 `graph.dll` 后经 ctypes 调用，"
                       "查询实际发生在 C 里。数据变化时会自动加载一份新的 DLL 副本，无需重启。",
        "howto": "怎么加资料 / 图片",
        "howto_body": (
            "1. **加实体**：编辑 `kg.json` 的 `nodes`，写 `id`、`name`、`type`。\n"
            "2. **加关系**：在 `edges` 里写 `from`、`to`、`relation`。\n"
            "3. **加资料**：新建 `materials/<id>.md`（双语可建 `<id>.zh.md` / `<id>.en.md`）。\n"
            "4. **加图片**：把图片命名为 `<id>.jpg` 放进 `assets/`。\n\n"
            "保存后 3 秒内页面会自动更新，无需重启。"
        ),
        "type_unknown": "未分类",
        "reset_chat": "清空对话",
        "entity_removed": "这条消息关联的实体已从 kg.json 中删除。",
        "footer": "数据存放在 kg.json、materials/、assets/ 中，保存后页面会自动刷新。",
    },
    "en": {
        "app_title": "RedTrace AI",
        "badge": "Hunan First Normal School · Red Culture Knowledge Graph",
        "subtitle": "A knowledge graph and smart study platform for Hunan First Normal School's red culture",
        "tags": "Relation mining · Figure tracing · AI-planned routes",
        "language": "Language / 语言",
        "settings": "Settings",
        "nav": "Page",
        "page_chat": "Chat",
        "page_graph": "Knowledge graph",
        "page_study": "Study",
        "graph_hint": "Drag nodes to rearrange; click a node to highlight its relations. Colours show entity types.",
        "timeline_title": "Timeline of the Hunan First Normal years",
        "view_entity": "Pick an entity to ask about",
        "view_btn": "Open this entity",
        "choose_route": "Choose a route",
        "duration": "Duration",
        "pois_count": "stops",
        "map_note": "Marker positions are approximate, for orientation only. Tiles come from OpenStreetMap; offline, only markers and the route are drawn.",
        "poi_list": "Stops and notes",
        "open_entity": "Open entity card",
        "tasks": "Route tasks",
        "quiz": "Quick quiz",
        "quiz_new": "New questions",
        "quiz_submit": "Submit answers",
        "quiz_score": "Score",
        "quiz_need_all": "Please answer every question.",
        "quiz_all_right": "All correct — well done!",
        "export": "Export study report (docx)",
        "export_ready": "Report ready — download it below.",
        "download": "Download report",
        "correct": "Correct answer",
        "no_image": "(no image yet)",
        "custom_route": "AI-planned route",
        "custom_hint": "Pick an interest and a duration; the route is planned by matching entity types and ordering stops by C-BFS hop distance.",
        "interest": "Interest",
        "interest_person": "People",
        "interest_place": "Sites",
        "interest_event": "Events",
        "interest_concept": "Ideas",
        "hours": "Duration",
        "hours_unit": "hours",
        "start_from": "Start from",
        "generate": "Plan my route",
        "custom_match": "theme match",
        "custom_hops": "{n} hop(s) from previous stop",
        "export_custom": "Export this route's report",
        "data_status": "Data status",
        "entities": "Entities",
        "relations": "Relations",
        "rel_types": "Relation types",
        "updated": "Last update",
        "auto_refresh": "Auto refresh (update the page when files are saved)",
        "reload_now": "Reload now",
        "reloaded": "Latest data loaded.",
        "data_changed": "Data files changed — page updated automatically.",
        "placeholder": "Try: Mao Zedong, cold water bath, the well of HNFS…",
        "welcome": "Ask about a person, a site or an event, and I will map out the relations behind it.",
        "examples": "Try asking",
        "not_found": "That entity is not in the knowledge base yet.",
        "try_these": "Did you mean:",
        "no_relations": "No relations yet.",
        "out_relations": "Direct relations (this entity → others)",
        "in_relations": "Incoming relations (others → this entity)",
        "more": "+{n} more",
        "two_hop": "Indirect relations (two-hop paths)",
        "sources": "Sources",
        "raw_c": "Raw output from the C layer",
        "path_tool": "Path between two entities (C BFS shortest path)",
        "path_from": "From",
        "path_to": "To",
        "path_btn": "Find the path",
        "path_hops": "{n} hop(s)",
        "path_same": "The two entities are the same.",
        "path_none": "There is no connecting path between these two entities.",
        "path_time": "C BFS time",
        "path_time_py": "Python BFS time",
        "engine": "Engine",
        "engine_c": "C kernel (graph.dll)",
        "engine_py": "Python fallback (C not compiled)",
        "path_unsupported": "This graph engine does not support path queries.",
        "path_caption": "Computed by BFS in graph.c; a reversed edge is shown as ←.",
        "material_missing": "No detailed material yet. Add `materials/{id}.md` and it will appear here.",
        "c_core": "C core",
        "c_core_info": "Adjacency list + `query_neighbors()`, compiled from `graph.c` into `graph.dll` and "
                       "called through ctypes — the lookup happens in C. A fresh DLL copy is loaded "
                       "whenever the data changes, so no restart is needed.",
        "howto": "How to add material / images",
        "howto_body": (
            "1. **Entity** — edit `nodes` in `kg.json` (`id`, `name`, `type`).\n"
            "2. **Relation** — edit `edges` in `kg.json` (`from`, `to`, `relation`).\n"
            "3. **Material** — add `materials/<id>.md` (bilingual: `<id>.zh.md` / `<id>.en.md`).\n"
            "4. **Image** — put `<id>.jpg` into `assets/`.\n\n"
            "Save the file and the page refreshes itself within 3 seconds."
        ),
        "type_unknown": "Uncategorised",
        "reset_chat": "Clear chat",
        "entity_removed": "The entity behind this message was removed from kg.json.",
        "footer": "All data lives in kg.json, materials/ and assets/ — save a file and the page refreshes itself.",
    },
}

TYPE_LABELS = {
    "PERSON": ("人物", "Person"),
    "PLACE": ("旧址 · 场景", "Place"),
    "EVENT": ("事件", "Event"),
    "ORG": ("组织", "Organisation"),
    "CONCEPT": ("精神 · 理念", "Concept"),
    "WORK": ("文献 · 作品", "Work"),
}

PAGES = ("chat", "graph", "study")

REL_LABELS = {
    "FOUNDED": ("创办", "Founded"),
    "CLASSMATE_OF": ("同学", "Classmate of"),
    "TEACHER_OF": ("老师", "Teacher of"),
    "STUDIED_AT": ("在此求学", "Studied at"),
    "PARTICIPATED_IN": ("参与", "Took part in"),
    "ADVOCATED": ("倡导", "Advocated"),
    "WROTE": ("撰写", "Wrote"),
    "LOCATED_IN": ("位于", "Located in"),
    "MEMBER_OF": ("成员", "Member of"),
    "PREDECESSOR_OF": ("前身", "Predecessor of"),
    "RELATED_TO": ("相关", "Related to"),
    "FRIEND_OF": ("挚友", "Friend of"),
    "PARTNER_OF": ("伴侣", "Partner of"),
    "PRACTICED_AT": ("在此实践", "Practised at"),
    "INFLUENCED": ("影响", "Influenced"),
    "MOTTO_OF": ("校训", "Motto of"),
    "EMBODIED_BY": ("体现", "Embodied by"),
    "USED_AS_TEXTBOOK": ("用作教材", "Used as textbook"),
    "PART_OF": ("属于", "Part of"),
}


def rel_label(rel: str, lang: str) -> str:
    pair = REL_LABELS.get(rel)
    return pair[0] if lang == "zh" else pair[1] if pair else rel


def type_label(node_type: str, lang: str) -> str:
    pair = TYPE_LABELS.get(str(node_type).upper())
    if not pair:
        return TEXT[lang]["type_unknown"]
    return pair[0] if lang == "zh" else pair[1]


def display_name(node: dict, lang: str) -> str:
    """实体显示名：英文界面用 name_en（没写就回退中文名）。"""
    if lang == "en":
        return node.get("name_en") or node["name"]
    return node["name"]


def image_credit(node: dict, lang: str) -> str:
    if lang == "en":
        return node.get("image_credit_en") or node.get("image_credit") or ""
    return node.get("image_credit") or node.get("image_credit_en") or ""


def timestamp_text(mtime: float) -> str:
    """把 mtime 显示成「2026-10-24 13:24」而不是一串数字。"""
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError, OverflowError):
        return "-"


# ============================================================
# 2. 视觉样式
# ============================================================
def find_bg() -> str | None:
    for name in BG_CANDIDATES:
        path = os.path.join(ASSETS, name)
        if os.path.exists(path):
            return path
    return None


def bg_data_uri() -> str:
    """把背景图内联成 data URI，省去静态文件服务的路径问题。"""
    path = find_bg()
    if not path:
        return ""
    lower = path.lower()
    mime = "image/png" if lower.endswith(".png") else \
           "image/webp" if lower.endswith(".webp") else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


CSS = """
<style>
:root {
    --ink: #f5ebe6;
    --muted: #d7bdb6;
    --gold: #e8c07d;
    --accent: #d8452f;
    --glass: rgba(28, 12, 14, 0.55);
    --line: rgba(232, 192, 125, 0.22);
}

/* ---------- 背景 ---------- */
[data-testid="stAppViewContainer"] {
    background-image:
        linear-gradient(180deg, rgba(8,4,5,.58) 0%, rgba(8,4,5,.72) 45%, rgba(8,4,5,.86) 100%),
        __BG__;
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], #MainMenu, footer { display: none; }
[data-testid="stMainBlockContainer"], .block-container {
    padding-top: 1.6rem;
    padding-bottom: 4.5rem;
    max-width: 1120px;
    margin: 0 auto;
}

/* ---------- 侧边栏 ---------- */
[data-testid="stSidebar"] {
    background: rgba(16, 7, 8, 0.72);
    border-right: 1px solid var(--line);
    backdrop-filter: blur(10px);
}
[data-testid="stSidebarContent"], [data-testid="stSidebarUserContent"] { background: transparent; }
[data-testid="stSidebar"] * { color: var(--ink); }
[data-testid="stSidebar"] .stButton > button { width: 100%; }

/* ---------- 文字 ---------- */
h1, h2, h3, h4 { color: var(--ink); letter-spacing: .01em; }
p, li, span, label { color: var(--ink); }
a { color: var(--gold) !important; text-decoration: none; border-bottom: 1px dotted rgba(232,192,125,.45); }
a:hover { color: #fff1cf !important; }
code { background: rgba(232,192,125,.12); color: #ffe9bd; border-radius: 4px; }

/* ---------- 顶部主视觉 ---------- */
.hero {
    position: relative;
    padding: 1.5rem 1.7rem 1.35rem;
    margin-bottom: 1.1rem;
    border-radius: 22px;
    border: 1px solid var(--line);
    background: linear-gradient(140deg, rgba(126, 28, 24, .55), rgba(22, 9, 11, .62) 62%);
    box-shadow: 0 20px 50px rgba(0, 0, 0, .38);
    backdrop-filter: blur(7px);
}
.hero .badge {
    display: inline-block;
    font-size: .74rem;
    letter-spacing: .16em;
    color: var(--gold);
    border: 1px solid rgba(232,192,125,.4);
    padding: .24rem .7rem;
    border-radius: 999px;
    background: rgba(232,192,125,.07);
}
.hero h1 { margin: .65rem 0 .45rem; font-size: clamp(1.5rem, 2.5vw, 2.1rem); line-height: 1.25; }
.hero h1 .h1-en {
    font-size: .48em;
    letter-spacing: .06em;
    color: var(--gold);
    font-weight: 500;
    margin-left: .25rem;
    vertical-align: middle;
    opacity: .92;
}
.hero p { margin: 0; color: var(--muted); font-size: .95rem; }
.hero-tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .7rem; }
.hero-tag {
    font-size: .76rem;
    color: #ffe7c4;
    border: 1px solid rgba(232,192,125,.38);
    background: rgba(232,192,125,.1);
    border-radius: 999px;
    padding: .2rem .65rem;
    letter-spacing: .02em;
}
.hero::after {
    content: "";
    position: absolute; inset: 0;
    border-radius: 22px;
    background: radial-gradient(120% 80% at 88% 10%, rgba(232,192,125,.16), transparent 60%);
    pointer-events: none;
}

/* ---------- 统计条 ---------- */
.stats { display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 1.2rem; }
.stats .chip {
    font-size: .82rem;
    color: var(--muted);
    background: rgba(255,255,255,.05);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: .3rem .8rem;
}
.stats .chip b { color: var(--gold); font-weight: 600; }

/* ---------- 聊天气泡 ---------- */
[data-testid="stChatMessage"] {
    background: var(--glass);
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 18px;
    padding: .95rem 1.15rem;
    margin-bottom: .75rem;
    backdrop-filter: blur(8px);
    box-shadow: 0 10px 28px rgba(0,0,0,.25);
}
[data-testid="stChatMessage"] p { line-height: 1.75; }

/* ---------- 实体标题 ---------- */
.ent-head { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin-bottom: .35rem; }
.ent-name { font-size: 1.28rem; font-weight: 600; color: #fff6ec; letter-spacing: .02em; }
.ent-type {
    font-size: .74rem;
    color: var(--gold);
    border: 1px solid rgba(232,192,125,.4);
    background: rgba(232,192,125,.1);
    padding: .12rem .55rem;
    border-radius: 999px;
}
.section-title {
    font-size: .82rem;
    letter-spacing: .12em;
    color: var(--gold);
    text-transform: uppercase;
    margin: 1rem 0 .5rem;
    opacity: .9;
}

/* ---------- 两点路径 ---------- */
.path-head { display: flex; align-items: center; gap: .55rem; flex-wrap: wrap; margin-bottom: .2rem; }
.path-badge {
    font-size: .74rem;
    color: #1a0b0c;
    background: var(--gold);
    border-radius: 999px;
    padding: .12rem .6rem;
    font-weight: 600;
}
.pathline { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; margin: .65rem 0 .8rem; }
.pathline .pn {
    background: rgba(232,192,125,.14);
    border: 1px solid rgba(232,192,125,.42);
    color: #fff3e2;
    border-radius: 999px;
    padding: .3rem .8rem;
    font-size: .95rem;
    white-space: nowrap;
}
.pathline .pr { color: var(--gold); font-size: .8rem; letter-spacing: .03em; }

/* ---------- 按钮 ---------- */
.stButton > button {
    border-radius: 999px;
    border: 1px solid rgba(232,192,125,.32);
    background: rgba(255,255,255,.05);
    color: var(--ink);
    font-size: .88rem;
    padding: .32rem .85rem;
    transition: all .18s ease;
}
.stButton > button:hover {
    border-color: var(--gold);
    background: rgba(232,192,125,.16);
    color: #fff8ec;
    transform: translateY(-1px);
}

/* ---------- 输入框 ---------- */
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stChatInput"] {
    background: rgba(26, 11, 13, .82);
    border: 1px solid rgba(232,192,125,.3);
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 12px 30px rgba(0,0,0,.4);
    backdrop-filter: blur(8px);
}
[data-testid="stChatInput"] div[data-baseweb="textarea"] { background: transparent; }
[data-testid="stChatInput"] textarea { color: var(--ink) !important; }
[data-testid="stChatInput"] textarea::placeholder { color: rgba(215,189,182,.65) !important; }

/* ---------- 其它组件 ---------- */
[data-testid="stExpander"] details {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(255,255,255,.04);
}
[data-testid="stAlert"] { border-radius: 14px; }
hr { border-color: var(--line); }
.stRadio [role="radiogroup"] { gap: .35rem; }
img { border-radius: 14px; }
</style>
"""


def inject_css() -> None:
    uri = bg_data_uri()
    bg = f'url("{uri}")' if uri else \
        "linear-gradient(160deg, #3a0f10 0%, #1a0708 55%, #120506 100%)"
    st.markdown(CSS.replace("__BG__", bg), unsafe_allow_html=True)


# ============================================================
# 3. 数据加载（按文件指纹缓存 + 自动失效）
# ============================================================
def iter_material_files() -> list[str]:
    if not os.path.isdir(MATERIALS):
        return []
    return sorted(
        os.path.join(MATERIALS, f)
        for f in os.listdir(MATERIALS)
        if f.lower().endswith(".md")
    )


def iter_asset_files() -> list[str]:
    if not os.path.isdir(ASSETS):
        return []
    return sorted(
        os.path.join(ASSETS, f)
        for f in os.listdir(ASSETS)
        if f.lower().endswith(IMG_EXTS)
    )


def data_signature() -> str:
    """kg.json + materials + assets + content 的指纹；任何改动都会触发重新加载。"""
    h = hashlib.sha1()
    extra = []
    content_dir = os.path.join(ROOT, "content")
    if os.path.isdir(content_dir):
        extra = [os.path.join(content_dir, f) for f in sorted(os.listdir(content_dir))
                 if f.endswith(".json")]
    for path in [KG_PATH, *iter_material_files(), *iter_asset_files(), *extra]:
        try:
            info = os.stat(path)
        except OSError:
            continue
        h.update(f"{os.path.basename(path)}|{info.st_mtime_ns}|{info.st_size};".encode())
    return h.hexdigest()[:16]


def build_index(kg: dict) -> dict:
    nodes = {n["id"]: n for n in kg["nodes"]}
    aliases: dict[str, str] = {}
    for nid, node in nodes.items():
        for alias in [nid, node["name"], *node.get("aliases", [])]:
            alias = str(alias).strip()
            if alias:
                aliases.setdefault(alias, nid)

    out_edges: dict[str, list[tuple[str, str]]] = {nid: [] for nid in nodes}
    in_edges: dict[str, list[tuple[str, str]]] = {nid: [] for nid in nodes}
    for e in kg["edges"]:
        if e["from"] in nodes and e["to"] in nodes:
            out_edges[e["from"]].append((e["to"], e["relation"]))
            in_edges[e["to"]].append((e["from"], e["relation"]))

    return {
        "nodes": nodes,
        "aliases": aliases,
        "out": out_edges,
        "in": in_edges,
        "rel_types": sorted({e["relation"] for e in kg["edges"]}),
        "kg": kg,
    }


def load_core(root: str):
    """按文件路径重新加载 c_core.py，然后调用 build_and_load(root)。

    为什么不用 `import c_core`：Streamlit 的热重跑只重新执行主脚本，
    已经 import 过的模块会一直留在进程里（sys.modules）。改了 c_core.py 之后，
    正在运行的服务里仍然是旧版函数，于是报
        build_and_load() takes 0 positional arguments but 1 was given
    这里每次都从磁盘按路径 exec 一份最新的 c_core.py，
    所以升级代码后只要刷新页面就会自动生效，不必重启服务。
    """
    import importlib.util
    import sys as _sys

    path = os.path.join(root, "c_core.py")
    if not os.path.exists(path):
        raise RuntimeError(f"找不到 c_core.py：{path}")

    name = "_c_core_runtime"          # 固定名字，重复 exec 不会在 sys.modules 里堆积
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 c_core.py：{path}")
    module = importlib.util.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)

    try:
        return module.build_and_load(root)
    except TypeError as exc:
        if "positional" in str(exc):
            raise RuntimeError(
                "运行中的服务仍在用旧版 c_core.py，且自动重载失败。\n"
                "请关闭终端（Ctrl+C）后重新运行 start.bat。"
            ) from exc
        raise


@st.cache_resource(show_spinner=False, max_entries=3)
def load_bundle(signature: str) -> dict:
    """签名变 → 重新读 kg.json 并重新加载 C 内核（新副本，全局状态是干净的）。"""
    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)
    lib = load_core(ROOT)
    index = build_index(kg)
    index["lib"] = lib
    index["mtime"] = os.path.getmtime(KG_PATH)
    return index


def get_material(node_id: str, lang: str) -> tuple[str | None, str | None]:
    """materials/<id>.<lang>.md 优先，其次 materials/<id>.md。"""
    for name in (f"{node_id}.{lang}.md", f"{node_id}.md"):
        path = os.path.join(MATERIALS, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                return text, name
    return None, None


def resolve_image(node: dict) -> str | None:
    """先看 kg.json 的 image 字段，再按 assets/<id>.<ext> 自动匹配。"""
    declared = str(node.get("image") or "").strip()
    if declared and not declared.lower().startswith("placeholder"):
        path = os.path.join(ASSETS, declared)
        if os.path.exists(path):
            return path
    for ext in IMG_EXTS:
        path = os.path.join(ASSETS, node["id"] + ext)
        if os.path.exists(path):
            return path
    return None


def find_entity(prompt: str, index: dict) -> str | None:
    """最长别名优先命中（避免「湖南第一师范旧址」被「第一师范旧址」抢走）。"""
    text = prompt.strip().lower()
    if not text:
        return None
    best_key, best_id = (-1, 0), None
    for alias, nid in index["aliases"].items():
        pos = text.find(alias.lower())
        if pos != -1:
            key = (len(alias), -pos)
            if key > best_key:
                best_key, best_id = key, nid
    return best_id


def find_all_entities(prompt: str, index: dict) -> list[str]:
    text = prompt.strip().lower()
    hits: list[tuple[int, int, str]] = []
    for alias, nid in index["aliases"].items():
        pos = text.find(alias.lower())
        if pos != -1:
            hits.append((pos, -len(alias), nid))
    hits.sort()
    seen, out = set(), []
    for _, _, nid in hits:
        if nid not in seen:
            seen.add(nid)
            out.append(nid)
    return out


def two_hop_paths(node_id: str, index: dict, limit: int = 10) -> list[tuple[str, str]]:
    """本实体 → 中间实体 → 目标 的两跳路径（返回 id，显示时再按语言取名）。"""
    seen, paths = set(), []
    for mid, _ in index["out"].get(node_id, []):
        for target, _ in index["out"].get(mid, []):
            if target in (node_id, mid):
                continue
            key = (mid, target)
            if key in seen:
                continue
            seen.add(key)
            paths.append((mid, target))
    return paths[:limit]


# ============================================================
# 4. 界面组件
# ============================================================
def stats_html(index: dict, lang: str) -> str:
    t = TEXT[lang]
    return (
        f'<div class="stats">'
        f'<span class="chip">{t["entities"]} <b>{len(index["nodes"])}</b></span>'
        f'<span class="chip">{t["relations"]} <b>{len(index["kg"]["edges"])}</b></span>'
        f'<span class="chip">{t["rel_types"]} <b>{len(index["rel_types"])}</b></span>'
        f'</div>'
    )


def render_relation_chips(pairs, index, lang, prefix, columns=3, max_show=18) -> None:
    """关联实体做成一排可点的按钮，点一下就能继续追问。"""
    nodes = index["nodes"]
    shown = pairs[:max_show]
    for row in itertools.batched(shown, columns):
        cols = st.columns(len(row))
        for col, (target_id, rel) in zip(cols, row):
            with col:
                target_node = nodes[target_id]
                label = f"{display_name(target_node, lang)} · {rel_label(rel, lang)}"
                if st.button(label, key=f"{prefix}-{target_id}-{rel}", width="stretch"):
                    # 用英文名继续追问时，match 走 aliases（kg.json 里已含 name_en）
                    st.session_state["_pending"] = display_name(target_node, lang)
                    st.rerun()
    if len(pairs) > max_show:
        st.caption(TEXT[lang]["more"].format(n=len(pairs) - max_show))


def render_entity_card(entity_id: str, index: dict, lang: str, key_prefix: str) -> None:
    node = index["nodes"][entity_id]
    t = TEXT[lang]
    image_path = resolve_image(node)

    if image_path:
        left, right = st.columns([3, 1])
    else:
        left, right = st.container(), None

    with left:
        st.markdown(
            f'<div class="ent-head"><span class="ent-name">{display_name(node, lang)}</span>'
            f'<span class="ent-type">{type_label(node.get("type", ""), lang)}</span></div>',
            unsafe_allow_html=True,
        )
        material, _ = get_material(entity_id, lang)
        if material:
            st.markdown(material)
        elif node.get("desc"):
            desc = node.get("desc_en") or node["desc"] if lang == "en" else node["desc"]
            st.markdown(str(desc))
        else:
            st.caption(t["material_missing"].format(id=entity_id))

    if right is not None:
        with right:
            st.image(image_path, width="stretch",
                     caption=image_credit(node, lang) or None)

    out_pairs = index["out"].get(entity_id, [])
    in_pairs = index["in"].get(entity_id, [])

    if out_pairs:
        st.markdown(f'<div class="section-title">{t["out_relations"]}</div>',
                    unsafe_allow_html=True)
        render_relation_chips(out_pairs, index, lang, f"{key_prefix}-out")

    if in_pairs:
        st.markdown(f'<div class="section-title">{t["in_relations"]}</div>',
                    unsafe_allow_html=True)
        render_relation_chips(in_pairs, index, lang, f"{key_prefix}-in")

    if not out_pairs and not in_pairs:
        st.caption(t["no_relations"])

    paths = two_hop_paths(entity_id, index)
    if paths:
        with st.expander(f"{t['two_hop']} · {len(paths)}"):
            st.markdown("\n".join(
                f"- {display_name(node, lang)} → **{display_name(index['nodes'][mid], lang)}**"
                f" → **{display_name(index['nodes'][target], lang)}**"
                for mid, target in paths
            ))

    sources = node.get("sources") or []
    if sources:
        st.markdown(f'<div class="section-title">{t["sources"]}</div>', unsafe_allow_html=True)
        st.markdown("\n".join(f"- [{s}]({s})" for s in sources))

    lib = index.get("lib")
    if lib is not None:
        with st.expander(t["raw_c"]):
            count, raw = lib.query_raw(entity_id)
            st.caption(f'query_neighbors("{entity_id}", buf, 16384) → {count}')
            st.code(raw or "(empty)", language="text")


def make_path_message(a_id: str, b_id: str, index: dict) -> dict:
    """调用 C 语言的 BFS 求两点最短路径，顺带记录 C 侧耗时。"""
    msg = {"role": "assistant", "kind": "path", "from": a_id, "to": b_id,
           "hops": -2, "steps": [], "elapsed_us": 0.0}
    lib = index.get("lib")
    if lib is None:
        return msg
    started = time.perf_counter()
    hops, steps = lib.find_path(a_id, b_id)
    msg["elapsed_us"] = (time.perf_counter() - started) * 1e6
    msg["hops"] = hops
    msg["steps"] = steps
    return msg


def render_path_card(msg: dict, index: dict, lang: str) -> None:
    """把 BFS 结果画成「实体 —关系→ 实体」的链路。"""
    t = TEXT[lang]
    nodes = index["nodes"]
    if msg.get("from") not in nodes or msg.get("to") not in nodes:
        st.warning(t["entity_removed"])
        return

    a = display_name(nodes[msg["from"]], lang)
    b = display_name(nodes[msg["to"]], lang)
    hops = msg.get("hops", -2)

    if hops == -2:
        st.markdown(f"**{a}** ↔ **{b}**")
        st.caption(t["path_unsupported"])
        return
    if hops < 0:
        st.markdown(f"**{a}** ↔ **{b}**")
        st.caption(t["path_none"])
        return
    if hops == 0:
        st.markdown(f"**{a}**")
        st.caption(t["path_same"])
        return

    chips = [f'<span class="pn">{a}</span>']
    for _, rel, nxt, reversed_ in msg["steps"]:
        label = rel_label(rel, lang)
        arrow = f"← {label} —" if reversed_ else f"— {label} →"
        chips.append(f'<span class="pr">{arrow}</span>')
        chips.append(f'<span class="pn">{display_name(nodes[nxt], lang)}</span>')

    st.markdown(
        f'<div class="path-head"><span class="path-badge">{t["path_hops"].format(n=hops)}</span>'
        f'<span class="ent-name">{a}</span><span class="pr">↔</span>'
        f'<span class="ent-name">{b}</span></div>'
        f'<div class="pathline">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )
    engine = getattr(index.get("lib"), "engine", "c")
    time_label = t["path_time"] if engine == "c" else t["path_time_py"]
    st.caption(f'{time_label} {msg.get("elapsed_us", 0):.2f} µs · {t["path_caption"]}')


def render_message(msg: dict, index: dict, lang: str, idx: int) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        elif msg.get("kind") == "entity":
            # 实体可能已经从 kg.json 里删掉了，历史消息要优雅降级而不是整页报错
            if msg["entity_id"] in index["nodes"]:
                render_entity_card(msg["entity_id"], index, lang, f"m{idx}")
            else:
                st.warning(TEXT[lang]["entity_removed"])
        elif msg.get("kind") == "path":
            render_path_card(msg, index, lang)
        else:
            st.markdown(msg.get("text", ""))
            for name in msg.get("suggestions", []):
                if st.button(name, key=f"sug-{idx}-{name}"):
                    st.session_state["_pending"] = name
                    st.rerun()


def answer(prompt: str, index: dict, lang: str) -> dict:
    t = TEXT[lang]
    entity_id = find_entity(prompt, index)
    if not entity_id:
        display = [display_name(n, lang) for n in index["kg"]["nodes"]]
        close = difflib.get_close_matches(prompt.strip(), display, n=3, cutoff=0.3)
        text = f"⚠️ {t['not_found']}"
        if close:
            text += "\n\n" + t["try_these"] + " " + " / ".join(f"**{c}**" for c in close)
        return {"role": "assistant", "kind": "notice", "text": text, "suggestions": close}

    others = [e for e in find_all_entities(prompt, index) if e != entity_id]
    if others:
        # 一句话里出现两个实体 → 交给 C 的 BFS 算最短路径
        return make_path_message(entity_id, others[0], index)

    return {"role": "assistant", "kind": "entity", "entity_id": entity_id}


def sidebar(index: dict, lang: str) -> bool:
    t = TEXT[lang]
    with st.sidebar:
        st.markdown(f"### ⚙️ {t['settings']}")

        options = ["zh", "en"]
        labels = {"zh": "中文", "en": "English"}
        picked = st.radio(
            t["language"], options,
            index=options.index(st.session_state.lang),
            format_func=lambda code: labels[code],
            horizontal=True, key="lang_choice",
        )
        if picked != st.session_state.lang:
            st.session_state.lang = picked
            st.rerun()

        st.divider()
        st.markdown(f"#### 🧭 {t['nav']}")
        page_labels = {"chat": f"💬 {t['page_chat']}",
                       "graph": f"🕸️ {t['page_graph']}",
                       "study": f"🎒 {t['page_study']}"}
        page = st.radio(
            t["nav"], list(PAGES), index=list(PAGES).index(st.session_state.page),
            format_func=lambda code: page_labels[code],
            key="page_choice", label_visibility="collapsed",
        )
        if page != st.session_state.page:
            st.session_state.page = page
            st.rerun()

        st.divider()
        st.markdown(f"#### 📊 {t['data_status']}")
        st.markdown(stats_html(index, lang), unsafe_allow_html=True)

        auto = st.toggle(t["auto_refresh"], value=True, key="auto_refresh")
        if st.button(f"🔄 {t['reload_now']}", width="stretch"):
            load_bundle.clear()
            st.session_state["_flash"] = t["reloaded"]
            st.rerun()
        if st.button(f"🧹 {t['reset_chat']}", width="stretch"):
            st.session_state.messages = []
            st.session_state.pop("_flash", None)
            st.rerun()

        st.divider()
        # 「怎么加资料/图片」「C 语言内核」两块属于开发说明，默认收进后台不显示；
        # 需要时用环境变量 RED_AGENT_DEV=1 启动即可重新出现在侧边栏。
        if DEV_PANELS:
            with st.expander(f"📚 {t['howto']}", expanded=False):
                st.markdown(t["howto_body"])

            with st.expander(f"🧩 {t['c_core']}", expanded=False):
                st.caption(t["c_core_info"])
                lib = index.get("lib")
                if lib is not None:
                    engine = getattr(lib, "engine", "c")
                    engine_label = t["engine_c"] if engine == "c" else t["engine_py"]
                    if lang == "en":
                        text = (f"engine: {engine_label}\n"
                                f"graph copy: _runtime/graph_{lib.signature}.dll\n"
                                f"data signature: {lib.signature}")
                    else:
                        text = (f"内核引擎：{engine_label}\n"
                                f"graph.dll 副本：_runtime/graph_{lib.signature}.dll\n"
                                f"数据签名：{lib.signature}")
                    st.code(text, language="text")

        sep = ": " if lang == "en" else "："
        st.caption(f"{t['updated']}{sep}{timestamp_text(index['mtime'])}")
    return auto


# ============================================================
# 4.5 内容数据（时间轴 / 研学路线 / 题库）
# ============================================================
def _load_json(rel: str, default):
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def pick_text(obj: dict, key: str, lang: str) -> str:
    """按语言取字段：key_en 优先，没有就回退 key。"""
    if lang == "en":
        value = obj.get(key + "_en")
        if value:
            return value
    return obj.get(key, "") or ""


def load_timeline(lang: str) -> list[dict]:
    items = _load_json("content/timeline.json", []) or []
    return [{"year": it.get("year", ""),
             "label": pick_text(it, "label", lang),
             "text": pick_text(it, "text", lang),
             "entity": it.get("entity", "")} for it in items]


def load_routes(lang: str, index: dict) -> list[dict]:
    """把 routes.json 本地化，并把点位补上实体图片与资料。"""
    data = _load_json("content/routes.json", {}) or {}
    pois = data.get("pois") or {}
    out = []
    for route in data.get("routes") or []:
        ordered = []
        for pid in route.get("pois", []):
            poi = pois.get(pid)
            if not poi:
                continue
            node = index["nodes"].get(poi.get("entity", ""), {})
            image = poi.get("image") or node.get("image") or (poi.get("entity", "") + ".jpg")
            ordered.append({
                "id": pid,
                "entity": poi.get("entity", ""),
                "name": pick_text(poi, "name", lang),
                "addr": pick_text(poi, "addr", lang),
                "intro": pick_text(poi, "intro", lang),
                "lat": poi.get("lat"), "lng": poi.get("lng"),
                "image": image,
                "has_image": os.path.exists(os.path.join(ASSETS, image)),
            })
        out.append({
            "id": route.get("id", ""),
            "title": pick_text(route, "title", lang),
            "duration": pick_text(route, "duration", lang),
            "summary": pick_text(route, "summary", lang),
            "tasks": (route.get("tasks_en") if lang == "en" and route.get("tasks_en")
                      else route.get("tasks", [])),
            "pois": ordered,
        })
    return out


def load_quiz(lang: str) -> list[dict]:
    data = _load_json("content/quiz.json", []) or []
    out = []
    for q in data:
        out.append({
            "id": q.get("id", ""),
            "entity": q.get("entity", ""),
            "q": pick_text(q, "q", lang),
            "options": q.get("options_en") if lang == "en" and q.get("options_en")
                       else q.get("options", []),
            "answer": int(q.get("answer", 0)),
            "explain": pick_text(q, "explain", lang),
        })
    return out


# ============================================================
# 4.6 三个页面
# ============================================================
def render_chat_page(index: dict, lang: str, t: dict) -> None:
    for i, msg in enumerate(st.session_state.messages):
        render_message(msg, index, lang, i)

    if not st.session_state.messages:
        st.markdown(f"#### 👋 {t['examples']}")
        st.caption(t["welcome"])
        picks = [display_name(n, lang) for n in index["kg"]["nodes"][:4]]
        cols = st.columns(len(picks))
        for col, name in zip(cols, picks):
            with col:
                if st.button(name, key=f"ex-{name}", width="stretch"):
                    st.session_state["_pending"] = name
                    st.rerun()

    st.caption(t["footer"])

    # ---- 两点路径工具（C 语言 BFS） ----
    with st.expander(f"🧭 {t['path_tool']}", expanded=False):
        ids = list(index["nodes"])
        c1, c2, c3 = st.columns([3, 3, 2])
        a_id = c1.selectbox(
            t["path_from"], ids, key="path_from",
            format_func=lambda i: display_name(index["nodes"][i], lang),
        )
        b_id = c2.selectbox(
            t["path_to"], ids, key="path_to", index=min(1, len(ids) - 1),
            format_func=lambda i: display_name(index["nodes"][i], lang),
        )
        if c3.button(t["path_btn"], width="stretch"):
            st.session_state.messages.append({
                "role": "user",
                "content": f"{display_name(index['nodes'][a_id], lang)} ↔ "
                           f"{display_name(index['nodes'][b_id], lang)}",
            })
            st.session_state.messages.append(make_path_message(a_id, b_id, index))
            st.rerun()
        st.caption(t["path_caption"])

    prompt = st.chat_input(t["placeholder"])
    if not prompt:
        prompt = st.session_state.pop("_pending", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append(answer(prompt, index, lang))
        st.rerun()


def goto_page(name: str) -> None:
    """程序化切换页面：必须清掉 radio 的控件状态，否则它会覆盖回去。"""
    st.session_state.page = name
    st.session_state.pop("page_choice", None)
    st.rerun()


def render_graph_page(index: dict, lang: str, t: dict) -> None:
    st.markdown(f"#### 🕸️ {t['page_graph']}")
    st.caption(t["graph_hint"])

    nodes_payload = [
        {"id": nid, "label": display_name(node, lang),
         "type": (node.get("type") or "CONCEPT").upper()}
        for nid, node in index["nodes"].items()
    ]
    edges_payload = [
        {"s": e["from"], "t": e["to"], "rel": rel_label(e["relation"], lang)}
        for e in index["kg"]["edges"]
        if e["from"] in index["nodes"] and e["to"] in index["nodes"]
    ]
    legend = {k: (v[0] if lang == "zh" else v[1]) for k, v in TYPE_LABELS.items()}
    components.html(
        ui_graph.graph_component(nodes_payload, edges_payload, legend, height=640),
        height=650, scrolling=False,
    )

    ids = list(index["nodes"])
    c1, c2 = st.columns([4, 1])
    picked = c1.selectbox(
        t["view_entity"], ids, key="graph_pick",
        format_func=lambda i: display_name(index["nodes"][i], lang),
    )
    if c2.button(t["view_btn"], width="stretch"):
        st.session_state.messages.append(
            {"role": "user", "content": display_name(index["nodes"][picked], lang)})
        st.session_state.messages.append(
            {"role": "assistant", "kind": "entity", "entity_id": picked})
        goto_page("chat")

    st.markdown(f"#### 🕰️ {t['timeline_title']}")
    items = load_timeline(lang)
    if items:
        st.markdown(ui_graph.timeline_html(items), unsafe_allow_html=True)


def _all_pois(lang: str, index: dict) -> list[dict]:
    """把三条路线里的点位去重合并（地图/定制路线共用）。"""
    seen, out = set(), []
    for route in load_routes(lang, index):
        for poi in route["pois"]:
            if poi["id"] not in seen:
                seen.add(poi["id"])
                out.append(poi)
    return out


def _render_custom_route(index: dict, lang: str, t: dict) -> None:
    st.markdown(f"##### ✨ {t['custom_route']}")
    st.caption(t["custom_hint"])

    pois = _all_pois(lang, index)
    if not pois:
        st.info("content/routes.json 缺失")
        return

    kinds = [("PERSON", t["interest_person"]), ("PLACE", t["interest_place"]),
             ("EVENT", t["interest_event"]), ("CONCEPT", t["interest_concept"])]
    kind_labels = dict(kinds)
    c1, c2, c3 = st.columns([2, 3, 3])
    kind = c1.selectbox(t["interest"], [k for k, _ in kinds],
                        format_func=lambda k: kind_labels[k], key="cr_kind")
    hours = c2.radio(t["hours"], [2, 3, 4], index=1, horizontal=True,
                     format_func=lambda h: f"{h} {t['hours_unit']}", key="cr_hours")
    start = c3.selectbox(
        t["start_from"], [p["entity"] for p in pois], key="cr_start",
        format_func=lambda e: display_name(index["nodes"].get(e, {"name": e, "id": e}), lang),
    )

    if st.button(f"✨ {t['generate']}", key="cr_generate"):
        st.session_state["cr_result"] = custom_route.generate(index, pois, kind, hours, start)

    result = st.session_state.get("cr_result")
    if not result:
        return

    items = result["items"]
    st.markdown(f"**{t['custom_route']}** · {result['hours']} {t['hours_unit']} · "
                f"{len(items)} {t['pois_count']}")
    components.html(
        ui_map.map_component([it["poi"] for it in items], lang, height=420,
                             route_title=t["custom_route"], offline_note=t["map_note"]),
        height=480, scrolling=False,
    )

    for n, it in enumerate(items, 1):
        poi = it["poi"]
        with st.container(border=True):
            cimg, ctxt = st.columns([1, 3])
            with cimg:
                if poi["has_image"]:
                    st.image(os.path.join(ASSETS, poi["image"]), width="stretch")
                else:
                    st.caption(t["no_image"])
            with ctxt:
                badge = t["custom_match"] if it["match"] else ""
                st.markdown(f"**{n}. {poi['name']}**" + (f"　`{badge}`" if badge else ""))
                st.caption(f"{poi['addr']} · {t['custom_hops'].format(n=it['dist'])}")
                st.markdown(poi["intro"])

    with st.expander(f"✅ {t['tasks']}", expanded=True):
        flags = [st.checkbox(task, key=f"crtask-{result['hours']}-{result['kind']}-{j}")
                 for j, task in enumerate(custom_route.make_tasks(items, lang))]

    if st.button(f"📄 {t['export_custom']}", key="cr_export"):
        route = {"id": "custom", "title": t["custom_route"],
                 "summary": t["custom_hint"],
                 "duration": f"{result['hours']} {t['hours_unit']}",
                 "tasks": custom_route.make_tasks(items, lang)}
        data, fname, mime = report_mod.build_report(
            route, [it["poi"] for it in items], index["nodes"], lang, flags, [])
        st.session_state["cr_report"] = (data, fname, mime)

    stored = st.session_state.get("cr_report")
    if stored:
        st.success(t["export_ready"])
        st.download_button(t["download"], data=stored[0], file_name=stored[1],
                           mime=stored[2], key="cr_download")


def render_study_page(index: dict, lang: str, t: dict) -> None:
    st.markdown(f"#### 🎒 {t['page_study']}")

    # ---- AI 定制路线（放在最上面，作为默认入口）----
    _render_custom_route(index, lang, t)

    st.divider()
    routes = load_routes(lang, index)
    if not routes:
        st.info("content/routes.json 缺失")
        return

    st.markdown(f"##### 🗺️ {t['choose_route']}")
    labels = [f"{r['title']} · {len(r['pois'])} {t['pois_count']}" for r in routes]
    idx = st.selectbox(t["choose_route"], range(len(routes)),
                       format_func=lambda i: labels[i], key="route_sel",
                       label_visibility="collapsed")
    route = routes[idx]
    st.markdown(f"**{route['summary']}**")
    st.caption(f"{t['duration']}：{route['duration']}")

    components.html(
        ui_map.map_component(route["pois"], lang, height=480,
                             route_title=route["title"], offline_note=t["map_note"]),
        height=540, scrolling=False,
    )

    # ---- 点位讲解 ----
    st.markdown(f"#### 📍 {t['poi_list']}")
    for n, poi in enumerate(route["pois"], 1):
        with st.container(border=True):
            cimg, ctxt = st.columns([1, 3])
            with cimg:
                image_path = os.path.join(ASSETS, poi["image"])
                if poi["has_image"]:
                    st.image(image_path, width="stretch")
                else:
                    st.caption(t["no_image"])
            with ctxt:
                st.markdown(f"**{n}. {poi['name']}**")
                st.caption(poi["addr"])
                st.markdown(poi["intro"])
                if st.button(t["open_entity"], key=f"poi-{route['id']}-{poi['id']}"):
                    st.session_state.messages.append(
                        {"role": "user", "content": poi["name"]})
                    st.session_state.messages.append(
                        {"role": "assistant", "kind": "entity",
                         "entity_id": poi["entity"]})
                    goto_page("chat")

    # ---- 任务卡 ----
    with st.expander(f"✅ {t['tasks']}", expanded=True):
        done_flags = []
        for j, task in enumerate(route["tasks"]):
            done_flags.append(st.checkbox(task, key=f"task-{route['id']}-{j}"))

    # ---- 随堂测评 ----
    st.markdown(f"#### 📝 {t['quiz']}")
    quiz = load_quiz(lang)
    if not quiz:
        st.info("content/quiz.json 缺失")
        return

    quiz_key = f"quiz-{route['id']}-{lang}"
    picked_ids = st.session_state.get(quiz_key)
    if not picked_ids:
        picked_ids = [q["id"] for q in random.sample(quiz, min(5, len(quiz)))]
        st.session_state[quiz_key] = picked_ids

    by_id = {q["id"]: q for q in quiz}
    selected = [by_id[i] for i in picked_ids if i in by_id]

    if st.button(t["quiz_new"], key=f"newquiz-{route['id']}"):
        st.session_state[quiz_key] = [q["id"] for q in random.sample(quiz, min(5, len(quiz)))]
        st.session_state.pop(f"quizres-{route['id']}", None)
        st.rerun()

    answers = []
    for n, q in enumerate(selected, 1):
        answers.append(st.radio(
            f"{n}. {q['q']}", options=list(range(len(q["options"]))),
            index=None, key=f"ans-{route['id']}-{q['id']}",
            format_func=lambda k, opts=q["options"]: opts[k],
        ))

    if st.button(t["quiz_submit"], key=f"submit-{route['id']}"):
        if any(a is None for a in answers):
            st.warning(t["quiz_need_all"])
        else:
            rows = []
            for q, a in zip(selected, answers):
                rows.append({
                    "q": q["q"], "chosen": q["options"][a],
                    "answer": q["options"][q["answer"]],
                    "ok": a == q["answer"], "explain": q["explain"],
                    "entity": q["entity"],
                })
            st.session_state[f"quizres-{route['id']}"] = rows

    result = st.session_state.get(f"quizres-{route['id']}")
    score = 0
    if result:
        score = sum(1 for r in result if r["ok"])
        st.markdown(f"**{t['quiz_score']}：{score} / {len(result)}**")
        if score == len(result):
            st.success(t["quiz_all_right"])
        for n, row in enumerate(result, 1):
            mark = "✅" if row["ok"] else "❌"
            st.markdown(f"{mark} **{n}. {row['q']}**")
            st.caption(f"{t['quiz_score']}：{row['chosen']} ｜ "
                       f"{t['correct']}：{row['answer']}")
            if row["explain"]:
                st.caption(row["explain"])

    # ---- 导出小结 ----
    st.divider()
    if st.button(t["export"], key=f"export-{route['id']}"):
        rows = result or []
        data, fname, mime = report_mod.build_report(
            route, route["pois"], index["nodes"], lang, done_flags, rows)
        st.session_state[f"report-{route['id']}"] = (data, fname, mime)

    stored = st.session_state.get(f"report-{route['id']}")
    if stored:
        st.success(t["export_ready"])
        st.download_button(t["download"], data=stored[0], file_name=stored[1],
                           mime=stored[2], key=f"dl-{route['id']}")


# ============================================================
# 5. 主流程
# ============================================================
inject_css()

if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "page" not in st.session_state:
    st.session_state.page = "chat"
if "messages" not in st.session_state:
    st.session_state.messages = []

signature = data_signature()

try:
    index = load_bundle(signature)
except Exception as exc:  # C 内核或数据有问题时给可读的提示，而不是整页崩掉
    st.error("数据加载失败 / Failed to load data\n\n```\n" + str(exc) + "\n```")
    st.stop()

lang = st.session_state.lang
t = TEXT[lang]


@st.fragment(run_every="3s")
def auto_watch(sig: str) -> None:
    """每 3 秒嗅一次文件指纹，数据变了就整页刷新。"""
    if data_signature() != sig:
        st.rerun()


auto_refresh = sidebar(index, lang)
if auto_refresh:
    auto_watch(signature)

# ---- 顶部主视觉 ----
_en_suffix = '<span class="h1-en">RedTrace AI</span>' if lang == "zh" else ""
_tag_chips = "".join(
    f'<span class="hero-tag">{chip.strip()}</span>'
    for chip in t["tags"].split("·")
)
st.markdown(
    f'<div class="hero">'
    f'<span class="badge">{t["badge"]}</span>'
    f'<h1>🚩 {t["app_title"]} {_en_suffix}</h1>'
    f'<p>{t["subtitle"]}</p>'
    f'<div class="hero-tags">{_tag_chips}</div>'
    f'</div>',
    unsafe_allow_html=True,
)
st.markdown(stats_html(index, lang), unsafe_allow_html=True)

if st.session_state.get("_flash"):
    st.success(st.session_state.pop("_flash"))
if st.session_state.get("_sig") and st.session_state["_sig"] != signature:
    st.toast(t["data_changed"])
st.session_state["_sig"] = signature

# ---- 按页面渲染 ----
if st.session_state.page == "graph":
    render_graph_page(index, lang, t)
elif st.session_state.page == "study":
    render_study_page(index, lang, t)
else:
    render_chat_page(index, lang, t)

