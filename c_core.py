# -*- coding: utf-8 -*-
"""C 语言图内核的 Python 封装。

数据流：  kg.json ──生成──> nodes.txt / edges.txt ──C 读取──> 邻接表 ──> 查询邻居
                                                                  │
                                        Python 通过 ctypes 调用 ──┘

自动更新原理
------------
graph.c 里的图数据是 C 进程内的静态数组，同一个 DLL 只会被加载一次，
所以「数据变了但页面还是老结果」是这类项目最常见的坑。

这里的做法：每次按【数据内容签名】把 graph.dll 复制成一份新文件
（_runtime/graph_<签名>.dll）再加载。文件名不同 → Windows 会把它当成
新模块 → 全局变量从零开始 → load_graph() 读进来的是最新数据。
因此改完 kg.json 无需重新编译、无需重启服务，页面几秒内就会更新
（同一个进程内即可热加载，旧模块仍安全驻留内存）。

注意：同一个 DLL 路径在一个进程里只会加载一次，对已加载的模块重复调用
load_graph() 会把节点/边再追加一遍（graph.c 里 nodeCount 只增不减）。
所以这里把「路径 → 已加载的图」记在 _LOADED 里，数据没变就复用，
保证 load_graph() 对每个模块只执行一次。

约束（来自 graph.c 的静态数组，不可越界）
----------------------------------------
    MAX_NODES = 200      节点数上限
    MAX_EDGES = 600      边数上限
    id ≤ 31 字节 / name ≤ 63 字节 / relation ≤ 31 字节
    name、id、relation 中不能出现空格或制表符（C 侧用 sscanf("%s") 解析）
超限时这里会给出明确的中文报错，而不是让 C 侧静默越界。
"""
from __future__ import annotations

import ctypes
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager

# ---- 必须与 graph.c 保持一致 ----
MAX_NODES = 200
MAX_EDGES = 600
MAX_ID = 31
MAX_NAME = 63
MAX_REL = 31

BUFFER_SIZE = 16384          # 一跳邻居缓冲
PATH_BUFFER_SIZE = 32768     # BFS 路径缓冲
DLL_NAME = "graph.dll" if sys.platform == "win32" else "libgraph.so"
# 内核可以有多个版本：Windows 不允许覆盖正在被映射的 dll，
# 这时新内核就以 graph_v2.dll 落地，加载时取「最新的那一份」。
ALT_DLL_NAMES = ("graph_v2.dll", "graph_v3.dll")
SOURCE_NAME = "graph.c"
RUNTIME_DIR = "_runtime"


# ===================== 小工具 =====================
@contextmanager
def _cwd(path):
    """C 代码里用的是 fopen("nodes.txt") 相对路径，加载时必须切到项目目录。"""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _check_limits(kg: dict) -> None:
    nodes, edges = kg.get("nodes", []), kg.get("edges", [])
    if len(nodes) > MAX_NODES:
        raise RuntimeError(
            f"节点数量 {len(nodes)} 超过 C 侧上限 {MAX_NODES}。"
            f"请把 graph.c 中的 MAX_NODES 调大并重新编译，或精简 kg.json。"
        )
    if len(edges) > MAX_EDGES:
        raise RuntimeError(
            f"关系数量 {len(edges)} 超过 C 侧上限 {MAX_EDGES}。"
            f"请把 graph.c 中的 MAX_EDGES 调大并重新编译，或精简 kg.json。"
        )

    ids = set()
    for n in nodes:
        nid = str(n.get("id", ""))
        name = str(n.get("name", ""))
        if not nid or not name:
            raise RuntimeError(f"kg.json 里有节点缺少 id 或 name：{n}")
        if nid in ids:
            raise RuntimeError(f"kg.json 里 id 重复：{nid}")
        ids.add(nid)
        if _byte_len(nid) > MAX_ID:
            raise RuntimeError(f"id「{nid}」超过 {MAX_ID} 字节，请缩短（C 侧 char[{MAX_ID + 1}]）。")
        if _byte_len(name) > MAX_NAME:
            raise RuntimeError(f"名称「{name}」超过 {MAX_NAME} 字节，请缩短（C 侧 char[{MAX_NAME + 1}]）。")
        if " " in name or "\t" in name:
            raise RuntimeError(f"名称「{name}」不能包含空格或制表符（C 侧用 sscanf %s 解析）。")

    for e in edges:
        for key in ("from", "to", "relation"):
            val = str(e.get(key, ""))
            if not val or " " in val or "\t" in val:
                raise RuntimeError(f"关系 {e} 的 {key} 不能为空、不能含空格或制表符。")
        if e["from"] not in ids or e["to"] not in ids:
            raise RuntimeError(f"关系 {e} 引用了不存在的节点 id。")
        if _byte_len(str(e["relation"])) > MAX_REL:
            raise RuntimeError(
                f"关系类型「{e['relation']}」超过 {MAX_REL} 字节，请缩短（C 侧 char[{MAX_REL + 1}]）。"
            )


