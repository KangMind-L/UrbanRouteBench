import random
import re, string, os, sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).parent.parent.parent))  # 向上回溯3层到项目根目录
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../")))
# sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
project_root = Path(__file__).resolve().parent.parent  # 向上回溯两级到项目根目录
sys.path.append(str(project_root))
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
from prompts import json_generate_prompt_2, react_reflect_planner_agent_prompt, reflect_prompt, zeroshot_react_agent_prompt

from preprocess.queryToJson import QUERY_GENERATE_PLANNER
# from utils.func import load_line_json_data, save_file
import sys
import json
import openai
import time
import pandas as pd
from datetime import datetime
from tqdm import tqdm
from langchain_google_genai import ChatGoogleGenerativeAI
import argparse
from datasets import load_dataset
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

# 设置显存优化 (重要！)
os.environ["CUDA_VISIBLE_DEVICES"] = "2,3"  # 强制使用 GPU 0



# OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
# GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']
# DEEPSEEK_API_KEY = os.environ['DEEPSEEK_API_KEY']

# chat-completions
#sk-35FfaisxpT0NLMny3EyRX8FI3qvcTsTHPRc04MrCptehzE2S
# OPENAI_API_KEY = "sk-Qoz7oXQEaT586P3ywtIe5IoRWgZ4NGcxRYAKljcrzZNMPKep"
# GOOGLE_API_KEY = "0"
# DEEPSEEK_API_KEY = "sk-9a737cbf09a84c78bcb8403b5c374e66"
# 魔塔 qwen480，
# "sk-jEnWQN0y0EgIi21lwONLKR5tD5f9Fbsyk6vY8SmwCiHMXztE"
# iflow deepseek3.2  qwen3-max zhipu 4.7 qwen3-32bW
# sk-2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2
# nvidia分组  V3.2
# 1bzBQsxqUJuTBChw71Ib1ZTPBlGEzkniXZKC3r373BbXtoK9

# 默认分组 gpt "gemini-2.5-pro", kimi
# sk-sk-mXIoQJ7Y7ojULM9pb6uy8yFbZTwlUjHVLNvJQB1cBsk77KFX
pd.options.display.max_info_columns = 200
os.environ['TIKTOKEN_CACHE_DIR'] = './tmp'
#TODO 工具映射转换
actionMapping = {"RouteSearch":"routes","Wgs84Search":"wgs84","RouteRank":"ranking","Planner":"planner","NotebookWrite":"notebook"}

SHREDDER_API_KEY = "sk-mXIoQJ7Y7ojULM9pb6uy8yFbZTwlUjHVLNvJQB1cBsk77KFX"
SHREDDER_URL = "https://api.shredder.money/v1"
def catch_openai_api_error():
    print("API请求失败，正在重试。。。。。。")
    # time.sleep(120)


