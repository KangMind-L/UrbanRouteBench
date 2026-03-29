import re, string, os, sys
from pathlib import Path

import requests
sys.path.append(str(Path(__file__).parent.parent.parent))  # 向上回溯3层到项目根目录
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../..")))
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

from prompts import zeroshot_react_agent_prompt
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
from fastapi.responses import StreamingResponse

# 设置显存优化 (重要！)
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"  # 强制使用 GPU 0



# OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
# GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']
# DEEPSEEK_API_KEY = os.environ['DEEPSEEK_API_KEY']

tools_list = ["notebook","routes","wgs84","planner"]
OPENAI_API_KEY = "sk-Qoz7oXQEaT586P3ywtIe5IoRWgZ4NGcxRYAKljcrzZNMPKep"
GOOGLE_API_KEY = "0"
DEEPSEEK_API_KEY = "sk-9a737cbf09a84c78bcb8403b5c374e66"
pd.options.display.max_info_columns = 200
os.environ['TIKTOKEN_CACHE_DIR'] = './tmp'
#TODO 工具映射转换
actionMapping = {"RouteSearch":"routes","Wgs84Search":"wgs84","Planner":"planner","NotebookWrite":"notebook"}

def catch_openai_api_error():
    error = sys.exc_info()[0]
    if error == openai.error.APIConnectionError:
        print("APIConnectionError")
    elif error == openai.error.RateLimitError:
        print("RateLimitError")
        time.sleep(60)
    elif error == openai.error.APIError:
        print("APIError")
    elif error == openai.error.AuthenticationError:
        print("AuthenticationError")
    else:
        print("API error:", error)


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
    reset: bool = False 

# -----------------------------
# 系统提示
# -----------------------------
SYSTEM_PROMPT = """
你是深圳市的一个智能的出行路线规划交互助手，可以和用户进行自然对话，也可以执行简单的出行规划。
"""

API_URL = "https://api.shredder.money/v1/chat/completions"
API_KEY = "sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi"
agent_pool = {}  # {(session_id, model_name): agent_instance}

@app.post("/plan_route_stream")
def run_route(req: QueryRequest):
    key = (req.session_id, req.model_name)
    print(f"当前请求 session_id={req.session_id}, model_name={req.model_name}")

    # 判断是否需要重置
    if req.reset or key not in agent_pool:
        print(f">>> 初始化 ReactAgent 实例 ({req.session_id}, {req.model_name})")
        agent_pool[key] = ReactAgent(
            None,
            tools=tools_list,
            max_steps=20,
            react_llm_name=req.model_name,
            planner_llm_name=req.model_name
        )
    else:
        print(f">>> 复用已有 ReactAgent 实例 ({req.session_id}, {req.model_name})")

    agent_instance = agent_pool[key]
    planner_results, scratchpad, action_log = agent_instance.run(req.query)
    
    return planner_results, scratchpad, action_log

