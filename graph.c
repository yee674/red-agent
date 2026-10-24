#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

/*
 * 湖南第一师范红色文化知识图谱 —— C 语言图内核
 *
 * 数据结构：
 *   graph[]        顶点表（id / name / type）
 *   firstEdge      有向边链表（头插法），供 query_neighbors 使用
 *   firstU         无向边链表（正反各一条，reversed 标记方向），供 BFS 最短路径使用
 *
 * 对外接口（Python 通过 ctypes 调用）：
 *   graph_api_version()                     版本号，便于前端判断内核是否为新版
 *   load_graph()                            读取 nodes.txt / edges.txt 建图
 *   query_neighbors(id, buf, max_len)       一跳邻居（有向），返回条数
 *   find_path(from, to, buf, max_len)       BFS 最短路径（无向），返回跳数
 *   get_node_count() / get_edge_count()
 *
 * 路径输出格式： a|rel|b|~rel|c
 *   "~rel" 表示这条边在原始数据里方向相反（b -> a），前端据此画箭头。
 */

#define MAX_NODES 200
#define MAX_EDGES 600
#define MAX_ID 31
#define MAX_NAME 63
#define MAX_REL 31

typedef struct EdgeNode {
    int to;                     /* 目标节点下标（有向：本节点 -> to） */
    char relation[MAX_REL + 1];
    struct EdgeNode* next;
} EdgeNode;

typedef struct UEdge {
    int to;                     /* 相邻节点下标（无向：两个方向都能走） */
    char relation[MAX_REL + 1];
    int reversed;               /* 1 = 原始边是 to -> 本节点 */
    struct UEdge* next;
} UEdge;

typedef struct {
    char id[MAX_ID + 1];
    char name[MAX_NAME + 1];
    char type[32];
    EdgeNode* firstEdge;        /* 有向邻接表 */
    UEdge* firstU;              /* 无向邻接表 */
} VertexNode;

VertexNode graph[MAX_NODES];
int nodeCount = 0;
int edgeCount = 0;

/* BFS 用的静态工作区，避免每次查询重新 malloc */
static int bfsQueue[MAX_NODES];
static int bfsVisited[MAX_NODES];
static int bfsPrev[MAX_NODES];
static int bfsPrevRev[MAX_NODES];
static char bfsPrevRel[MAX_NODES][MAX_REL + 1];

int graph_api_version(void) { return 2; }
int get_node_count(void) { return nodeCount; }
int get_edge_count(void) { return edgeCount; }

/* 根据 id 查找节点下标 */
int find_node_index(const char* id) {
    int i;
    if (!id) return -1;
    for (i = 0; i < nodeCount; i++) {
        if (strcmp(graph[i].id, id) == 0) return i;
    }
    return -1;
}

static void add_directed(int u, int v, const char* rel) {
    EdgeNode* e = (EdgeNode*)malloc(sizeof(EdgeNode));
    if (!e) return;
    e->to = v;
    strncpy(e->relation, rel, MAX_REL);
    e->relation[MAX_REL] = '\0';
    e->next = graph[u].firstEdge;      /* 头插法 */
    graph[u].firstEdge = e;
}

static void add_undirected(int u, int v, const char* rel, int reversed) {
    UEdge* e = (UEdge*)malloc(sizeof(UEdge));
    if (!e) return;
    e->to = v;
    strncpy(e->relation, rel, MAX_REL);
    e->relation[MAX_REL] = '\0';
    e->reversed = reversed;
    e->next = graph[u].firstU;
    graph[u].firstU = e;
}

/* 初始化图，读取 txt 文件 */
void load_graph(void) {
    FILE* f_nodes;
    FILE* f_edges;
    char line[512];

    nodeCount = 0;
    edgeCount = 0;

    f_nodes = fopen("nodes.txt", "r");
    f_edges = fopen("edges.txt", "r");
    if (!f_nodes || !f_edges) {
        if (f_nodes) fclose(f_nodes);
        if (f_edges) fclose(f_edges);
        return;
    }

    /* 1. 读节点 */
    while (nodeCount < MAX_NODES && fgets(line, sizeof(line), f_nodes)) {
        char id[MAX_ID + 1] = {0}, name[MAX_NAME + 1] = {0}, type[32] = {0};
        if (sscanf(line, "%31s\t%63s\t%31s", id, name, type) < 2) continue;
        strcpy(graph[nodeCount].id, id);
        strcpy(graph[nodeCount].name, name);
        strcpy(graph[nodeCount].type, type);
        graph[nodeCount].firstEdge = NULL;
        graph[nodeCount].firstU = NULL;
        nodeCount++;
    }
    fclose(f_nodes);

    /* 2. 读边：同时建「有向表」和「无向表」 */
    while (edgeCount < MAX_EDGES && fgets(line, sizeof(line), f_edges)) {
        char from[MAX_ID + 1] = {0}, to[MAX_ID + 1] = {0}, rel[MAX_REL + 1] = {0};
        int u, v;
        if (sscanf(line, "%31s\t%31s\t%31s", from, to, rel) < 3) continue;
        u = find_node_index(from);
        v = find_node_index(to);
        if (u == -1 || v == -1) continue;

        add_directed(u, v, rel);            /* 本节点 -> 目标 */
        add_undirected(u, v, rel, 0);       /* 无向：u 一侧 */
        add_undirected(v, u, rel, 1);       /* 无向：v 一侧，方向相反 */
        edgeCount++;
    }
    fclose(f_edges);
}