class ReactAgent:
    def __init__(self,
                 args,
                 mode: str = 'zero_shot',
                 tools: List[str] = None,
                 max_steps: int = 30,
                 max_retries: int = 3,
                 illegal_early_stop_patience: int = 3,
                 react_llm_name = 'gpt-3.5-turbo-1106',
                 planner_llm_name = 'gpt-3.5-turbo-1106',
                 strategy = "direct"
                #  logs_path = '../logs/',
                #  city_file_path = '../database/background/citySet.txt'
                 ) -> None: 
        self.SHREDDER_API_KEY = SHREDDER_API_KEY 
        self.max_steps = max_steps
        self.mode = mode
        # self.max_token_length = 0

        self.react_name = react_llm_name
        self.planner_name = planner_llm_name

        if self.mode == 'zero_shot':
            self.agent_prompt = zeroshot_react_agent_prompt
        self.strategy = strategy
        self.json_log = []
        self.lastest_plan = ''

        self.current_observation = ''
        self.current_data = None

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
                        max_tokens=2048,
                        model_name=react_llm_name,
                        openai_api_key= self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
                
        # elif 'Qwen/Qwen3-Coder-480B-A35B-Instruct' in react_llm_name:
        #     stop_list = ['\n']
        #     self.max_token_length = 30000
        #     self.llm = ChatOpenAI(temperature=0,
        #              max_tokens=256,
        #              model_name=react_llm_name,
        #              openai_api_key=SHREDDER_API_KEY,
        #              base_url=SHREDDER_URL, 
        #             #  model_kwargs={"stop": stop_list}
        #              )
        # elif 'deepseek-ai/DeepSeek-V3.2' in react_llm_name:
        #     stop_list = ['\n']
        #     self.max_token_length = 30000  # DeepSeek模型的最大token长度
        #     # 使用DeepSeek API配置
        #     self.llm = ChatOpenAI(temperature=0.7,  # 可以调整temperature
        #             max_tokens=256,
        #             model_name=react_llm_name,
        #             openai_api_key=SHREDDER_API_KEY,  # 使用DeepSeek的API Key
        #             base_url=SHREDDER_URL,  # 指定DeepSeek的API端点
        #             # model_kwargs={"stop": stop_list}
        #             )   
            




        self.illegal_early_stop_patience = illegal_early_stop_patience

        self.tools = self.load_tools(tools, planner_model_name=planner_llm_name,strategy = self.strategy)
        self.max_retries = max_retries
        self.retry_record = {key: 0 for key in self.tools}
        self.retry_record['invalidAction'] = 0

        # print(self.retry_record)

        self.last_actions = []

        # self.log_path = logs_path + datetime.now().strftime('%Y%m%d%H%M%S') + '.out'
        # self.log_file = open(self.log_path, 'a+')

        # print("logs will be stored in " + self.log_path)


        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        self.__reset_agent()

    def run(self, query, reset=True) -> None:

        # self.query = "我要在下午17点之前到达后瑞地铁站。从柏怡科技园乘坐地铁出发，途中需要在3个地方停留：先去金光华广场办事，然后到学府雅苑接人，最后到红岭南路①取些东西。因为是单人出行且预算有限（不超过25元），希望能提供换乘最少的地铁方案，确保我能准时到达目的地。"        
        self.query=query
        if reset:
            self.__reset_agent()

        while not self.is_halted() and not self.is_finished():
            self.step()

        return self.answer, self.scratchpad, self.json_log

    def step(self) -> None:
        def extract_tool_call(text: str):
    # 匹配工具调用：工具名 + [内容直到]
            pattern = r'\b(Planner|NotebookWrite|CoordSearch|RouteSearch|RouteRank)\s*\[[^\]]*\]'
            
            m = re.search(pattern, text)
            if m:
                return m.group(0).strip()   # 只返回匹配到的内容
            
            return ""  # 没匹配到就返回空
        def clean_agent_output(text):

            cleaned = text

            # ① 只删除单独出现的 Thought + 换行（不删后续内容）
            cleaned = re.sub(
                r'\bThought\b\s*\n?',   # Thought + 换行
                '', 
                cleaned
            )

            # ② 删除 Action 及其后全部内容
            cleaned = re.sub(
                r'\bAction\b[:：]?\s*[\s\S]*$',   # Action 后面所有内容
                '',
                cleaned,
                flags=re.IGNORECASE
            )

            return cleaned.strip()


        self.json_log.append({"step": self.step_n, "thought":"",
                              "action": "", "observation": "", "state":""})

        self.scratchpad += f'\nThought {self.step_n}:'
        thought_raw=self.prompt_agent()
        thought = clean_agent_output(thought_raw)
        self.scratchpad += ' ' + thought
        # self.scratchpad += ' ' + self.prompt_agent()

        print("Thought"+self.scratchpad.split('Thought')[-1])
        self.json_log[-1]['thought'] = self.scratchpad.split('\n')[-1].replace(f'\nThought {self.step_n}:',"")
        # self.log_file.write(self.scratchpad.split('\n')[-1] + '\n')


        # Act
        self.scratchpad += "下面推断当前步骤的一次工具调用，"+f'\nAction {self.step_n}:'
        action_raw = self.prompt_agent()

        action = extract_tool_call(action_raw)
        
        # action = re.sub(r'^(?i)action[:\n\s]*', '', action).strip()

        if action == None or action == '' or action == '\n':
            self.scratchpad += "您的操作将根据内容进行过滤。请确保你的动作不是以['\\n', 'Thought', ' action ', 'Observation']开头，并假设所有的动作在这个环境中都是允许的，然后再次执行该动作。"
        else:
            self.scratchpad += ' ' + action


        if len(self.last_actions) > 0 and self.last_actions[-1] != action:
            self.last_actions.clear()

        # refresh last_action list
        self.last_actions.append(action)

        self.json_log[-1]['action'] = self.scratchpad.split('\n')[-1].replace(f'\nAction {self.step_n}:',"")


        # examine if the same action has been repeated 3 times consecutively
        if len(self.last_actions) == 3:
            print("同一动作连续重复3次,在这里停止。")
            # self.log_file.write("The same action has been repeated 3 times consecutively. So we stop here.")
            self.json_log[-1]['state'] = '同样的动作重复3次'
            self.finished = True
            return


        # action_type, action_arg = parse_action(action)
        print(self.scratchpad.split('\n')[-1])
        # self.log_file.write(self.scratchpad.split('\n')[-1]+'\n')

        # Observe
        self.scratchpad += f'\nObservation {self.step_n}: '

        if action == None or action == '' or action == '\n':
            action_type = None 
            action_arg = None
            self.scratchpad += "由于无效操作，没有来自环境的反馈。请确保你的行动不是以[Thought, Action, Observation]开始的。 "
        
        else:
            action_type, action_arg = parse_action(action)
            
            if action_type != "Planner":
                if action_type in actionMapping:
                    pending_action = actionMapping[action_type]
                elif action_type not in actionMapping:
                    pending_action = 'invalidAction'
                
                if pending_action in self.retry_record:
                    if self.retry_record[pending_action] + 1 > self.max_retries:
                        action_type = 'Planner'
                        print(f"{pending_action} early stop due to {self.max_retries} max retries.")
                        # self.log_file.write(f"{pending_action} early stop due to {self.max_retries} max retries.")
                        self.json_log[-1]['state'] = f"{pending_action} early stop due to {self.max_retries} max retries."
                        self.finished = True
                        return
                    
                elif pending_action not in self.retry_record:
                    if self.retry_record['invalidAction'] + 1 > self.max_retries:
                        action_type = 'Planner'
                        print(f"invalidAction Early stop due to {self.max_retries} max retries.")
                        # self.log_file.write(f"invalidAction early stop due to {self.max_retries} max retries.")
                        self.json_log[-1]['state'] = f"invalidAction early stop due to {self.max_retries} max retries."
                        self.finished = True
                        return

            
            if action_type == 'NotebookWrite':
                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'由于篇幅有限而被屏蔽。确保数据已写入笔记本.')
                    if len(to_string(self.current_data).strip()) > 100:
                        self.scratchpad = self.scratchpad.replace(
                            to_string(self.current_data).strip(),
                            '由于篇幅有限而被屏蔽。确保数据已写入笔记本。'
                        )
                    self.current_observation = str(self.tools['notebook'].write(self.current_data, action_arg))
                    self.scratchpad  +=  self.current_observation
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['notebook'] += 1
                    self.current_observation = f'{e}'
                    self.scratchpad += f'{e}'
                    self.json_log[-1]['state'] = f'非法参数，其他错误'
            

            elif action_type == 'CoordSearch':

                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'由于篇幅有限而被屏蔽。确保数据已写入笔记本.')
                    if len(to_string(self.current_data).strip()) > 100:
                        self.scratchpad = self.scratchpad.replace(
                            to_string(self.current_data).strip(),
                            '由于篇幅有限而被屏蔽。确保数据已写入笔记本。'
                        )
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    self.current_data = self.tools['wgs84'].run(action_arg)
                    # print(len(self.current_data))
                    self.current_observation =  to_string(self.current_data)
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['wgs84'] += 1
                    self.current_observation = f'查询坐标失败，地理位置不存在，请重试'
                    self.scratchpad += f'CoordSearch前不应该有数字，查询坐标失败，地理位置不存在，请重试'
                    self.json_log[-1]['state'] = f'非法参数，其他错误'

            elif action_type == 'RouteSearch':

                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'由于篇幅有限而被屏蔽。确保数据已写入笔记本.')
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    # self.current_data = self.tools['routes'].run({"fromPlace": "沙井中心客运北::22.72972098,113.8384241", "toPlace": "信义荔山公馆八号馆::22.59572959254214", "time": "12:14", "arriveBy": "false", "mode": "BUS"})
                    if len(to_string(self.current_data).strip()) > 100:
                        self.scratchpad = self.scratchpad.replace(
                            to_string(self.current_data).strip(),
                            '由于篇幅有限而被屏蔽。确保数据已写入笔记本。'
                        )
                    self.current_data = self.tools['routes'].run(action_arg)
                    
                    self.current_observation =  to_string(self.current_data)

                    self.lastest_plan = self.current_data
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['routes'] += 1
                    self.current_observation = f'搜索路径失败，请重试.'
                    self.scratchpad += f'搜索路径失败，请重试'
                    self.json_log[-1]['state'] = f'非法参数，其他错误'

            elif action_type == 'RouteRank':
