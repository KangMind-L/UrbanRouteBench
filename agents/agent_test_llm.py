import random
from langchain_core.prompts.prompt import PromptTemplate
import re, string, os, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))  # 向上回溯3层到项目根目录
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../..")))
# sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
project_root = Path(__file__).resolve().parent.parent  # 向上回溯两级到项目根目录
sys.path.append(str(project_root))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools/planner")))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../tools/planner")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import importlib
from typing import List, Dict, Any
import tiktoken
from pandas import DataFrame
from langchain.chat_models import ChatOpenAI
from langchain.callbacks import get_openai_callback
from langchain.llms.base import BaseLLM
from langchain.prompts import PromptTemplate
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)
from prompts import not_tool_direct
# from utils.func import load_line_json_data, save_file
import sys
import json
import openai
import time
import pandas as pd
from datetime import datetime
from tqdm import tqdm
import argparse
from datasets import load_dataset
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
os.environ["CUDA_VISIBLE_DEVICES"] = "1,2"  # 强制使用 GPU 0

# 设置显存优化 (重要！)
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # 强制使用 GPU 0
# OPENAI_API_KEY = "sk-Qoz7oXQEaT586P3ywtIe5IoRWgZ4NGcxRYAKljcrzZNMPKep"
# GOOGLE_API_KEY = "0"
# DEEPSEEK_API_KEY = "sk-9a737cbf09a84c78bcb8403b5c374e66"
# 魔塔 qwen480，
# "sk-jEnWQN0y0EgIi21lwONLKR5tD5f9Fbsyk6vY8SmwCiHMXztE"
# iflow deepseek3.2  qwen3-max zhipu 4.6 qwen3-32b
# sk-2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2
# nvidia分组  V3.2
# 1bzBQsxqUJuTBChw71Ib1ZTPBlGEzkniXZKC3r373BbXtoK9

# 默认分组 gpt "gemini-2.5-pro",
# sk-mXIoQJ7Y7ojULM9pb6uy8yFbZTwlUjHVLNvJQB1cBsk77KFX
# OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
# GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']
# DEEPSEEK_API_KEY = os.environ['DEEPSEEK_API_KEY']
SHREDDER_API_KEY = "sk-2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2"
SHREDDER_URL = "https://api.shredder.money/v1"
pd.options.display.max_info_columns = 200
os.environ['TIKTOKEN_CACHE_DIR'] = './tmp'
#TODO 工具映射转换
current_dir = os.path.dirname(os.path.abspath(__file__))
def catch_openai_api_error():
    print("查询失败，等待重试")


class ReactAgent:
    def __init__(self,
                 args,
                 mode: str = 'zero_shot',
                 tools: List[str] = None,
                 max_steps: int = 30,
                 max_retries: int = 3,
                 illegal_early_stop_patience: int = 3,
                 react_llm_name = 'gpt-5',
                 planner_llm_name = 'gpt-5',
                 agent_prompt = not_tool_direct,
                #  logs_path = '../logs/',
                #  city_file_path = '../database/background/citySet.txt'
                 ) -> None: 


        self.mode = mode

        self.SHREDDER_API_KEY = SHREDDER_API_KEY 
        # self.agent_prompt = agent_prompt
        self.json_log = []
        if agent_prompt =="not-tool-direct":
            self.agent_prompt = not_tool_direct

        if react_llm_name in ['llama3.1:8b','llama3:70b']:
            stop_list = ['\n']

            self.max_token_length = 30000  # DeepSeek模型的最大token长度 
            self.llm = ChatOpenAI(
                temperature=0.7,
                max_tokens=2048,
                openai_api_key="ollama",  
                base_url="http://localhost:11434/v1",
                model_name=react_llm_name,
                # model_kwargs={"stop": stop_list}
            )

