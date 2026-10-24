#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_NODES 100
#define MAX_EDGES 200

typedef struct EdgeNode {
    int to;                     // 目标节点下标
    char relation[32];          // 关系类型
    struct EdgeNode* next;
} EdgeNode;

typedef struct {
    char id[32];
    char name[64];
    char type[32];
    EdgeNode* firstEdge;
} VertexNode;

VertexNode graph[MAX_NODES];
int nodeCount = 0;

// 根据 id 查找节点下标
int find_node_index(const char* id) {
    for (int i = 0; i < nodeCount; i++) {
        if (strcmp(graph[i].id, id) == 0) return i;
    }
    return -1;
}

// 初始化图，读取 txt 文件
void load_graph() {
    FILE* f_nodes = fopen("nodes.txt", "r");
    FILE* f_edges = fopen("edges.txt", "r");
    if (!f_nodes || !f_edges) return;

    char line[256];
    // 1. 读节点
    while (fgets(line, sizeof(line), f_nodes)) {
        sscanf(line, "%s\t%s\t%s", graph[nodeCount].id, graph[nodeCount].name, graph[nodeCount].type);
        graph[nodeCount].firstEdge = NULL;
        nodeCount++;
    }
    fclose(f_nodes);

    // 2. 读边（建立邻接表）
    while (fgets(line, sizeof(line), f_edges)) {
        char from[32], to[32], rel[32];
        sscanf(line, "%s\t%s\t%s", from, to, rel);

        int u = find_node_index(from);
        int v = find_node_index(to);

        if (u != -1 && v != -1) {
            EdgeNode* edge = (EdgeNode*)malloc(sizeof(EdgeNode));
            edge->to = v;
            strcpy(edge->relation, rel);
            // 头插法
            edge->next = graph[u].firstEdge;
            graph[u].firstEdge = edge;
        }
    }
    fclose(f_edges);
}

// 供 Python 调用的接口：查询邻居
// 输入：id，输出缓冲区 buf，缓冲区最大长度 max_len
// 返回：找到的邻居数量，-1 表示没找到该节点
int query_neighbors(const char* id, char* buf, int max_len) {
    int u = find_node_index(id);
    if (u == -1) {
        sprintf(buf, "NOT_FOUND");
        return -1;
    }

    buf[0] = '\0'; // 清空缓冲区
    int count = 0;
    EdgeNode* p = graph[u].firstEdge;

    while (p != NULL) {
        // 拼接格式： 目标名字|关系;目标名字|关系;
        strcat(buf, graph[p->to].name);
        strcat(buf, "|");
        strcat(buf, p->relation);
        strcat(buf, ";");

        count++;
        p = p->next;
    }
    return count;
}