# {"fromPlace": "沙井中心客运北::22.72972098,113.8384241", "toPlace": "信义荔山公馆八号馆::22.59572959254214,114.12307127479797", "time": "12:14", "arriveBy": "false", "mode": "BUS"}]
# {"fromPlace": "沙井中心客运北::22.72972098,113.8384241", "toPlace": "信义荔山公馆八号馆::22.59572959254214", "time": "12:14", "arriveBy": "false", "mode": "BUS"}]
                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    # action_arg = f"{self.lastest_plan},{action_arg}"
                    # self.current_data = self.tools['ranking'].run(action_arg)
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'由于篇幅有限而被屏蔽。确保数据已写入笔记本.')
                    if len(to_string(self.current_data).strip()) > 100:
                        self.scratchpad = self.scratchpad.replace(
                            to_string(self.current_data).strip(),
                            '由于篇幅有限而被屏蔽。确保数据已写入笔记本。'
                        )
                    # parts = action_arg.split(",")
                    # user_time = parts[0].strip()                       # '13:17'
                    # arrive_by_str = parts[1].strip().lower()          # 'false' 或 'true'
                    # preference = parts[2].strip() if len(parts) > 2 else None

                    # # 布尔化 arriveBy
                    # arrive_by = True if arrive_by_str == "true" else False
                    # self.current_data = self.tools['ranking'].run(
                    #             text=self.lastest_plan,   # 路线文本
                    #             time=user_time,           # 出发/到达时间
                    #             arriveBy=arrive_by,       # 布尔类型
                    #             preference=preference     # 出行偏好
                    #         )
                    # 解析 action 参数
                    # action_arg 示例: 'time="20:08", time_window=None, preference="时间最少-步行最少", stay_time=None'

                    # 将参数按逗号分隔，再按 '=' 提取 key/value
                    # 将 action_arg 按逗号分割，再按 '=' 提取 key/value
                    params = {}
                    for part in action_arg.split(","):
                        key, value = part.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # 去掉引号，如果是 None 保持 None
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value == "None":
                            value = None
                        elif key in ["time_window", "stay_time"]:  # 转整数
                            value = int(value)
                        params[key] = value

                    # 构建实际调用参数，只保留不为 None 的
                    call_args = {k: v for k, v in params.items() if v is not None}

                    # text 始终传入
                    call_args['text'] = self.lastest_plan

                    # 调用路径排序工具
                    self.current_data = self.tools['ranking'].run(**call_args)




                    self.current_observation =  to_string(self.current_data)
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['ranking'] += 1
                    self.current_observation = f'排名参数解析错误,请重试.'
                    self.scratchpad += f'排名参数解析错误,请重试.'
                    self.json_log[-1]['state'] = f'非法参数，其他错误'
            elif action_type == "Planner":
                self.current_observation = str(self.tools['planner'].run(str(self.tools['notebook'].list_all()),action_arg))
                self.scratchpad  +=  self.current_observation
                self.answer = self.current_observation
                self.__reset_record()
                self.json_log[-1]['state'] = f'Successful'

            else:
                self.retry_record['invalidAction'] += 1
                self.current_observation = "检查工具名和参数，工具有误，重试"
                self.scratchpad += self.current_observation
                self.json_log[-1]['state'] = f'invalidAction'

        if action == None or action == '' or action == '\n':
            print(f'Observation {self.step_n}: ' + "由于无效的动作，没有来自环境的反馈.")
            # write(f'Observation {self.step_n}: ' + "Your action is filtered due to content. Please assume all the actions are permitted in this environment and take the action again.")
            self.json_log[-1]['observation'] = "由于无效的动作，没有来自环境的反馈."
        else:
            print(f'Observation {self.step_n}: ' + self.current_observation+'\n')
            # rite(f'Observation {self.step_n}: ' + self.current_observation+'\n')
            self.json_log[-1]['observation'] = self.current_observation

        self.step_n += 1

        # 

        if action_type and action_type == 'Planner' and self.retry_record['planner']==0:
            
            self.finished = True
            self.answer = self.current_observation
            self.step_n += 1
            return

    def prompt_agent(self,api_max_retries=5, base_delay=4, max_delay=1800) -> str:
        retry = 0
        while True:
            try:
                # print(self._build_agent_prompt())

                # prompt_content = self._build_agent_prompt()
                # print("=== Prompt Content ===")
                # print(prompt_content)
                # print("=====================")


                # raw_response = self.llm.invoke(prompt_content)
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


                # # print(request)
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
        if self.mode == "zero_shot":
            return self.agent_prompt.format(
                scratchpad=self.scratchpad,
                query=self.query)

    def is_finished(self) -> bool:
        return self.finished

    def is_halted(self) -> bool:
        return ((self.step_n > self.max_steps) or (
                    len(self.enc.encode(self._build_agent_prompt())) > self.max_token_length)) and not self.finished

    def __reset_agent(self) -> None:
        self.step_n = 1
        self.finished = False
        self.answer = ''
        self.scratchpad: str = ''
        self.__reset_record()
        self.json_log = []
        self.current_observation = ''
        self.current_data = None
        self.last_actions = []

        if 'notebook' in self.tools:
            self.tools['notebook'].reset()
    
    def __reset_record(self) -> None:
        self.retry_record = {key: 0 for key in self.retry_record}
        self.retry_record['invalidAction'] = 0


    def load_tools(self, tools: List[str], planner_model_name=None,strategy=None) -> Dict[str, Any]:
        tools_map = {}
        for tool_name in tools:
            module = importlib.import_module("tools.{}.apis".format(tool_name))
            
            # Avoid instantiating the planner tool twice 
            if tool_name == 'planner' and planner_model_name is not None:
                # print(tool_name[0].upper())
                # print(tool_name[1:])
                if strategy in ['direct']:
                    tools_map[tool_name] = getattr(module, tool_name[0].upper()+tool_name[1:])(model_name=planner_model_name,SHREDDER_API_KEY =self.SHREDDER_API_KEY,strategy = self.strategy)
                elif strategy in ['cot']:
                    tools_map[tool_name] = getattr(module, tool_name[0].upper()+tool_name[1:])(model_name=planner_model_name,SHREDDER_API_KEY =self.SHREDDER_API_KEY,strategy = self.strategy)

                elif strategy in ['react']:
                    tools_map[tool_name] = getattr(module, "React"+tool_name[0].upper()+tool_name[1:])(model_name=planner_model_name,SHREDDER_API_KEY =self.SHREDDER_API_KEY,strategy = self.strategy)

                elif strategy in ['reflect']:
                    tools_map[tool_name] = getattr(module, "ReactReflect"+tool_name[0].upper()+tool_name[1:])(model_name=planner_model_name,agent_prompt=react_reflect_planner_agent_prompt,reflect_prompt=reflect_prompt,SHREDDER_API_KEY =self.SHREDDER_API_KEY,strategy = self.strategy)
            else:
                tools_map[tool_name] = getattr(module, tool_name[0].upper()+tool_name[1:])()
        return tools_map

