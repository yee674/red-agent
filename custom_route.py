# -*- coding: utf-8 -*-
"""「AI 定制路线」：按兴趣主题 + 时长，用图谱关系与 C 语言的 BFS 跳数自动排一条路线。

算法（三步，全部可解释）：
1. 匹配度：点位实体类型 == 兴趣主题（人物/旧址/事件/精神理念）记 1 分；
2. 距离：用 C 的 find_path 算「起点 → 点位」的最短跳数，越近越优先；
3. 排序：从起点出发做贪心最近邻（每次选跳数最小的下一个点位），得到一条走得顺的路线。
"""
from __future__ import annotations

HOURS_TO_COUNT = {2: 3, 3: 4, 4: 6}


def _hops(lib, a: str, b: str) -> int:
    if lib is None:
        return 99
    try:
        n, _ = lib.find_path(a, b)
    except Exception:
        return 99
    return n if n >= 0 else 99


def generate(index: dict, pois: list[dict], kind: str, hours: int,
             start_entity: str) -> dict:
    """返回 {poi 列表(已排序), 每个点位的匹配度与跳数, 说明文字数据}"""
    lib = index.get("lib")
    nodes = index["nodes"]
    want = HOURS_TO_COUNT.get(hours, 4)

    scored = []
    for poi in pois:
        node = nodes.get(poi["entity"], {})
        match = 1.5 if (node.get("type") or "").upper() == kind else 0.0
        dist = _hops(lib, start_entity, poi["entity"])
        scored.append({"poi": poi, "match": match, "dist": dist,
                       "score": match * 2 + (10 - min(dist, 10))})

    # 起点优先入选
    start_poi = next((s for s in scored if s["poi"]["entity"] == start_entity), None)
    picked = sorted(scored, key=lambda s: (-s["score"], s["dist"]))
    if start_poi:
        picked = [start_poi] + [s for s in picked if s is not start_poi]
    picked = picked[:max(want, 2 if start_poi else want)]

    # 贪婪最近邻排序：从起点开始，每次挑跳数最小的下一个点
    ordered, cur = [], start_entity
    rest = [s for s in picked]
    if start_poi:
        ordered.append({"poi": start_poi["poi"], "match": start_poi["match"],
                        "dist": 0, "score": start_poi["score"]})
        rest = [s for s in rest if s is not start_poi]
    while rest:
        rest.sort(key=lambda s: (_hops(lib, cur, s["poi"]["entity"]), -s["score"]))
        nxt = rest.pop(0)
        ordered.append({"poi": nxt["poi"], "match": nxt["match"],
                        "dist": _hops(lib, cur, nxt["poi"]["entity"]),
                        "score": nxt["score"]})
        cur = nxt["poi"]["entity"]

    return {"items": ordered, "hours": hours, "kind": kind}


def make_tasks(items: list[dict], lang: str) -> list[str]:
    """按点位自动生成 3 条可执行任务（中/英）。"""
    names = [it["poi"]["name"] for it in items]
    if not names:
        return []
    first = names[0]
    last = names[-1]
    mid = names[len(names) // 2]
    if lang == "en":
        return [
            f"Start at {first}: note one fact you did not know before.",
            f"At {mid}: find an object, inscription or photo that matches the theme.",
            f"At {last}: write down how it connects to the person or idea you care about.",
        ]
    return [
        f"在「{first}」记下一条你原本不知道的事实。",
        f"在「{mid}」找一个与主题呼应的实物、题刻或照片。",
        f"在「{last}」写下它和你关注的人物/理念之间的关系。",
    ]
