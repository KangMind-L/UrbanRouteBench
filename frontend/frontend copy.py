import streamlit as st
import requests
import uuid
from datetime import datetime
import json
import re
import pandas as pd
import pydeck as pdk
import folium
from streamlit_folium import st_folium

# -----------------------------
# 后端接口地址（修改为你的 FastAPI 服务地址）
# -----------------------------
API_ENDPOINT = "http://localhost:8000/plan_route"

# -----------------------------
# 页面基础设置
# -----------------------------
st.set_page_config(page_title="🚆 智能出行助手", layout="wide")

# -----------------------------
# 初始化 Session 状态
# -----------------------------
if "sessions" not in st.session_state:
    st.session_state.sessions = {}  # {session_name: {"id":..., "messages":[...]}}

if "current_session" not in st.session_state:
    new_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    st.session_state.current_session = "会话 1"
    st.session_state.sessions["会话 1"] = {
        "id": new_id,
        "messages": [
            {"role": "assistant", "content": "你好👋，我是你的出行助手，请告诉我出行需求吧～"}
        ]
    }

# 存储地图显示状态
if "show_map" not in st.session_state:
    st.session_state.show_map = False

if "current_route_points" not in st.session_state:
    st.session_state.current_route_points = []

# -----------------------------
# 侧边栏：会话管理
# -----------------------------
with st.sidebar:
    st.header("💬 会话列表")

    if st.button("🆕 新建会话"):
        session_count = len(st.session_state.sessions) + 1
        session_name = f"会话 {session_count}"
        session_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        st.session_state.sessions[session_name] = {
            "id": session_id,
            "messages": [
                {"role": "assistant", "content": "你好👋，我是你的出行助手，请告诉我出行需求吧～"}
            ]
        }
        st.session_state.current_session = session_name
        st.session_state.show_map = False  # 新建会话时隐藏地图
        st.rerun()

    session_names = list(st.session_state.sessions.keys())
    selected_session = st.radio("选择会话", session_names, index=session_names.index(st.session_state.current_session))

    st.session_state.current_session = selected_session

    st.subheader("⚙️ 模型选择")
    model_name = st.selectbox(
        "选择模型",
        ["deepseek-ai/DeepSeek-V3.2","gpt-5", "deepseek-chat","Qwen/Qwen3-VL-235B-A22B-Instruct","ZhipuAI/GLM-4.5","kimi-for-coding"],
        index=0
    )
    st.session_state.model_name = model_name

# -----------------------------
# 主界面部分：标题 + 欢迎提示 + 聊天内容
# -----------------------------
current_chat = st.session_state.sessions[st.session_state.current_session]

st.title("🚆 智能出行助手")

st.markdown("""
欢迎使用 **智能出行助手**！  
你可以直接和我聊天，例如：  
>老人晚上要去万象新天2期，得在晚上9点53分前赶到。从文芳阁这边坐公共交通过去，麻烦选条最近的路，少走点儿路，全程车费别超过7块钱。
""")

st.divider()

# -----------------------------
# 显示消息：用户靠右，助手靠左
# -----------------------------
for msg in current_chat["messages"]:
    if msg["role"] == "user":
        st.markdown(
            f"""
            <div style="display: flex; justify-content: flex-end; margin: 6px 0;">
                <div style="background-color: #DCF8C6; color: black; padding: 10px 14px; border-radius: 14px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                    {msg["content"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: flex-start; margin: 6px 0;">
                <div style="background-color: #F1F0F0; color: black; padding: 10px 14px; border-radius: 14px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                    {msg["content"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# -----------------------------
# 显示地图（如果有路线数据）
# -----------------------------
if st.session_state.show_map and st.session_state.current_route_points:
    st.markdown("### 🗺 路线地图")
    
    route_points = st.session_state.current_route_points
    
    avg_lat = sum(p["lat"] for p in route_points) / len(route_points)
    avg_lon = sum(p["lon"] for p in route_points) / len(route_points)

    map_obj = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)

    coords = []
    for point in route_points:
        coords.append((point["lat"], point["lon"]))
        folium.Marker(
            location=[point["lat"], point["lon"]],
            popup=point["name"],
            tooltip=point["name"],
            icon=folium.Icon(color="blue")
        ).add_to(map_obj)

    folium.PolyLine(locations=coords, weight=5, opacity=0.7).add_to(map_obj)

    st_folium(map_obj, width=700, height=500)

# -----------------------------
# 聊天输入框
# -----------------------------
if prompt := st.chat_input("请输入你的出行需求..."):
    # 显示用户泡泡
    current_chat["messages"].append({"role": "user", "content": prompt})
    st.markdown(
        f"""
        <div style="display: flex; justify-content: flex-end; margin: 6px 0;">
            <div style="background-color: #DCF8C6; padding: 10px 14px; border-radius: 14px; max-width: 70%; text-align: left; box-shadow:0 1px 2px rgba(0,0,0,0.1);">
                {prompt}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 回复占位符
    reply_placeholder = st.empty()
    
    stream_url = API_ENDPOINT.replace("/plan_route", "/plan_route_stream")
    reply = ""
    
    with st.spinner("正在生成回复..."):
        try:
            with requests.post(
                stream_url,
                json={
                    "session_id": current_chat["id"],
                    "query": prompt,
                    "model_name": st.session_state.model_name,
                    "reset": False
                },
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    reply_placeholder.markdown(f"请求出错：{resp.text}")
                else:
                    for chunk in resp.iter_content(chunk_size=1, decode_unicode=True):
                        if chunk:
                            reply += chunk
                            reply_placeholder.markdown(
                                f"""
                                <div style="display:flex;justify-content:flex-start;margin:6px 0;">
                                    <div style="background-color:#F1F0F0;padding:10px 14px;border-radius:14px;max-width:70%;text-align:left;box-shadow:0 1px 2px rgba(0,0,0,0.1);">
                                        {reply}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
        except Exception as e:
            reply_placeholder.markdown(f"请求出错：{e}")

    # 保存助手回复
    current_chat["messages"].append({"role": "assistant", "content": reply})
    
    # 设置地图显示状态和路线数据
    st.session_state.show_map = True
    # 这里可以根据实际的后端返回数据来动态生成路线点
    # 目前使用示例数据
    st.session_state.current_route_points = [
        {"name": "起点", "lat": 22.54055, "lon": 113.94412},
        {"name": "途经点1", "lat": 22.52760, "lon": 113.95195},
        {"name": "途经点2", "lat": 22.51891, "lon": 113.94150},
        {"name": "终点", "lat": 22.53332, "lon": 113.93691},
    ]
    
    # 强制刷新页面以显示地图
    st.rerun()