# class PlanAgent:
#     def __init__(self,
#                 #  logs_path = '../logs/',
#                 #  city_file_path = '../database/background/citySet.txt'
#                  ) -> None: 

#         stop_list = [']\']\n']

#         self.max_token_length = 60000  # DeepSeek模型的最大token长度 
#         self.llm = ChatOpenAI(
#             temperature=0,
#             max_tokens=512,
#             openai_api_key="EMPTY",  
#             base_url="http://localhost:11434/v1",
#             model_name="llama2-7b-finetune",
#             model_kwargs={"stop": stop_list}
#         )



#     def run(self, query) -> string:

#         # self.query = "我要在下午17点之前到达后瑞地铁站。从柏怡科技园乘坐地铁出发，途中需要在3个地方停留：先去金光华广场办事，然后到学府雅苑接人，最后到红岭南路①取些东西。因为是单人出行且预算有限（不超过25元），希望能提供换乘最少的地铁方案，确保我能准时到达目的地。"        
#         self.query=query
#         self.plan = self.prompt_agent()
#         return self.plan



#     def prompt_agent(self) -> str:
#         while True:
#             try:
#                 content = "你是一个路径规划助手，请将-"+self.query+"的工具执行计划输出,只能输出一次工具执行结果，不需要重复的内容"""
#                 request = format_step(self.llm.invoke([HumanMessage(content)]).content)

