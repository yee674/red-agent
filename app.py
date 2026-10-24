import streamlit as st
import ctypes
import os
import json
import subprocess
import sys

# ================= 1. 自动检测环境并编译 C 语言核心 =================
lib_name = "graph.dll" if sys.platform == "win32" else "libgraph.so"

if not os.path.exists(lib_name):
    try:
        subprocess.run(["gcc", "-std=c99", "-shared", "-fPIC", "-o", lib_name, "graph.c"], check=True)
    except Exception as e:
        st.error(f"C代码编译失败: {e}")


@st.cache_resource
def load_c_core():
    lib = ctypes.CDLL(os.path.abspath(lib_name))
    lib.query_neighbors.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    lib.query_neighbors.restype = ctypes.c_int
    lib.load_graph()
    return lib


@st.cache_data
def load_kg_data():
    with open("kg.json", encoding="utf-8") as f:
        kg_data = json.load(f)
    name_to_id = {n["name"]: n["id"] for n in kg_data["nodes"]}
    return kg_data, name_to_id


lib = load_c_core()
kg, name_to_id = load_kg_data()

# ================= 2. 多语言字典配置 =================
TEXT = {
    "zh": {
        "title": "🚩 一师红色文化智能研学",
        "subtitle": "请直接输入人物或地点名称（例如：毛泽东、杨昌济、第八班教室）",
        "chat_placeholder": "输入您的问题…",
        "not_found": "未在知识图谱中找到该实体。",
        "found": "找到以下关联：",
        "lang_btn": "Switch to English"
    },
    "en": {
        "title": "🚩 HNFS Red Culture Intelligent Study",
        "subtitle": "Please enter a person or place name (e.g. 毛泽东, 杨昌济)",
        "chat_placeholder": "Type your question…",
        "not_found": "Entity not found in the knowledge graph.",
        "found": "Found the following relations:",
        "lang_btn": "切换至中文"
    }
}

# 关系类型翻译字典
REL_ZH = {
    "FOUNDED": "创办",
    "CLASSMATE_OF": "同学",
    "TEACHER_OF": "老师",
    "STUDIED_AT": "在此求学",
    "PARTICIPATED_IN": "参与",
    "ADVOCATED": "倡导",
    "WROTE": "撰写",
    "LOCATED_IN": "位于",
    "MEMBER_OF": "成员",
    "PREDECESSOR_OF": "前身",
    "RELATED_TO": "相关"
}

if "lang" not in st.session_state:
    st.session_state.lang = "zh"
t = TEXT[st.session_state.lang]

# ================= 3. 侧边栏 =================
with st.sidebar:
    st.header("⚙️ Settings / 设置")
    if st.button(t["lang_btn"]):
        st.session_state.lang = "en" if st.session_state.lang == "zh" else "zh"
        st.rerun()

    st.divider()
    st.write("**Core Algorithm / 核心算法**")
    st.info("C Language Adjacency List + BFS\n(C 语言邻接表图遍历)")
    st.caption("Results are calculated by C core, not LLM. / 结果由 C 内核计算，非大模型生成。")

# ================= 4. 主界面与聊天交互 =================
st.title(t["title"])
st.caption(t["subtitle"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "image" in msg:
            st.image(msg["image"], width=300)

if prompt := st.chat_input(t["chat_placeholder"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        found_entity = None
        for name in name_to_id.keys():
            if name in prompt:
                found_entity = name
                break

        if found_entity:
            entity_id = name_to_id[found_entity]
            buf = ctypes.create_string_buffer(4096)
            count = lib.query_neighbors(entity_id.encode("utf-8"), buf, 4096)

            if count > 0:
                result_str = buf.value.decode("utf-8")
                relations = result_str.strip(";").split(";")

                reply = f"关于 **{found_entity}**，{t['found']}\n\n"
                for rel in relations:
                    if rel:
                        target, rel_type = rel.split("|")
                        # 根据语言切换关系类型名称
                        display_type = REL_ZH.get(rel_type, rel_type) if st.session_state.lang == "zh" else rel_type
                        reply += f"- {target} `{display_type}`\n"

                st.markdown(reply)

                # 读取本地图片展示
                img_filename = "placeholder.png"
                for n in kg["nodes"]:
                    if n["id"] == entity_id:
                        img_filename = n.get("image", "placeholder.png")
                        break

                img_path = os.path.join("assets", img_filename)
                if os.path.exists(img_path):
                    st.image(img_path, caption=found_entity, width=300)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": reply,
                        "image": img_path
                    })
                else:
                    st.caption("暂无图片 / No image available")
                    st.session_state.messages.append({"role": "assistant", "content": reply})

            else:
                st.warning(t["not_found"])
                st.session_state.messages.append({"role": "assistant", "content": t["not_found"]})
        else:
            reply = t["not_found"] + "\n请检查名称是否准确（如：毛泽东、蔡和森、水井、第八班教室）。"
            st.warning(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})