def _graph_text(kg: dict) -> tuple[str, str]:
    """把知识图谱转成 C 侧读取的两个 TSV 文件内容（顺序决定头插后的展示顺序）。"""
    nodes_text = "".join(
        f"{n['id']}\t{n['name']}\t{n.get('type', 'CONCEPT')}\n" for n in kg["nodes"]
    )
    edges_text = "".join(
        f"{e['from']}\t{e['to']}\t{e['relation']}\n" for e in kg["edges"]
    )
    return nodes_text, edges_text


# ===================== DLL 构建 / 实例化 =====================
def _find_compilers(root: str) -> list[str]:
    """找可用的 C 编译器：PATH 里的 gcc/clang，以及常见的 MinGW 安装位置。"""
    found = []
    for name in ("gcc", "clang"):
        path = shutil.which(name)
        if path:
            found.append(path)

    patterns = [
        os.path.join(root, "tools", "**", "bin", "gcc.exe"),
        os.path.join(root, "**", "w64devkit", "bin", "gcc.exe"),
        r"C:\mingw64\bin\gcc.exe",
        r"C:\msys64\mingw64\bin\gcc.exe",
        r"C:\TDM-GCC-64\bin\gcc.exe",
        r"C:\w64devkit\bin\gcc.exe",
        os.path.expanduser(r"~\scoop\apps\mingw\current\bin\gcc.exe"),
    ]
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            if path not in found:
                found.append(path)
    return found


def _kernel_path(root: str) -> str | None:
    """在项目根目录里挑出最新的内核 dll（graph.dll / graph_v2.dll / graph_v3.dll）。"""
    best, best_time = None, -1.0
    for name in (DLL_NAME, *(n for n in ALT_DLL_NAMES if sys.platform == "win32")):
        path = os.path.join(root, name)
        if os.path.exists(path):
            t = os.path.getmtime(path)
            if t > best_time:
                best, best_time = path, t
    return best


def _writable(path: str) -> bool:
    try:
        with open(path, "ab"):
            pass
        return True
    except OSError:
        return False