#                 return request
#             except:
#                 catch_openai_api_error()
#                 print(self._build_agent_prompt())
#                 print(len(self.enc.encode(self._build_agent_prompt())))
#                 time.sleep(5)



### String Stuff ###
gpt2_enc = tiktoken.encoding_for_model("text-davinci-003")
def parse_action(string):
    pattern = r'^(\w+)\[(.+)\]$'
    match = re.match(pattern, string)

    try:
        if match:
            action_type = match.group(1)
            action_arg = match.group(2)
            return action_type, action_arg
        else:
            return None, None
        
    except:
        return None, None

def format_step(step: str) -> str:
    return step.strip().strip('\n')

def truncate_scratchpad(scratchpad: str, n_tokens: int = 1600, tokenizer=gpt2_enc) -> str:
    lines = scratchpad.split('\n')
    observations = filter(lambda x: x.startswith('Observation'), lines)
    observations_by_tokens = sorted(observations, key=lambda x: len(tokenizer.encode(x)))
    while len(gpt2_enc.encode('\n'.join(lines))) > n_tokens:
        largest_observation = observations_by_tokens.pop(-1)
        ind = lines.index(largest_observation)
        lines[ind] = largest_observation.split(':')[0] + ': [truncated wikipedia excerpt]'
    return '\n'.join(lines)


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
"""设置步行最大时间
多加几条路径"""
# if __name__ == '__main__':
#     #TODO 加工具
#     tools_list = ["routes","wgs84","ranking","planner","notebook"]
#     model_names = ['qwen3-max','gpt-5']
#     # model_names = ["gpt-5","qwen3-coder-480b-a35b-instruct",'deepseek-v3.2','llama3.1:8b']

#     # model_names = ['gpt-5']
#     # "gpt-5",

#     # model_name = ['gpt-3.5-turbo-1106','gpt-4-1106-preview','gemini','mistral-7B-32K','mixtral','ChatGLM3-6B-32K'][2]
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--query_type", type=str, default="args")
#     parser.add_argument("--set_type", type=str, default="train")
#     parser.add_argument("--model_name", type=str, default="gpt-5") 
#     parser.add_argument("--output_dir", type=str, default="../output_Result")
#     parser.add_argument("--strategy", type=str, default="ReAct")
#     args = parser.parse_args()
#     # if args.set_type == 'validation':
#     if args.set_type == 'train':

#         # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
#         query_data_list = pd.read_csv('../12-20/train.csv')
#     elif args.set_type == 'validation':
#         query_data_list = pd.read_csv('../12-20/val.csv')
#     elif args.set_type == 'test':
#         query_data_list = pd.read_csv('../12-20/test.csv')

#     # elif args.set_type == 'test':
#     #     query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']

        
#     # numbers = [i for i in range(1,len(query_data_list)+1)]
#     numbers = [63]

#     # numbers = [i for i in range(36,51)] # deepseek
#     # numbers = [i for i in range(21,51)] # deepseek

#     # numbers = [25] # gpt-5

#     #TODO 迭代次数
#     # agent_plan = PlanAgent()
#     # plan = agent_plan.run()
#     for model_name in model_names:
#         agent = ReactAgent(None, tools=tools_list,max_steps=30,react_llm_name=model_name,planner_llm_name=model_name)
#         with get_openai_callback() as cb:
            