# # ,
#         if  react_llm_name in ["qwen3-max","gpt-5.2","gpt-5.1",'gpt-5','deepseek-v3.2' ,'deepseek-v3.2-exp','deepseek-r1','gemini-2.5-pro','deepseek-v3',"qwen3-coder-480b-a35b-instruct"]:
#             stop_list = ['\n']  
        else:
            self.max_token_length = 30000
            self.llm = ChatOpenAI(temperature=0.7,
                        max_tokens=4096,
                        model_name=react_llm_name,
                        openai_api_key= self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )




        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # print(self.retry_recor
    def run(self, query, reset=True) -> None:
        self.answer = ''
        # self.query = "我要在下午17点之前到达后瑞地铁站。从柏怡科技园乘坐地铁出发，途中需要在3个地方停留：先去金光华广场办事，然后到学府雅苑接人，最后到红岭南路①取些东西。因为是单人出行且预算有限（不超过25元），希望能提供换乘最少的地铁方案，确保我能准时到达目的地。"        
        self.query=query    
        self.step()

        return self.answer

    def step(self) -> None:


       
        self.answer = self.prompt_agent()
        return

      

    def prompt_agent(self,api_max_retries=5, base_delay=4, max_delay=1800) -> str:
        retry = 0
        while True:
            try:
            # #    print(self._build_agent_prompt())
                
                # prompt_content = self._build_agent_prompt()
                # print("=== Prompt Content ===")
                # print(prompt_content)
                # print("=====================")
                # # message = HumanMessage(content=prompt_content)


                # # print("=== Message Object ===")
                # # print(type(message))  # 应该输出 <class 'langchain_core.messages.HumanMessage'>
                # # print(vars(message))  # 查看消息对象的属性
                # # print("=====================")

                # raw_response = self.llm.invoke(prompt_content)
                # # raw_response = self.llm.invoke(prompt_content)

                # print("=== Raw Response ===")
                # print(type(raw_response))  # 检查返回类型
                # print(vars(raw_response))  # 查看响应对象属性
                # print("===================")
                
                # # 然后获取内容
                # response_content = raw_response.content
                # print("=== Response Content ===")
                # print(response_content)
                # print("=======================")
                
                # # 最后格式化
                # formatted = format_step(response_content)
                # print("=== Formatted ===")
                # print(formatted)
                # print("================")
                    
                # request = formatted 
                request = format_step(self.llm.invoke(self._build_agent_prompt()).content)
                # request = format_step(self.llm.invoke(self._build_agent_prompt(),stop=['\n']).content)

                # print(request)
                return request
            except Exception as e:
                catch_openai_api_error()

                retry += 1
                if retry > api_max_retries:
                    raise RuntimeError(
                        f"❌ LLM 调用失败，已重试 {api_max_retries} 次，最后错误: {e}"
                    )

                # 指数退避公式：base * 2^(retry-1)，再加一点随机抖动
                delay = min(base_delay * (5 ** (retry - 1)), max_delay)
                jitter = random.uniform(0, delay * 0.1)   # 0~10% 抖动，防止雪崩
                sleep_time = delay + jitter
                # ptint()

                print(f"⚠️ 第 {retry} 次失败，{sleep_time:.1f}s 后重试…")
                time.sleep(sleep_time)
                # catch_openai_api_error()
                # print(self._build_agent_prompt())
                # print(len(self.enc.encode(self._build_agent_prompt())))
                # time.sleep(30)

    def _build_agent_prompt(self) -> str:
        
        return self.agent_prompt.format(
                query=self.query)

    def is_finished(self) -> bool:
        return self.finished

    def is_halted(self) -> bool:
        return ((self.step_n > self.max_steps) or (
                    len(self.enc.encode(self._build_agent_prompt())) > self.max_token_length)) and not self.finished



### String Stuff ###
gpt2_enc = tiktoken.encoding_for_model("text-davinci-003")
def format_step(step: str) -> str:
    return step.strip('\n').strip()


