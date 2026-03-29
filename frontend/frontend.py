
import streamlit as st
import requests
import uuid
from datetime import datetime
import json


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
        st.rerun()

    session_names = list(st.session_state.sessions.keys())
    selected_session = st.radio("选择会话", session_names, index=session_names.index(st.session_state.current_session))



    st.session_state.current_session = selected_session

st.subheader("⚙️ 模型选择")
model_name = st.selectbox(
        "选择模型",
        ["deepseek-ai/DeepSeek-V3.2","gpt-5",  "deepseek-chat","Qwen/Qwen3-VL-235B-A22B-Instruct","ZhipuAI/GLM-4.5","kimi-for-coding"],
        index=0
    )

    # 保存到 session_state（后端需要时可以用）
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
# 聊天输入框
# -----------------------------
if prompt := st.chat_input("请输入你的出行需求..."):
    current_chat["messages"].append({"role": "user", "content": prompt})
    st.markdown(
        f"""
        <div style="display: flex; justify-content: flex-end; margin: 6px 0;">
            <div style="background-color: #DCF8C6; padding: 10px 14px; border-radius: 14px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                {prompt}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ##请求后端
    # with st.spinner("正在思考，请稍候..."):
    #     try:
    #         payload = {
    #             "session_id": current_chat["id"],
    #             "query": prompt
    #         }
    #         res = requests.post(API_ENDPOINT, json=payload)
    #         res.raise_for_status()
    #         data = res.json()
    #         reply = data.get("reply", "（请重新输入）")
    #     except Exception as e:
    #         reply = f"请求出错：{e}"

        

    #流式调用
# 流式请求后端
    # 流式调用
    stream_url = API_ENDPOINT.replace("/plan_route", "/plan_route_stream")
    placeholder = st.empty()
    reply = ""

    with st.spinner("正在生成回复..."):
        try:
            with requests.post(
                stream_url,
                json={
                    "session_id": current_chat["id"],
                    "query": prompt,
                    "model_name": st.session_state.model_name,
                    "reset": False  # 如果你在UI里点了“新建会话”，也可以改成 True
                },
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    placeholder.markdown(f"请求出错：{resp.text}")
                else:
                    for chunk in resp.iter_content(chunk_size=1, decode_unicode=True):
                        if chunk:
                            reply += chunk
                            placeholder.markdown(
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
            placeholder.markdown(f"请求出错：{e}")




#循环后不显示了
    # # 显示助手回复
    # st.markdown(
    #     f"""
    #     <div style="display: flex; justify-content: flex-start; margin: 6px 0;">
    #         <div style="background-color: #F1F0F0; padding: 10px 14px; border-radius: 14px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
    #              {reply}
    #         </div>
    #     </div>
    #     """,
    #     unsafe_allow_html=True,
    # )

    # 保存助手回复
    current_chat["messages"].append({"role": "assistant", "content": reply})