#             for number in tqdm(numbers[:]):
#                 query = query_data_list.iloc[number-1]['query']
#                 # check if the directory exists
#                 if not os.path.exists(os.path.join(f'{args.output_dir}/{args.query_type}/{args.strategy}/{model_name}')):
#                     os.makedirs(os.path.join(f'{args.output_dir}/{args.query_type}/{args.strategy}/{model_name}'))
#                 if not os.path.exists(os.path.join(f'{args.output_dir}/{args.query_type}/{args.strategy}/{model_name}/generated_plan_{number}.json')):
#                     result =  [{}]
#                 else:
#                     result = json.load(open(os.path.join(f'{args.output_dir}/{args.query_type}/{args.strategy}/{model_name}/generated_plan_{number}.json'), encoding='utf-8'))
                    
#                 while True:
#                     # plan = agent_plan.run(query)
#                     planner_results, scratchpad, action_log  = agent.run(query)
#                     if planner_results != None:
#                         break
                
#                 if planner_results == 'Max Token Length Exceeded.':
#                     result[-1][f'{model_name}_{args.strategy}_results_logs'] = scratchpad 
#                     result[-1][f'{model_name}_{args.strategy}_results'] = 'Max Token Length Exceeded.'
#                     action_log[-1]['state'] = 'Max Token Length of Planner Exceeded.'
#                     result[-1][f'{model_name}_{args.strategy}_action_logs'] = action_log
#                 else:
#                     result[-1][f'{model_name}_{args.strategy}_results_logs'] = scratchpad 
#                     result[-1][f'{model_name}_{args.strategy}_results'] = planner_results
#                     result[-1][f'{model_name}_{args.strategy}_action_logs'] = action_log

#                 # write to json file
#                 # with open(os.path.join(f'{args.output_dir}/{args.set_type}/generated_plan_{number}.json'), 'w',) as f:
#                 #     json.dump(result, f, indent=4)
#                 with open(os.path.join(f'{args.output_dir}/{args.query_type}/{args.strategy}/{model_name}/generated_plan_{number}.json'), 'w',encoding='utf-8' ) as f:
#                     json.dump(result, f,  ensure_ascii=False,indent=4)
            
#         print(cb)




import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from langchain.callbacks import get_openai_callback
import os
import json
import pandas as pd
import argparse
import asyncio
from typing import List, Dict, Any

# 创建线程安全的队列
result_queue = queue.Queue()
failed_queue = queue.Queue()
lock = threading.Lock()
def replace_react_with_direct(result_list, model_name):
    """
    将 result_list[-1] 中的 ReAct 字段名原地替换为 direct
    """
    if not result_list or not isinstance(result_list, list):
        return False

    item = result_list[-1]
    modified = False

    key_map = {
        f"{model_name}_ReAct_results": f"{model_name}_direct_results",
        f"{model_name}_ReAct_results_logs": f"{model_name}_direct_results_logs",
        f"{model_name}_ReAct_action_logs": f"{model_name}_direct_action_logs",
    }

    for old_key, new_key in key_map.items():
        if old_key in item:
            # 若 direct 不存在才迁移，避免覆盖
            if new_key not in item:
                item[new_key] = item[old_key]
            del item[old_key]
            modified = True

    return modified

