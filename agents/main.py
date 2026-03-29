# main.py
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


# -----------------------------
# 会话存储
# -----------------------------
store = {}
def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = []
    return store[session_id]

# -----------------------------
# FastAPI 初始化
# -----------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# -----------------------------
# 请求模型定义
# -----------------------------
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    model_name: str
    

# -----------------------------
# 系统提示
# -----------------------------
SYSTEM_PROMPT = """
你是深圳市的一个智能的出行路线规划交互助手，可以和用户进行自然对话，也可以执行简单的出行规划。
"""

# -----------------------------
# API 配置
# -----------------------------
API_URL = "https://api.shredder.money/v1/chat/completions"
API_KEY = "sk-Qoz7oXQEaT586P3ywtIe5IoRWgZ4NGcxRYAKljcrzZNMPKep"

# -----------------------------
# 调用模型生成回复
# -----------------------------
def generate_reply(session_id: str, query: str, model_name: str):
    history = get_session_history(session_id)

    # 构建 message 列表
    messages = []
    if len(history) == 0:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})

    # 构造请求体
    data = {
        "model": model_name,
        "messages": messages
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 发送请求
    response = requests.post(API_URL, headers=headers, json=data, verify=False)
    result = response.json()

    # 解析返回内容
    try:
        reply = result["choices"][0]["message"]["content"]
    except Exception as e:
        reply = f"[错误] 无法解析模型回复: {result}"

    # 更新会话历史
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": reply})

    return reply

# -----------------------------
# FastAPI 接口
# -----------------------------
# @app.post("/plan_route")
# def plan_route_api(request: QueryRequest):
#     reply = generate_reply(request.session_id, request.query, request.model_name)
#     return {"reply": reply}


from fastapi.responses import StreamingResponse
import json

@app.post("/plan_route_stream")
def plan_route_stream(request: QueryRequest):
    def event_stream():
        history = get_session_history(request.session_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": request.query}]
        
        data = {
            "model": request.model_name,
            "messages": messages,
            "stream": True
        }
        
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
        
        full_reply = ""  # 用于存储整个助手回复
        with requests.post(API_URL, headers=headers, json=data, stream=True, verify=False) as r:
            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        chunk = decoded[len("data: "):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            content = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                            full_reply += content
                            yield content
                        except:
                            continue
        # ✅ 请求完成后，把用户和助手消息加入 history
        history.append({"role": "user", "content": request.query})
        history.append({"role": "assistant", "content": full_reply})
    return StreamingResponse(event_stream(), media_type="text/plain")


# -----------------------------
# 本地测试
# -----------------------------
# -----------------------------
# ✅ 本地测试（流式 stream）
# -----------------------------
def test_stream():
    print("=== 开始测试流式输出（同步方式） ===")

    # 测试数据
    session_id = "test-stream"
    query = "我在深圳大学，去世界之窗怎么走？"
    model_name="gpt-5"
    req = QueryRequest(query=query, session_id=session_id, model_name = model_name)

    print("用户:", query)
    print("AI: ", end="")

    # 手动构造 stream 请求（不依赖 FastAPI）
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    data = {
        "model": req.model_name,
        "messages": messages,
        "stream": True
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}

    # 真正发起流式请求
    with requests.post(API_URL, headers=headers, json=data, stream=True, verify=False) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    chunk = decoded[len("data: "):].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        content = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                        print(content, end="")
                    except:
                        continue

    print("\n=== 流式测试结束 ===")

if __name__ == "__main__":
    # print("=== 本地测试开始 ===")
    # session_id = "test-session"

    # q1 = "我在崇文花园"
    # r1 = generate_reply(session_id, q1, "gpt-5")
    # print("\n用户:", q1)
    # print("AI:", r1)

    # q2 = "我家是在哪里？"
    # r2 = generate_reply(session_id, q2, "gpt-5")
    # print("\n用户:", q2)
    # print("AI:", r2)

    # print("\n=== 最终会话历史 ===")
    # for i, msg in enumerate(get_session_history(session_id), 1):
    #     print(f"{i}. {msg['role']}: {msg['content']}")
    test_stream()