def _ensure_dll(root: str) -> str:
    """返回可用的内核 dll；源码比 dll 新且本机有编译器时才重新编译。"""
    src_path = os.path.join(root, SOURCE_NAME)
    current = _kernel_path(root)

    need_build = current is None
    if current and os.path.exists(src_path):
        need_build = os.path.getmtime(src_path) > os.path.getmtime(current)

    if need_build:
        compilers = _find_compilers(root)
        for target_name in (DLL_NAME, *(n for n in ALT_DLL_NAMES if sys.platform == "win32")):
            target = os.path.join(root, target_name)
            if os.path.exists(target) and not _writable(target):
                continue          # 被旧进程占用的 dll 跳过，换下一个文件名
            for compiler in compilers:
                try:
                    subprocess.run(
                        [compiler, "-std=c99", "-O2", "-shared", "-fPIC",
                         "-o", target_name, SOURCE_NAME],
                        cwd=root, check=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    return target
                except Exception:
                    continue
        if current:
            return current        # 没编译器 / 编译失败：用现有的内核
        raise RuntimeError(
            "没有找到 graph.dll，也没能调用 gcc/clang 编译 graph.c。\n"
            "解决方式三选一：\n"
            "  1) 安装 MinGW-w64（把 gcc 加进 PATH）后重新运行；\n"
            "  2) 把便携版 w64devkit 解压到项目下 tools/ 目录（自动识别）；\n"
            "  3) 直接把编译好的 graph.dll 放到项目目录里。"
        )
    return current


def _prepare_work(root: str, nodes_text: str, edges_text: str) -> str:
    """把 nodes.txt / edges.txt 写到可写目录：优先项目目录，只读部署退到临时目录。

    直接写目标文件而不是先探测目录——有些环境目录可新建文件、但已有的 txt 是只读的。
    """
    candidates = [root, os.path.join(tempfile.gettempdir(), "redtrace_work")]
    last = None
    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            with open(os.path.join(cand, "nodes.txt"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(nodes_text)
            with open(os.path.join(cand, "edges.txt"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(edges_text)
            return cand
        except OSError as exc:
            last = exc
            continue
    raise RuntimeError(f"没有可写的工作目录（{last}）")


def _instantiate_dll(root: str, signature: str, work: str | None = None) -> str:
    """按数据签名复制出一份唯一的 DLL 文件，保证全局状态是全新的。"""
    runtime = os.path.join(work or root, RUNTIME_DIR)
    os.makedirs(runtime, exist_ok=True)
    suffix = ".so" if DLL_NAME.endswith(".so") else ".dll"
    target = os.path.join(runtime, f"graph_{signature}{suffix}")
    if not os.path.exists(target):
        shutil.copy2(_ensure_dll(root), target)
        _prune_runtime(runtime, keep=8)
    return target


def _prune_runtime(runtime: str, keep: int = 8) -> None:
    """只保留最近的若干份副本（正在使用的会被 Windows 锁住，删不掉就跳过）。"""
    try:
        files = [
            os.path.join(runtime, f)
            for f in os.listdir(runtime)
            if f.endswith(".dll") or f.endswith(".so")
        ]
        files.sort(key=os.path.getmtime, reverse=True)
        for old in files[keep:]:
            try:
                os.remove(old)
            except OSError:
                pass
    except OSError:
        pass


# ===================== 对外接口 =====================
class GraphLib:
    """封装一个已加载好的 C 邻接表图。"""

    engine = "c"          # 页面据此显示「C 内核」还是「Python 兜底」

    def __init__(self, root: str, lib: ctypes.CDLL, signature: str):
        self.root = root
        self.lib = lib
        self.signature = signature
        self._local = threading.local()      # 每个线程复用自己的缓冲区

    def _buffer(self, kind: str, size: int) -> ctypes.Array:
        """复用缓冲区：避免每次查询都 create_string_buffer(32KB)。"""
        buf = getattr(self._local, kind, None)
        if buf is None or len(buf) < size:
            buf = ctypes.create_string_buffer(size)
            setattr(self._local, kind, buf)
        return buf

    def query_raw(self, node_id: str) -> tuple[int, str]:
        """C 函数原始输出：返回 (邻居数, "目标名|关系;目标名|关系;")。"""
        buf = self._buffer("neigh", BUFFER_SIZE)
        count = self.lib.query_neighbors(
            node_id.encode("utf-8"), buf, BUFFER_SIZE
        )
        return count, buf.value.decode("utf-8", errors="replace")

    def neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """解析成 [(目标名, 关系), ...]"""
        count, raw = self.query_raw(node_id)
        if count <= 0:
            return []
        out = []
        for item in raw.strip(";").split(";"):
            if "|" in item:
                name, rel = item.split("|", 1)
                out.append((name, rel))
        return out

    # ---------- C 语言 BFS 最短路径 ----------
    @property
    def api_version(self) -> int:
        try:
            self.lib.graph_api_version.restype = ctypes.c_int
            return int(self.lib.graph_api_version())
        except AttributeError:
            return 1          # 旧版 DLL 没有这个函数

    def find_path(self, from_id: str, to_id: str) -> tuple[int, list[tuple[str, str, str, bool]]]:
        """C 里的 BFS 最短路径（无向）。

        返回 (跳数, [(起点id, 关系, 终点id, 是否反向), ...])；
        跳数 0 表示同一实体，-1 表示不存在或没找到，-2 表示这个 DLL 没有 BFS。
        """
        if not hasattr(self.lib, "find_path"):
            return -2, []
        buf = self._buffer("path", PATH_BUFFER_SIZE)
        hops = self.lib.find_path(
            from_id.encode("utf-8"), to_id.encode("utf-8"), buf, PATH_BUFFER_SIZE
        )
        raw = buf.value.decode("utf-8", errors="replace")
        if hops <= 0:
            return int(hops), []

        parts = raw.split("|")
        steps = []
        # 格式：id0 | rel1 | id1 | rel2 | id2 ...
        for i in range(1, len(parts) - 1, 2):
            rel, nxt = parts[i], parts[i + 1]
            reversed_ = rel.startswith("~")
            steps.append((parts[i - 1], rel.lstrip("~"), nxt, reversed_))
        return int(hops), steps

    def node_count(self) -> int:
        try:
            self.lib.get_node_count.restype = ctypes.c_int
            return int(self.lib.get_node_count())
        except AttributeError:
            return -1

    def edge_count(self) -> int:
        try:
            self.lib.get_edge_count.restype = ctypes.c_int
            return int(self.lib.get_edge_count())
        except AttributeError:
            return -1


# 同一个 DLL 文件在一个进程里只会被加载一次（Windows 按路径缓存模块句柄），
# 因此再次对它调用 load_graph() 会把节点/边重复追加进静态数组。
# 这里记住「文件路径 -> 已加载的图」，同一份数据直接复用，绝不重复 load_graph()。
#
# 注册表挂在 sys 上而不是模块里：Streamlit 只重跑主脚本、不重新 import 模块，
# 升级 c_core.py 后需要 importlib.reload()，而 reload 会清空模块级变量。
# 放在 sys 上，reload 之后仍然记得「这个 DLL 已经加载过」，不会重复 load_graph()。
def _registry() -> dict:
    reg = getattr(sys, "_c_core_loaded", None)
    if reg is None:
        reg = {}
        setattr(sys, "_c_core_loaded", reg)
    return reg


_LOADED: dict[str, "GraphLib"] = _registry()
_LOAD_LOCK = threading.Lock()
CORE_API = 3          # 3 = 带 C 语言 BFS 最短路径（find_path）


def _python_fallback(kg: dict, reason: str = ""):
    """编译不了 C（比如公网 Linux 容器没有 gcc）时的兜底内核，接口与 GraphLib 相同。"""
    from py_graph import PyGraph

    key = "python:" + hashlib.sha1(
        json.dumps(kg, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    with _LOAD_LOCK:
        cached = _LOADED.get(key)
        if cached is not None:
            return cached
        nodes = {n["id"]: n for n in kg["nodes"]}
        graph = PyGraph(nodes, kg["edges"])
        _LOADED[key] = graph
    if reason:
        print(f"[c_core] 使用纯 Python 兜底内核（{reason}）")
    return graph


def build_and_load(root: str | None = None):
    """读 kg.json → 生成 nodes.txt / edges.txt → 加载 C 邻接表。

    每次数据变化都会返回一个全新的图实例，可直接热替换，不必重启；
    数据没变时复用同一个实例（避免重复 load_graph 造成节点重复）。
    没有可用的 C 内核时（缺 gcc / 平台不匹配），自动退化为纯 Python 实现，
    页面上会显示当前用的是哪一个引擎。
    """
    root = os.path.abspath(root or os.path.dirname(os.path.abspath(__file__)))
    kg_path = os.path.join(root, "kg.json")
    with open(kg_path, encoding="utf-8") as f:
        kg = json.load(f)

    _check_limits(kg)
    nodes_text, edges_text = _graph_text(kg)

    work = _prepare_work(root, nodes_text, edges_text)   # 只读部署时自动退到临时目录

    # 允许强制用 Python（调试 / 平台编译不可靠时）
    if os.environ.get("RED_AGENT_ENGINE", "").strip().lower() in ("python", "py"):
        return _python_fallback(kg, "RED_AGENT_ENGINE=python")

    try:
        dll_path = _ensure_dll(root)
    except Exception as exc:
        return _python_fallback(kg, f"没有可用的 C 内核：{type(exc).__name__}")

    signature = hashlib.sha1(
        (nodes_text + "\x00" + edges_text + "\x00" +
         f"{os.path.getsize(dll_path)}:{os.path.getmtime(dll_path)}").encode("utf-8")
    ).hexdigest()[:12]

    try:
        target = _instantiate_dll(root, signature, work)
    except Exception as exc:
        return _python_fallback(kg, f"DLL 准备失败：{type(exc).__name__}")

    with _LOAD_LOCK:
        cached = _LOADED.get(target)
        if cached is not None:
            return cached

        try:
            lib = ctypes.CDLL(target)
            lib.query_neighbors.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            lib.query_neighbors.restype = ctypes.c_int
            lib.load_graph.argtypes = []
            lib.load_graph.restype = None
            if hasattr(lib, "find_path"):          # 新版内核才有 BFS
                lib.find_path.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                          ctypes.c_char_p, ctypes.c_int]
                lib.find_path.restype = ctypes.c_int

            with _cwd(work):        # C 侧用相对路径读 nodes.txt / edges.txt
                lib.load_graph()
        except Exception as exc:
            return _python_fallback(kg, f"加载 {DLL_NAME} 失败：{type(exc).__name__}")

        graph = GraphLib(work, lib, signature)
        _LOADED[target] = graph
        return graph


def query_entity(lib: GraphLib, entity_id: str) -> tuple[int, str]:
    """兼容旧接口：返回 (邻居数, 原始字符串)。"""
    return lib.query_raw(entity_id)