def process_model_query(model_name: str, number: int, query_data_list: pd.DataFrame, 
                       tools_list: List[str], output_dir: str, query_type: str, 
                       strategy: str, agent_class,set_type) -> Dict[str, Any]:
    """
    处理单个模型对单个查询的任务
    """

    output_path = os.path.join(output_dir, set_type,query_type, strategy, model_name, f'generated_plan_{number}.json')

    if os.path.exists(output_path):
        try:
            existing_result = json.load(open(output_path, 'r', encoding='utf-8'))
            if existing_result and existing_result[-1].get(f'{model_name}_{strategy}_results'):
                print(f"第{number}条数据，模型{model_name}的结果已存在，跳过...")
                return {'model': model_name, 'number': number, 'status': 'skipped'}
        except:
            pass
    # if os.path.exists(output_path):
    #     try:
    #         with open(output_path, 'r', encoding='utf-8') as f:
    #             existing_result = json.load(f)

    #         # ---------- 1. ReAct → direct 字段名迁移 ----------
    #         if strategy == "direct" and existing_result and isinstance(existing_result, list):
    #             last_item = existing_result[-1]
    #             modified = False

    #             key_map = {
    #                 f"{model_name}_ReAct_results": f"{model_name}_direct_results",
    #                 f"{model_name}_ReAct_results_logs": f"{model_name}_direct_results_logs",
    #                 f"{model_name}_ReAct_action_logs": f"{model_name}_direct_action_logs",
    #             }

    #             for old_key, new_key in key_map.items():
    #                 if old_key in last_item:
    #                     if new_key not in last_item:
    #                         last_item[new_key] = last_item[old_key]
    #                     del last_item[old_key]
    #                     modified = True

    #             if modified:
    #                 with open(output_path, 'w', encoding='utf-8') as f:
    #                     json.dump(existing_result, f, ensure_ascii=False, indent=4)
    #                 print(
    #                     f"第{number}条数据，模型{model_name}：已将 ReAct 字段替换为 direct"
    #                 )

    #         # ---------- 2. 判断 direct 结果是否已存在 ----------
    #         direct_key = f"{model_name}_direct_results"
    #         if existing_result and existing_result[-1].get(direct_key):
    #             print(
    #                 f"第{number}条数据，模型{model_name} 的 direct 结果已存在，跳过..."
    #             )
    #             return {
    #                 'model': model_name,
    #                 'number': number,
    #                 'status': 'skipped'
    #             }

    #     except Exception as e:
    #         print(f"第{number}条数据，读取或处理已有结果失败，继续执行。原因：{e}")

    # 创建输出目录
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result_data = {}
    if query_type =="query1":
        raw_query = query_data_list.iloc[number-1]['query1']
    elif query_type =="query2":
        raw_query = query_data_list.iloc[number-1]['query2']
    else:
         raw_query = query_data_list.iloc[number-1]['query']
    try:
        if query_type !="args":
            param_agent = QUERY_GENERATE_PLANNER(
                max_steps=30,
                react_llm_name=model_name,
                planner_llm_name=model_name,
                api_key =SHREDDER_API_KEY
            )
            # 解析参数
            while True:
                arguments = param_agent.run(raw_query)
                if not arguments:
                    continue
                break

            # 拼接最终 query
            
        else:
            arguments = query_data_list.iloc[number-1]['json']
        
        # 检查文件是否已存在
        query = raw_query + "\n结构化参数为：" + arguments

        
        # 初始化代理
        agent = agent_class(None, tools=tools_list, max_steps=30, 
                           react_llm_name=model_name, planner_llm_name=model_name,strategy = strategy)
        
        # 执行查询
        max_retries = 3
        for retry in range(max_retries):
            try:
                planner_results, scratchpad, action_log = agent.run(query)
                
                if planner_results is None:
                    if retry < max_retries - 1:
                        print(f"第{number}条数据，模型{model_name}第{retry+1}次重试...")
                        continue
                    else:
                        planner_results = 'No results after retries'
                        scratchpad = 'No scratchpad after retries'
                        action_log = [{'state': 'No results after retries'}]
                
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"第{number}条数据，模型{model_name}第{retry+1}次重试，错误: {str(e)}")
                    import time
                    time.sleep(2)  # 等待2秒后重试
                else:
                    planner_results = f"Error: {str(e)}"
                    scratchpad = f"Error: {str(e)}"
                    action_log = [{'state': f"Error: {str(e)}"}]
                    return 
        
        # 准备结果
        result = [{}]
        if planner_results == 'Max Token Length Exceeded.':
            result[-1][f'{model_name}_{strategy}_results_logs'] = scratchpad 
            result[-1][f'{model_name}_{strategy}_results'] = 'Max Token Length Exceeded.'
            if action_log and len(action_log) > 0:
                action_log[-1]['state'] = 'Max Token Length of Planner Exceeded.'
            result[-1][f'{model_name}_{strategy}_action_logs'] = action_log
        else:
            result[-1][f'{model_name}_{strategy}_results_logs'] = scratchpad 
            result[-1][f'{model_name}_{strategy}_results'] = "结构化参数如下:"+arguments+"\n"+planner_results
            result[-1][f'{model_name}_{strategy}_action_logs'] = action_log
        
        # 保存到文件
        with lock: 
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
        
        result_data = {
            'model': model_name,
            'number': number,
            'status': 'success',
            'path': output_path
        }
        
    except Exception as e:
        result_data = {
            'model': model_name,
            'number': number,
            'status': 'failed',
            'error': str(e)
        }
        failed_queue.put((model_name, number, str(e)))
    
    return result_data

def process_all_models_parallel(model_names: List[str], numbers: List[int], 
                               query_data_list: pd.DataFrame, tools_list: List[str],
                               output_dir: str, query_type_list: pd.DataFrame, strategy_list: pd.DataFrame,
                               agent_class, max_workers_per_model: int = 2,set_type = "direct") -> Dict[str, Any]:
    """
    并行处理所有模型和所有查询
    """
    all_results = []
    failed_tasks = []
    
    # 创建进度条
    total_tasks = len(model_names) * len(numbers)*len(query_type_list)*len(strategy_list)
    print(f"总任务数: {total_tasks} ")
    
    with ThreadPoolExecutor(max_workers=min(max_workers_per_model * len(model_names), os.cpu_count() * 2)) as executor:
        # 提交所有任务
        future_to_task = {}
        for model_name in model_names:
            for query_type in query_type_list:
                for strategy in strategy_list:
 
                    for number in numbers:
                        task = executor.submit(
                            process_model_query, 
                            model_name, number, query_data_list, tools_list,
                            output_dir, query_type, strategy, agent_class,set_type
                        )
                        future_to_task[task] = (model_name, number)
        
        # 处理完成的任务
        with tqdm(total=total_tasks, desc="整体进度") as pbar:
            for future in as_completed(future_to_task):
                model_name, number = future_to_task[future]
                
                try:
                    result = future.result(timeout=300)  # 5分钟超时
                    all_results.append(result)
                    
                    if result.get('status') == 'failed':
                        failed_tasks.append((model_name, number, result.get('error', 'Unknown error')))
                    
                except Exception as e:
                    error_msg = f"任务执行异常: {str(e)}"
                    failed_tasks.append((model_name, number, error_msg))
                    print(f"模型 {model_name} 第{number}条数据异常: {error_msg}")
                
                pbar.update(1)
    
    return {
        'all_results': all_results,
        'failed_tasks': failed_tasks
    }