/*
 * 一跳邻居（有向），供 Python 渲染「直接关联」。
 * 输出 "目标名|关系;目标名|关系;"
 */
int query_neighbors(const char* id, char* buf, int max_len) {
    int u = find_node_index(id);
    int count = 0;
    int used = 0;
    EdgeNode* p;

    if (!buf || max_len <= 0) return -1;
    buf[0] = '\0';

    if (u == -1) {
        strncpy(buf, "NOT_FOUND", max_len - 1);
        buf[max_len - 1] = '\0';
        return -1;
    }

    for (p = graph[u].firstEdge; p != NULL; p = p->next) {
        int n = snprintf(buf + used, max_len - used, "%s|%s;",
                         graph[p->to].name, p->relation);
        if (n < 0 || used + n >= max_len) break;   /* 缓冲不够就停，绝不越界 */
        used += n;
        count++;
    }
    return count;
}

/*
 * 从 s 出发做一次 BFS，找到 t 就返回 1 并填好 bfsPrev/bfsPrevRel。
 * mode = 0：只沿有向边走（关系方向自然）  mode = 1：无向（可走反向边）
 */
static int bfs_search(int s, int t, int mode) {
    int head = 0, tail = 0, i;

    for (i = 0; i < nodeCount; i++) {
        bfsVisited[i] = 0;
        bfsPrev[i] = -1;
        bfsPrevRev[i] = 0;
        bfsPrevRel[i][0] = '\0';
    }

    bfsQueue[tail++] = s;
    bfsVisited[s] = 1;

    while (head < tail) {
        int u = bfsQueue[head++];
        UEdge* p;

        if (u == t) return 1;

        for (p = graph[u].firstU; p != NULL; p = p->next) {
            int v = p->to;
            if (mode == 0 && p->reversed) continue;   /* 只走正向边 */
            if (bfsVisited[v]) continue;
            bfsVisited[v] = 1;
            bfsPrev[v] = u;
            bfsPrevRev[v] = p->reversed;
            strncpy(bfsPrevRel[v], p->relation, MAX_REL);
            bfsPrevRel[v][MAX_REL] = '\0';
            bfsQueue[tail++] = v;
            if (v == t) return 1;
        }
    }
    return bfsVisited[t] ? 1 : 0;
}

/*
 * BFS 最短路径，返回跳数；0 表示同一个节点，-1 表示没找到。
 * 先试「只走正向边」——这样显示出来的是「A —关系→ B」的自然方向；
 * 找不到再允许走反向边（反向边在输出里标 ~）。
 */
int find_path(const char* from_id, const char* to_id, char* buf, int max_len) {
    int s, t, hops = 0, used = 0, cur, i;
    int pathNodes[MAX_NODES];
    int pathRevs[MAX_NODES];
    char pathRels[MAX_NODES][MAX_REL + 1];

    if (!buf || max_len <= 0) return -1;
    buf[0] = '\0';

    s = find_node_index(from_id);
    t = find_node_index(to_id);
    if (s == -1 || t == -1) {
        strncpy(buf, "NOT_FOUND", max_len - 1);
        buf[max_len - 1] = '\0';
        return -1;
    }
    if (s == t) {
        snprintf(buf, max_len, "%s", graph[s].id);
        return 0;
    }

    if (!bfs_search(s, t, 0) && !bfs_search(s, t, 1)) {
        strncpy(buf, "NO_PATH", max_len - 1);
        buf[max_len - 1] = '\0';
        return -1;
    }

    /* 回溯：t -> s，倒序存进临时数组 */
    cur = t;
    while (cur != s && hops < MAX_NODES) {
        pathNodes[hops] = cur;
        pathRevs[hops] = bfsPrevRev[cur];
        strncpy(pathRels[hops], bfsPrevRel[cur], MAX_REL);
        pathRels[hops][MAX_REL] = '\0';
        hops++;
        cur = bfsPrev[cur];
        if (cur == -1) {
            buf[0] = '\0';
            return -1;
        }
    }

    /* 正向拼接：起点 */
    used = snprintf(buf, max_len, "%s", graph[s].id);
    if (used < 0 || used >= max_len) { buf[0] = '\0'; return -1; }

    for (i = hops - 1; i >= 0; i--) {
        int n = snprintf(buf + used, max_len - used, "|%s%s|%s",
                         pathRevs[i] ? "~" : "", pathRels[i],
                         graph[pathNodes[i]].id);
        if (n < 0 || used + n >= max_len) break;
        used += n;
    }
    return hops;
}
