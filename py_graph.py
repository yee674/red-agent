# -*- coding: utf-8 -*-
"""纯 Python 兜底内核：接口与 c_core.GraphLib 完全一致。

为什么需要它：把项目部署到公网（Linux 容器）时，编译不了 graph.c 的平台
（没有 gcc、或架构不匹配）也能照常运行。页面会标注当前用的是哪一个内核。
"""
from __future__ import annotations

from collections import deque

MAX_REL = 31


class PyGraph:
    """与 GraphLib 同名的接口，内部用 dict + deque 实现同样的语义。"""

    engine = "python"
    api_version = 0          # 0 表示没有 C 内核

    def __init__(self, nodes: dict, edges: list[dict]):
        self.nodes = nodes
        self.edges = edges
        self._out: dict[str, list[tuple[str, str]]] = {nid: [] for nid in nodes}
        self._und: dict[str, list[tuple[str, str, bool]]] = {nid: [] for nid in nodes}
        for e in edges:
            u, v, rel = e["from"], e["to"], e["relation"]
            if u not in nodes or v not in nodes:
                continue
            self._out[u].append((v, rel))
            self._und[u].append((v, rel, False))
            self._und[v].append((u, rel, True))
        self.signature = "python"

    # ---------- 与 C 版一致的方法 ----------
    def query_raw(self, node_id: str) -> tuple[int, str]:
        """返回 (邻居数, "目标名|关系;目标名|关系;")（顺序与 C 的头插法一致：倒序）。"""
        if node_id not in self.nodes:
            return -1, "NOT_FOUND"
        items = []
        for target, rel in reversed(self._out.get(node_id, [])):
            items.append(f"{self.nodes[target]['name']}|{rel};")
        return len(items), "".join(items)

    def neighbors(self, node_id: str) -> list[tuple[str, str]]:
        count, raw = self.query_raw(node_id)
        if count <= 0:
            return []
        out = []
        for item in raw.strip(";").split(";"):
            if "|" in item:
                name, rel = item.split("|", 1)
                out.append((name, rel))
        return out

    def _bfs(self, s: str, t: str, forward_only: bool):
        """返回 [(节点id, 关系, 下一跳id, 是否反向)]，找不到返回 None。"""
        if s == t:
            return []
        prev: dict[str, tuple[str, str, bool]] = {}
        seen = {s}
        q = deque([s])
        while q:
            u = q.popleft()
            for v, rel, reversed_ in self._und.get(u, []):
                if forward_only and reversed_:
                    continue
                if v in seen:
                    continue
                seen.add(v)
                prev[v] = (u, rel, reversed_)
                if v == t:
                    path = []
                    cur = t
                    while cur != s:
                        p, r, rev = prev[cur]
                        path.append((p, r, cur, rev))
                        cur = p
                    return list(reversed(path))
                q.append(v)
        return None

    def find_path(self, from_id: str, to_id: str):
        """与 C 的 find_path 同义：先只走正向边，找不到再允许反向边。"""
        if from_id not in self.nodes or to_id not in self.nodes:
            return -1, []
        if from_id == to_id:
            return 0, []
        path = self._bfs(from_id, to_id, True)
        if path is None:
            path = self._bfs(from_id, to_id, False)
        if path is None:
            return -1, []
        return len(path), path

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def raw_call(self, *args, **kwargs) -> str:
        return "(python fallback graph)"