if __name__ == '__main__':
    # 工具列表


    tools_list = ["routes", "wgs84", "ranking", "planner", "notebook"]
    model_names = [
        # "deepseek-v3.2-exp",
    #    "deepseek-v3.2",
        # 'qwen3-max',
        # "qwen3-coder-480b-a35b-instruct"
        # "llama3:7b"
        # "llama3.1:8b",
        "gpt-5.4",
        # "glm-4.7",
        # "llama3:70b",
        # "qwen3-32b",
        # "gemini-2.5-pro",
        # "gemini-3-pro",
        # "gemini-2.5-flash",
        #   "gemini-3-flash",
        # "kimi-k2.5",
        # "gemini-3-pro-preview",
        # "gemini-3-flash-preview"
        ]
    query_type_list=[
        # "query",
        # "query1",
        # "query2",
        "args"
        ]
    strategy_list = [
        # "direct",
        # "cot",
        "react",
        # "reflect"



        ]
    # model_names = ['qwen3-max',"gpt-5", "qwen3-coder-480b-a35b-instruct", 'deepseek-v3.2', 'llama3.1:8b',"gemini-3-pro","gemini-2.5-pro"]
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--query_type", type=str, default="query")
    parser.add_argument("--set_type", type=str, default="test")
    parser.add_argument("--model_name", type=str, default="gpt-5") 
    parser.add_argument("--output_dir", type=str, default="../output_Result_V5")
    parser.add_argument("--strategy", type=str, default="ReAct")
    parser.add_argument("--max_workers", type=int, default=1, help="每个模型的并行工作线程数")
    args = parser.parse_args()
    
    # 加载数据
    if args.set_type == 'train':
        query_data_list = pd.read_csv('../test-V4/train.csv')
    elif args.set_type == 'validation':
        query_data_list = pd.read_csv('../test-V4/val.csv')
    elif args.set_type == 'test':
        query_data_list = pd.read_csv('../test-V4/test.csv')
    
    # 设置要处理的数字
    # numbers = [13]  # 示例，可以改为 range(1, 51) 等
    # numbers = [i for i in range(1,len(query_data_list)+1)]
    import json

    file_path = "/home/kangpeng/TripPlannerGPT/output_Result_combination_jsonl_V4/test/args_gpt-5.2_react_submission.jsonl"

    numbers = []

    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            data = json.loads(line)
            
            if "出行计划" in data and data["出行计划"] == []:
                numbers.append(i)

    print("出现 '出行计划: []' 的行号：")
    print(numbers)
    # print("数量：", len(line_numbers))
    # numbers = [1]
    # 统计信息
    start_time = time.time()
    
    # 并行处理
    with get_openai_callback() as cb:
        results = process_all_models_parallel(
            model_names=model_names,
            numbers=numbers,
            query_data_list=query_data_list,
            tools_list=tools_list,
            output_dir=args.output_dir,
            query_type_list=query_type_list,
            strategy_list=strategy_list,
            agent_class=ReactAgent,  # 确保ReactAgent已定义
            max_workers_per_model=args.max_workers,
            set_type= args.set_type
        )
    
    end_time = time.time()
    
    # 输出统计信息
    print("\n" + "="*50)
    print("处理完成统计:")
    print(f"总耗时: {end_time - start_time:.2f}秒")
    print(f"成功任务数: {len([r for r in results['all_results'] if r.get('status') == 'success'])}")
    print(f"失败任务数: {len(results['failed_tasks'])}")
    print(f"跳过任务数: {len([r for r in results['all_results'] if r.get('status') == 'skipped'])}")
    
    if results['failed_tasks']:
        print("\n失败任务详情:")
        for model_name, number, error in results['failed_tasks']:
            print(f"  模型: {model_name}, 第{number}条数据, 错误: {error}")
    
    print(f"\nAPI调用统计:")
    print(cb)
    
    # 保存处理结果摘要
    summary_path = os.path.join(args.output_dir, f"processing_summary_{args.set_type}_{int(time.time())}.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        summary = {
            'parameters': vars(args),
            'statistics': {
                'total_time_seconds': end_time - start_time,
                'success_count': len([r for r in results['all_results'] if r.get('status') == 'success']),
                'failed_count': len(results['failed_tasks']),
                'skipped_count': len([r for r in results['all_results'] if r.get('status') == 'skipped']),
                'failed_tasks': results['failed_tasks']
            },
            'api_usage': {
                'total_tokens': cb.total_tokens,
                'prompt_tokens': cb.prompt_tokens,
                'completion_tokens': cb.completion_tokens,
                'total_cost': cb.total_cost
            }
        }
        json.dump(summary, f, ensure_ascii=False, indent=4)
    
    print(f"\n处理摘要已保存到: {summary_path}")