def normalize_answer(s):
    def remove_articles(text):
        return re.sub(r"\b(a|an|the|usd)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def EM(answer, key) -> bool:
    return normalize_answer(str(answer)) == normalize_answer(str(key))


def remove_observation_lines(text, step_n):
    pattern = re.compile(rf'^Observation {step_n}.*', re.MULTILINE)
    return pattern.sub('', text)

def validate_date_format(date_str: str) -> bool:
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    
    if not re.match(pattern, date_str):
        raise DateError
    return True

def validate_city_format(city_str: str, city_set: list) -> bool:
    if city_str not in city_set:
        raise ValueError(f"{city_str} is not valid city in {str(city_set)}.")
    return True

def parse_args_string(s: str) -> dict:
    # Split the string by commas
    segments = s.split(",")
    
    # Initialize an empty dictionary to store the results
    result = {}
    
    for segment in segments:
        # Check for various operators
        if "contains" in segment:
            if "~contains" in segment:
                key, value = segment.split("~contains")
                operator = "~contains"
            else:
                key, value = segment.split("contains")
                operator = "contains"
        elif "<=" in segment:
            key, value = segment.split("<=")
            operator = "<="
        elif ">=" in segment:
            key, value = segment.split(">=")
            operator = ">="
        elif "=" in segment:
            key, value = segment.split("=")
            operator = "="
        else:
            continue  # If no recognized operator is found, skip to the next segment
                
        # Strip spaces and single quotes
        key = key.strip()
        value = value.strip().strip("'")
        
        # Store the result with the operator included
        result[key] = (operator, value)
        
    return result

def to_string(data) -> str:
    if data is not None:
        if type(data) == DataFrame:
            return data.to_string(index=False)
        else:
            return str(data)
    else:
        return str(None)

def process_single_query(
    number: int,
    query_data_list: pd.DataFrame,
    args,
    model_name: str,
    strategy: str,
):
    # model_name = "gemini-3-flash"
        # "gemini-3-flash" ,
    try:
        # ---------- 1. 读取 query ----------
        try:
            query = query_data_list.iloc[number - 1]["query"]
            query_json_str = query_data_list.iloc[number - 1]["json"]
        except Exception as e:
            return number, f"读取第 {number} 条 query 失败：{e}"

        query = query + "\n结构化参数为：" + str(query_json_str)

        # ---------- 2. 构建输出路径 ----------
        folder_path = os.path.join(
            args.output_dir,args.set_type ,args.query_type, strategy, model_name
        )
        os.makedirs(folder_path, exist_ok=True)

        json_file_path = os.path.join(
            folder_path, f"generated_plan_{number}.json"
        )
        if os.path.exists(json_file_path):
            try:
                existing_result = json.load(open(json_file_path, 'r', encoding='utf-8'))
                if existing_result and existing_result[-1].get(f'{model_name}_{strategy}_results'):
                    print(f"第{number}条数据，模型{model_name}的结果已存在，跳过...")
                    return  number, "success"
            except:
                pass
        # ---------- 3. 读取已有结果（加锁） ----------
        with file_lock:
            if os.path.isfile(json_file_path):
                try:
                    with open(json_file_path, "r", encoding="utf-8") as f:
                        result = json.load(f)
                except Exception as e:
                    return number, f"读取结果文件失败（JSON 损坏）：{e}"
            else:
                result = [{}]

        # ---------- 4. 每个线程独立 Agent（关键修复） ----------
        agent = ReactAgent(
            None,
            max_steps=10,
            # react_llm_name="qwen3-max",
            # planner_llm_name="qwen3-max",            
            react_llm_name=model_name,
            planner_llm_name=model_name,
            agent_prompt=strategy
        )

        # ---------- 5. 调用模型 ----------
        start_time = time.time()

        try:
            planner_results = agent.run(query)
        except Exception as e:
            return number, f"模型调用异常：{e}"

        elapsed = time.time() - start_time
        if elapsed > 300:  # 5 分钟
            return number, "模型调用超时（超过 5 分钟）"


        # ---------- 6. 写结果 ----------
        result[-1]["query"] = query
        result[-1][f"{model_name}_{strategy}_results"] = planner_results

        with file_lock:
            try:
                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)
            except Exception as e:
                return number, f"结果写入失败：{e}"

        return number, "success"

    except Exception as e:
        return number, f"未知异常：{e}"

file_lock = Lock()

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    # parser.add_argument("--output_dir", type=str, default="./args")
    parser.add_argument("--set_type", type=str, default="test")
    parser.add_argument("--output_dir", type=str, default="../output_Result_V4")
    parser.add_argument("--query_type", type=str, default="args")
    args = parser.parse_args()

    # 模型列表google/gemini-2.5-pro
    model_names = [
        # 'qwen3-max',
        # "qwen3-coder-480b-a35b-instruct"
        # "llama3:7b"
        
        # "glm-4.6",
        # "gemini-2.5-pro",
        # # "llama3:70b",
        "qwen3-32b",
        'qwen3-max',
        # "qwen3-coder-480b-a35b-instruct"
        # "llama3:7b"
        "llama3.1:8b",
        "gpt-5.2",
        # "glm-4.7",
        "deepseek-v3.2",

        # "llama3:70b",


        # "gemini-2.5-pro",
        # "gemini-3-pro",
        # "gemini-2.5-flash",

        # "kimi-k2.5",
        # "qwen3-32b",
        # "gemini-3-flash" ,
        # "gpt-5.2",

        # "llama3.1:8b",
        ]
    strategy = "not-tool-direct"

        # "cot",
        # "direct"

    # 加载数据
    if args.set_type == 'train':
        query_data_list = pd.read_csv('../test-V4/train.csv')
    elif args.set_type == 'validation':
        query_data_list = pd.read_csv('../test-V4/val.csv')
    elif args.set_type == 'test':
        query_data_list = pd.read_csv('../test-V4/test.csv')


    numbers = [i for i in range(1,len(query_data_list)+1)]
    # numbers = list[int](range(1, 10))    # 1~50

    # 双层循环
    for model_name in model_names:
    # for idx, agent_prompt in enumerate(agent_prompts):

        # prompt_name = prompt_names[idx]

        print("\n" + "=" * 60)
        print(f"Running model: {model_name} | prompt: {strategy}")
        print("=" * 60)

        with get_openai_callback() as cb:

            # 遍历 50 个 query
            max_workers = min(8, os.cpu_count())  # 可按机器调大

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        process_single_query,
                        number,
                        query_data_list,
                        args,
                        model_name,
                        strategy,
                    )
                    for number in numbers
                ]

                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc=f"{model_name}-{strategy}",
                ):
                    idx, status = future.result()
                    if status != "success":
                        print(f"[Query {idx}] ❌ {status}")
                        

        print("\nCallback info:")
        print(cb)


