from langchain.chat_models import ChatOpenAI
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)
# from langchain_core.messages import HumanMessage
import os

# 设置显存优化 (重要！)
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # 强制使用 GPU 0
stop_list = ['\n']
llm = ChatOpenAI(
    model="deepseek-r1:7b",
    base_url="http://localhost:11434/v1",
    api_key="none",
    temperature=0,
    max_tokens=512,  # 减少 token 防止 OOM
    request_timeout=60,  # 增加超时时间
    model_kwargs={"stop": stop_list}
)

try:
    response = llm.invoke([
        HumanMessage(content="我要在中午12点15分从松岗中英文学校出发，途中需要依次在3个地方停留：先到南头检查站(关内)18办点事，然后去景龙中环龙雷路口接人，最后到梅林联检站（关内）01取些东西。就我一个人出行，希望能规划费用最低的路线方案，总预算控制在25元以内，每个途经点都需要停留半小时以上")
    ])
    print("AI回复:", response.content)
except Exception as e:
    print(f"错误详情: {str(e)}")