class ReactAgent:

    # @app.post("/plan_route_stream")
    # def plan_route_stream(request: QueryRequest):
    #     def event_stream():
    #         history = get_session_history(request.session_id)
    #         messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": request.query}]
            
    #         data = {
    #             "model": request.model_name,
    #             "messages": messages,
    #             "stream": True
    #         }
            
    #         headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
            
    #         full_reply = ""  # 用于存储整个助手回复
    #         with requests.post(API_URL, headers=headers, json=data, stream=True, verify=False) as r:
    #             for line in r.iter_lines():
    #                 if line:
    #                     decoded = line.decode("utf-8")
    #                     if decoded.startswith("data: "):
    #                         chunk = decoded[len("data: "):].strip()
    #                         if chunk == "[DONE]":
    #                             break
    #                         try:
    #                             content = json.loads(chunk)["choices"][0]["delta"].get("content", "")
    #                             full_reply += content
    #                             yield content
    #                         except:
    #                             continue
    #         # ✅ 请求完成后，把用户和助手消息加入 history
    #         history.append({"role": "user", "content": request.query})
    #         history.append({"role": "assistant", "content": full_reply})
    #     return StreamingResponse(event_stream(), media_type="text/plain")

    def __init__(self,
                 args,
                 mode: str = 'zero_shot',
                 tools: List[str] = None,
                 max_steps: int = 30,
                 max_retries: int = 3,
                 illegal_early_stop_patience: int = 3,
                 react_llm_name = 'gpt-3.5-turbo-1106',
                 planner_llm_name = 'gpt-3.5-turbo-1106',
                #  logs_path = '../logs/',
                #  city_file_path = '../database/background/citySet.txt'
                 ) -> None: 

        self.answer = ''
        self.max_steps = max_steps
        self.mode = mode

        self.react_name = react_llm_name
        self.planner_name = planner_llm_name

        if self.mode == 'zero_shot':
            self.agent_prompt = zeroshot_react_agent_prompt

        self.json_log = []

        self.current_observation = ''
        self.current_data = None

        if 'gpt-3.5' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 15000
            self.llm = ChatOpenAI(temperature=1,
                    max_tokens=256,
                    model_name=react_llm_name,
                    openai_api_key=OPENAI_API_KEY,
                    model_kwargs={"stop": stop_list})
        
        elif 'gpt-5' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 15000
            self.llm = ChatOpenAI(temperature=1,
                    max_tokens=256,
                    model_name=react_llm_name,
                    openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
                    base_url = "https://api.shredder.money/v1",
                    # model_kwargs={"stop": stop_list}
                    )
        elif 'ZhipuAI/GLM-4.6' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 15000
            self.llm = ChatOpenAI(temperature=1,
                    max_tokens=256,
                    model_name=react_llm_name,
                    openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
                    base_url = "https://api.shredder.money/v1",
                    # model_kwargs={"stop": stop_list}
                    )
            
            # print(self.llm.invoke("你是谁"))
                    
        elif 'gpt-4' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 30000
            self.llm = ChatOpenAI(temperature=0,
                    max_tokens=256,
                    model_name=react_llm_name,
                    openai_api_key=OPENAI_API_KEY,
                    model_kwargs={"stop": stop_list})
        elif 'deepseek-chat' in react_llm_name:
            stop_list = ['\n']
            self.max_token_length = 60000  # DeepSeek模型的最大token长度
    
            # 使用DeepSeek API配置
            self.llm = ChatOpenAI(temperature=0.7,  # 可以调整temperature
                    max_tokens=256,
                    model_name=react_llm_name,
                    openai_api_key='sk-9a737cbf09a84c78bcb8403b5c374e66',  # 使用DeepSeek的API Key
                    base_url="https://api.deepseek.com/v1",  # 指定DeepSeek的API端点
                    model_kwargs={"stop": stop_list})   
            
        elif 'deepseek-ft' in react_llm_name:
            stop_list = ['\n']

            self.max_token_length = 60000  # DeepSeek模型的最大token长度 
            self.llm = ChatOpenAI(
                temperature=0,
                max_tokens=512,
                openai_api_key="EMPTY",  
                base_url="http://localhost:11434/v1",
                model_name="deepseek-ft",

                # model_kwargs={"stop": stop_list}
            )
        elif 'llama2:7b' in react_llm_name:
            stop_list = ['\n']

            self.max_token_length = 60000  # DeepSeek模型的最大token长度 
            self.llm = ChatOpenAI(
                temperature=0,
                max_tokens=512,
                openai_api_key="EMPTY",  
                base_url="http://localhost:11434/v1",
                model_name="llama2:7b",
                model_kwargs={"stop": stop_list}
            )



        self.illegal_early_stop_patience = illegal_early_stop_patience

        self.tools = self.load_tools(tools, planner_model_name=planner_llm_name)
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
        # print(query)
        if reset:
            self.__reset_agent()

        while not self.is_halted() and not self.is_finished():
            self.step()

        return self.answer, self.scratchpad, self.json_log

    def step(self) -> None:

        self.json_log.append({"step": self.step_n, "thought":"",
                              "action": "", "observation": "", "state":""})

        self.scratchpad += f'\nThought {self.step_n}:'
        self.scratchpad += ' ' + self.prompt_agent()

        print(self.scratchpad.split('\n')[-1])
        self.json_log[-1]['thought'] = self.scratchpad.split('\n')[-1].replace(f'\nThought {self.step_n}:',"")
        # self.log_file.write(self.scratchpad.split('\n')[-1] + '\n')


        # Act
        self.scratchpad += f'\nAction {self.step_n}:'
        action = self.prompt_agent()

        if action == None or action == '' or action == '\n':
            self.scratchpad += " Your action is filtered due to content. Please make sure your action does not start with ['\\n', 'Thought', 'Action', 'Observation'] and assume all the actions are permitted in this environment and take the action again."
            self.scratchpad += ' ' + action


        if len(self.last_actions) > 0 and self.last_actions[-1] != action:
            self.last_actions.clear()

        # refresh last_action list
        self.last_actions.append(action)

        self.json_log[-1]['action'] = self.scratchpad.split('\n')[-1].replace(f'\nAction {self.step_n}:',"")


        # examine if the same action has been repeated 3 times consecutively
        if len(self.last_actions) == 3:
            print("The same action has been repeated 3 times consecutively. So we stop here.")
            # self.log_file.write("The same action has been repeated 3 times consecutively. So we stop here.")
            self.json_log[-1]['state'] = 'same action 3 times repeated'
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
            self.scratchpad += "No feedback from the environment due to the null action. Please make sure your action does not start with [Thought, Action, Observation]."
        
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
                    self.current_observation = str(self.tools['notebook'].write(self.current_data, action_arg))
                    self.scratchpad  +=  self.current_observation
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['notebook'] += 1
                    self.current_observation = f'{e}'
                    self.scratchpad += f'{e}'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'
            

            elif action_type == 'Wgs84Search':

                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    self.current_data = self.tools['wgs84'].run(action_arg)
                    self.current_observation =  to_string(self.current_data)
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['googleDistanceMatrix'] += 1
                    self.current_observation = f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.scratchpad += f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'

            elif action_type == 'RouteSearch':

                try:
                    # self.scratchpad = self.scratchpad.replace(to_string(self.current_data).strip(),'Masked due to limited length. Make sure the data has been written in Notebook.')
                    self.current_data = self.tools['routes'].run(action_arg)
                    self.current_observation =  to_string(self.current_data)
                    self.scratchpad += self.current_observation 
                    self.__reset_record()
                    self.json_log[-1]['state'] = f'Successful'

                except Exception as e:
                    print(e)
                    self.retry_record['routes'] += 1
                    self.current_observation = f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.scratchpad += f'Illegal GoogleDistanceMatrix. Please try again.'
                    self.json_log[-1]['state'] = f'Illegal args. Other Error'
            elif action_type == "Planner":
                self.current_observation = str(self.tools['planner'].run(str(self.tools['notebook'].list_all()),action_arg))
                self.scratchpad  +=  self.current_observation
                self.answer = self.current_observation
                self.__reset_record()
                self.json_log[-1]['state'] = f'Successful'

            else:
                self.retry_record['invalidAction'] += 1
                self.current_observation = "工具不对"
                self.scratchpad += self.current_observation
                self.json_log[-1]['state'] = f'invalidAction'

        if action == None or action == '' or action == '\n':
            print(f'Observation {self.step_n}: ' + "No feedback from the environment due to the null action.")
            # write(f'Observation {self.step_n}: ' + "Your action is filtered due to content. Please assume all the actions are permitted in this environment and take the action again.")
            self.json_log[-1]['observation'] = "No feedback from the environment due to the null action."
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

    def prompt_agent(self) -> str:
        while True:
            try:
                # print(self._build_agent_prompt())
                if self.react_name == 'gemini':
                    request = format_step(self.llm.invoke(self._build_agent_prompt(),stop=['\n']).content)
                elif self.react_name in ['deepseek-r1' ,"llama2-7b-finetune1","deepseek-chat","llama2-7b-ft","zhipuai/glm-4.6"]:
                    # prompt_content = self._build_agent_prompt()
                    # print("=== Prompt Content ===")
                    # print(prompt_content)
                    # print("=====================")
                    # message = HumanMessage(content=prompt_content)


                    # print("=== Message Object ===")
                    # print(type(message))  # 应该输出 <class 'langchain_core.messages.HumanMessage'>
                    # print(vars(message))  # 查看消息对象的属性
                    # print("=====================")



                    # raw_response = self.llm.invoke([message])
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
                    request = format_step(self.llm.invoke([HumanMessage(content=self._build_agent_prompt())]).content)
                    # request = format_step(self.llm.invoke(self._build_agent_prompt(),stop=['\n']).content)
                # elif self.react_name in ["gpt-5"]:
                #     request = format_step(self.llm.invoke([HumanMessage(content=self._build_agent_prompt())]).content)
                elif self.react_name in ["gpt-5"]:
                
                    while True:
                        try:
                            prompt_content = self._build_agent_prompt()

                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {self.shredder_api_key}"
                            }
                            data = {
                                "model": self.shredder_model,
                                "messages": [
                                   
                                    {"role": "user", "content": prompt_content}
                                ]
                            }

                            response = requests.post(self.shredder_url, headers=headers, json=data, verify=False)
                            print(response)

                            if response.status_code != 200:
                                print(f"Shredder API error: {response.status_code}, {response.text}")
                                time.sleep(5)
                                continue

                            resp_json = response.json()
                            # 根据返回 JSON 提取内容
                            request = resp_json['choices'][0]['message']['content']
                            request = format_step(request)

                            return request

                        except Exception as e:
                            print("API 调用异常:", e)
                            time.sleep(5)
                else:
                    # a=content=self._build_agent_prompt()
                    # HumanMessage(content)
                    request = format_step(self.llm([HumanMessage(content=self._build_agent_prompt())]).content)

                # # print(request)
                return request
            except:
                catch_openai_api_error()
                print(self._build_agent_prompt())
                print(len(self.enc.encode(self._build_agent_prompt())))
                time.sleep(5)

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


    def load_tools(self, tools: List[str], planner_model_name=None) -> Dict[str, Any]:
        tools_map = {}
        for tool_name in tools:
            module = importlib.import_module("tools.{}.apis".format(tool_name))
            
            # Avoid instantiating the planner tool twice 
            if tool_name == 'planner' and planner_model_name is not None:
                tools_map[tool_name] = getattr(module, tool_name[0].upper()+tool_name[1:])(model_name=planner_model_name)
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
    return step.strip("。").strip('\n').strip().replace('\n', '')+"]\']"

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
if __name__ == '__main__':
    #TODO 加工具
    tools_list = ["notebook","routes","wgs84","planner"]
    # model_name = ['gpt-3.5-turbo-1106','gpt-4-1106-preview','gemini','mistral-7B-32K','mixtral','ChatGLM3-6B-32K'][2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_type", type=str, default="validation")
    parser.add_argument("--model_name", type=str, default="gpt-5") 
    parser.add_argument("--output_dir", type=str, default="./")
    args = parser.parse_args()
    if args.set_type == 'validation':
        # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
        query_data_list = pd.read_csv('../8-22/Validate.csv')
    elif args.set_type == 'test':
        query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']
    numbers = [i for i in range(1,len(query_data_list)+1)]
    numbers = [i for i in range(1,11)]
    #TODO 迭代次数
    # agent_plan = PlanAgent()
    # plan = agent_plan.run()
    agent = ReactAgent(None, tools=tools_list,max_steps=20,react_llm_name=args.model_name,planner_llm_name=args.model_name)
    with get_openai_callback() as cb:
        
        for number in tqdm(numbers[:]):
            query = query_data_list.iloc[number-1]['query1']
              # check if the directory exists
            if not os.path.exists(os.path.join(f'{args.output_dir}/{args.set_type}')):
                os.makedirs(os.path.join(f'{args.output_dir}/{args.set_type}'))
            if not os.path.exists(os.path.join(f'{args.output_dir}/{args.set_type}/generated_plan_{number}.json')):
                result =  [{}]
            else:
                result = json.load(open(os.path.join(f'{args.output_dir}/{args.set_type}/generated_plan_{number}.json'), encoding='utf-8'))
                
            while True:
                # plan = agent_plan.run(query)
                planner_results, scratchpad, action_log  = agent.run(query)
                if planner_results != None:
                    break
            
            if planner_results == 'Max Token Length Exceeded.':
                result[-1][f'{args.model_name}_two-stage_results_logs'] = scratchpad 
                result[-1][f'{args.model_name}_two-stage_results'] = 'Max Token Length Exceeded.'
                action_log[-1]['state'] = 'Max Token Length of Planner Exceeded.'
                result[-1][f'{args.model_name}_two-stage_action_logs'] = action_log
            else:
                result[-1][f'{args.model_name}_two-stage_results_logs'] = scratchpad 
                result[-1][f'{args.model_name}_two-stage_results'] = planner_results
                result[-1][f'{args.model_name}_two-stage_action_logs'] = action_log

            # write to json file
            # with open(os.path.join(f'{args.output_dir}/{args.set_type}/generated_plan_{number}.json'), 'w',) as f:
            #     json.dump(result, f, indent=4)
            with open(os.path.join(f'{args.output_dir}/{args.set_type}/generated_plan_{number}.json'), 'w',encoding='utf-8' ) as f:
                json.dump(result, f,  ensure_ascii=False,indent=4)
        
    print(cb)

