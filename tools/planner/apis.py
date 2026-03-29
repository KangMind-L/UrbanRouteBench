import random
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from langchain.prompts import PromptTemplate
from agents.prompts import cot_planner_agent_prompt, planner_agent_prompt, react_planner_agent_prompt, react_reflect_planner_agent_prompt,reflect_prompt,REFLECTION_HEADER
from langchain.chat_models import ChatOpenAI
from langchain.llms.base import BaseLLM
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

import tiktoken
import re
import openai
import time
from enum import Enum
from typing import List, Union, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
import argparse
from .env import ReactEnv, ReactReflectEnv
SHREDDER_API_KEY = "2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2"
SHREDDER_URL = "https://api.shredder.money/v1"
# deepseekApiKey:sk-9301e16490e343a2b2c5864ce162b31a
# openaiApiKey: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
# OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
# GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']
OPENAI_API_KEY = "0"
GOOGLE_API_KEY = "0"
DEEPSEEK_API_KEY = "sk-9a737cbf09a84c78bcb8403b5c374e66"

def catch_openai_api_error():
    print("查询失败，等待重试")


class ReflexionStrategy(Enum):
    """
    REFLEXION: Apply reflexion to the next reasoning trace 
    """
    REFLEXION = 'reflexion'


class Planner:
    def __init__(self,
                 # args,
                 agent_prompt: PromptTemplate = planner_agent_prompt,
                 model_name: str = 'deepseek-chat',
                 SHREDDER_API_KEY:str ="",
                 strategy = "direct"
                 ) -> None:
        if strategy == "direct":
            self.agent_prompt = planner_agent_prompt
        elif strategy == "cot":
            self.agent_prompt = cot_planner_agent_prompt


        self.scratchpad: str = ''
        self.model_name = model_name
        self.SHREDDER_API_KEY =SHREDDER_API_KEY 
        
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # if model_name in  ['mistral-7B-32K']:
        #     self.llm = ChatOpenAI(temperature=0,
        #              max_tokens=4096,
        #              openai_api_key="EMPTY", 
        #              openai_api_base="http://localhost:8301/v1", 
        #              model_name="gpt-3.5-turbo")
        

        # self.llm = ChatOpenAI(temperature=1,
        #             max_tokens=256,
        #             model_name=react_llm_name,
        #             openai_api_key=SHREDDER_API_KEY,
        #             base_url=SHREDDER_URL, 
        #         #  model_kwargs={"stop": stop_list}
        #             )

        # if  model_name in ["qwen3-max","gpt-5.2","gpt-5.1",'gpt-5','deepseek-v3.2' ,'deepseek-v3.2-exp','deepseek-r1','gemini-2.5-pro','deepseek-v3',"qwen3-coder-480b-a35b-instruct"]:

            # stop_list = ['\n']  
        if model_name in ['llama3.1:8b',"llama3:70b"]:
            stop_list = ['\n']

            self.max_token_length = 30000  # DeepSeek模型的最大token长度 
            self.llm = ChatOpenAI(
                temperature=0.7,
                max_tokens=2048,
                openai_api_key="ollama",  
                base_url="http://localhost:11434/v1",
                model_name=model_name,
                # model_kwargs={"stop": stop_list}
            )
        else:
            self.max_token_length = 30000
            self.llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
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
            

        print(f"PlannerAgent {model_name} loaded.")

    def run(self, text, query, log_file=None,api_max_retries=5, base_delay=4, max_delay=1800) -> str:
        retry = 0

        while True:
            try:
                if log_file:
                    log_file.write('\n---------------Planner\n'+self._build_agent_prompt(text, query))
                request = self.llm.invoke(self._build_agent_prompt(text, query)).content
                return request
            except:
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

    def _build_agent_prompt(self, text, query) -> str:

        return self.agent_prompt.format(
            text=text,
            query=query)

class ReactPlanner:
    """
    A question answering ReAct Agent.
    """
    def __init__(self,
                 agent_prompt: PromptTemplate = react_planner_agent_prompt,
                 model_name: str = 'deepseek-chat',
                 SHREDDER_API_KEY:str ="",
                 strategy:str = "react",
                 ) -> None:
        self.SHREDDER_API_KEY =SHREDDER_API_KEY 
        self.agent_prompt = agent_prompt
        stop_list = ["Action","Thought","Observation"]
        self.max_token_length = 30000  # DeepSeek模型的最大token长度
        if model_name in ['llama3.1:8b',"llama3:70b"]:
            stop_list = ['\n']

            self.max_token_length = 30000  # DeepSeek模型的最大token长度 
            self.react_llm = ChatOpenAI(
                temperature=0.7,
                max_tokens=2048,
                openai_api_key="ollama",  
                base_url="http://localhost:11434/v1",
                model_name=model_name,
                # model_kwargs={"stop": stop_list}
            )
        else:
            self.max_token_length = 30000
            self.react_llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
            # 使用DeepSeek API配置
        # self.react_llm = ChatOpenAI(temperature=0.7,  # 可以调整temperature
        #             max_tokens=9192,
        #             model_name=model_name,
        #             openai_api_key='sk-9a737cbf09a84c78bcb8403b5c374e66',  # 使用DeepSeek的API Key
        #             base_url="https://api.deepseek.com/v1",  # 指定DeepSeek的API端点
        #             model_kwargs={"stop": stop_list}) 
        # self.react_llm = ChatOpenAI(model_name=model_name, temperature=0, max_tokens=1024, openai_api_key=OPENAI_API_KEY,model_kwargs={"stop": ["Action","Thought","Observation"]})
        self.env = ReactEnv()
        self.query = None
        self.max_steps = 30
        self.reset()
        self.finished = False
        self.answer = ''
        self.step_results =[]
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        print(f"ReactPlannerAgent {model_name} loaded.")
    def run(self, text, query, reset = True) -> None:

        self.query = query
        self.text = text

        if reset:
            self.reset()
        

        while not (self.is_halted() or self.is_finished()):
            self.step()
        
        return self.answer
        #  self.scratchpad

    
    def step(self) -> None:

        def extract_tool_call(text: str):
    # 匹配工具调用：工具名 + [内容直到]
            pattern = r'\b(LogicalJudgment|PlanSummary|Finish)\s*\[[^\]]*\]'
            
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

        # Think
        self.scratchpad += f'\nThought {self.curr_step}:'
        # self.scratchpad += ' ' + self.prompt_agent()
        thought=self.prompt_agent()
        self.scratchpad += ' ' + clean_agent_output(thought)
        print(self.scratchpad.split('\n')[-1])

        # Act
        self.scratchpad += f'\nAction {self.curr_step}:'
        action = extract_tool_call(self.prompt_agent())
        self.scratchpad += ' ' + action
        print(self.scratchpad.split('\n')[-1])

        # Observe
        self.scratchpad += f'\nObservation {self.curr_step}: '

        action_type, action_arg = parse_action(action)

        if action_type == 'LogicalJudgment':
            try:
                input_arg = eval(action_arg)
                if type(input_arg) != dict:
                    raise ValueError('子计划无法解析为json格式，请检查，只支持一段行程的计划')
                observation = self.env.LogicalJudgment(input_arg)
                if observation == "这一段逻辑没有问题，可以采用" and input_arg:
                    # 判断当前行程是否已经存在（根据起点和终点）
                    exists = any(
                        step.get("行程", {}).get("起点") == input_arg.get("行程", {}).get("起点") and
                        step.get("行程", {}).get("终点") == input_arg.get("行程", {}).get("终点")
                        for step in self.step_results
                    )
                    if not exists:
                        self.step_results.append(input_arg)

            except SyntaxError:
                observation = f'子计划无法解析为json格式，请检查，只支持一段行程的计划'
            except ValueError as e:
                observation = str(e)
        elif action_type == 'PlanSummary':
            try:
                input_arg = eval(action_arg)
                if type(input_arg) != dict:
                    raise ValueError('计划总结无法解析为json格式，请检查')
                observation = self.env.PlanSummary(self.step_results,input_arg)
            except SyntaxError:
                observation = f'计划总结无法解析为json格式，请检查'
            except ValueError as e:
                observation = str(e)
        elif action_type == 'Finish':
            self.finished = True
            observation = f'出行计划已完成'
            self.answer = action_arg
        
        else:
            observation = f'Action {action_type} 不支持.'
        
        self.curr_step += 1

        self.scratchpad += observation
        print(self.scratchpad.split('\n')[-1])

    def prompt_agent(self,api_max_retries=5, base_delay=4, max_delay=1800) -> str:
        retry = 0

        while True:
            try:
                # prompt = self._build_agent_prompt()
                # print("ReActPlanner提示词", prompt)  # 检查提示词是否正常

                # b = [HumanMessage(prompt)]
                # response = self.react_llm(b)        # 打印完整响应对象
                # print("API响应:", response)

                # c = response.content
                # print("最终结果:", c)         # 检查最终结果

                return format_step(self.react_llm.invoke(self._build_agent_prompt()).content)
                # return format_step(self.react_llm([HumanMessage(content=self._build_agent_prompt())]).content)
            except:
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
    
    def _build_agent_prompt(self) -> str:
        return self.agent_prompt.format(
                            query = self.query,
                            text = self.text,
                            scratchpad = self.scratchpad)
    
    def is_finished(self) -> bool:
        return self.finished

    def is_halted(self) -> bool:
        return ((self.curr_step > self.max_steps) or (
                    len(self.enc.encode(self._build_agent_prompt())) > 14000)) and not self.finished

    def reset(self) -> None:
        self.scratchpad = ''
        self.answer = ''
        self.curr_step = 1
        self.finished = False


class ReactReflectPlanner:
    """
    A question answering Self-Reflecting React Agent.
    """
    def __init__(self,
                 agent_prompt: PromptTemplate = react_reflect_planner_agent_prompt,
                 reflect_prompt: PromptTemplate = reflect_prompt,
                 SHREDDER_API_KEY:str ="",
                 model_name: str = 'deepseek-chat',
                 strategy:str = "reflect",
                 ) -> None:
        self.SHREDDER_API_KEY =SHREDDER_API_KEY 
        self.agent_prompt = agent_prompt
        self.reflect_prompt = reflect_prompt
        if model_name in ['llama3.1:8b',"llama3:70b"]:
            stop_list = ['\n']

            self.max_token_length = 30000  # DeepSeek模型的最大token长度 
            self.react_llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
            self.reflect_llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
        else:
            self.max_token_length = 30000
            self.react_llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
            self.reflect_llm = ChatOpenAI(temperature=1,
                        max_tokens=2048,
                        model_name=model_name,
                        openai_api_key = self.SHREDDER_API_KEY ,
                        base_url=SHREDDER_URL, 
                    #  model_kwargs={"stop": stop_list}
                        )
     
        # else:
        #     self.react_llm = ChatOpenAI(model_name=model_name, temperature=0, max_tokens=1024, openai_api_key=OPENAI_API_KEY,model_kwargs={"stop": ["Action","Thought","Observation,'\n"]})
        #     self.reflect_llm = ChatOpenAI(model_name=model_name, temperature=0, max_tokens=1024, openai_api_key=OPENAI_API_KEY,model_kwargs={"stop": ["Action","Thought","Observation,'\n"]})
        self.model_name = model_name
        self.env = ReactReflectEnv()
        self.query = None
        self.max_steps = 30
        self.reset()
        self.finished = False
        self.answer = ''
        self.reflections: List[str] = []
        self.step_results =[]
        self.reflections_str: str = ''
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        print(f"ReactReflectPlanner {model_name} loaded.")

    def run(self, text, query, reset = True) -> None:

        self.query = query
        self.text = text

        if reset:
            self.reset()
        

        while not (self.is_halted() or self.is_finished()):
            self.step()
            if self.env.is_terminated and not self.finished:
                self.reflect(ReflexionStrategy.REFLEXION)

        
        return self.answer

    
    def step(self) -> None:

        def extract_tool_call(text: str):
    # 匹配工具调用：工具名 + [内容直到]
            pattern = r'\b(LogicalJudgment|PlanSummary|Finish)\s*\[[^\]]*\]'
            
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

        # Think
        self.scratchpad += f'\nThought {self.curr_step}:'
        # self.scratchpad += ' ' + self.prompt_agent()
        thought=self.prompt_agent()
        self.scratchpad += ' ' + clean_agent_output(thought)
        print(self.scratchpad.split('\n')[-1])

        # Act
        self.scratchpad += f'\nAction {self.curr_step}:'
        action = extract_tool_call(self.prompt_agent())
        self.scratchpad += ' ' + action
        print(self.scratchpad.split('\n')[-1])

        # Observe
        self.scratchpad += f'\nObservation {self.curr_step}: '

        action_type, action_arg = parse_action(action)

        if action_type == 'LogicalJudgment':
            try:
                input_arg = eval(action_arg)
                if type(input_arg) != dict:
                    raise ValueError('子计划无法解析为json格式，请检查，只支持一段行程的计划')
                observation = self.env.LogicalJudgment(input_arg)
                if observation == "这一段逻辑没有问题，可以采用" and input_arg:
                    # 判断当前行程是否已经存在（根据起点和终点）
                    exists = any(
                        step.get("行程", {}).get("起点") == input_arg.get("行程", {}).get("起点") and
                        step.get("行程", {}).get("终点") == input_arg.get("行程", {}).get("终点")
                        for step in self.step_results
                    )
                    if not exists:
                        self.step_results.append(input_arg)

            except SyntaxError:
                observation = f'子计划无法解析为json格式，请检查，只支持一段行程的计划'
            except ValueError as e:
                observation = str(e)
        elif action_type == 'PlanSummary':
            try:
                input_arg = eval(action_arg)
                if type(input_arg) != dict:
                    raise ValueError('计划总结无法解析为json格式，请检查')
                observation = self.env.PlanSummary(self.step_results,input_arg)
            except SyntaxError:
                observation = f'计划总结无法解析为json格式，请检查'
            except ValueError as e:
                observation = str(e)
        elif action_type == 'Finish':
            self.finished = True
            observation = f'出行计划已完成'
            self.answer = action_arg
        
        else:
            observation = f'Action {action_type} 不支持.'
        
        self.curr_step += 1

        self.scratchpad += observation
        print(self.scratchpad.split('\n')[-1])

    def reflect(self, strategy: ReflexionStrategy) -> None:
        print('Reflecting...')
        if strategy == ReflexionStrategy.REFLEXION: 
            self.reflections += [self.prompt_reflection()]
            self.reflections_str = format_reflections(self.reflections)
        else:
            raise NotImplementedError(f'Unknown reflection strategy: {strategy}')
        print(self.reflections_str)

    def prompt_agent(self,api_max_retries=5, base_delay=4, max_delay=1800) -> str:
        retry = 0

        while True:
            try:
                if self.model_name in ['gemini']:
                    return format_step(self.react_llm.invoke(self._build_agent_prompt()).content)
                else:
                    return format_step(self.react_llm([HumanMessage(content=self._build_agent_prompt())]).content)
            except:
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
    
    def prompt_reflection(self) -> str:
        while True:
            try:
                if self.model_name in ['gemini']:
                    return format_step(self.reflect_llm.invoke(self._build_reflection_prompt()).content)
                else:
                    return format_step(self.reflect_llm([HumanMessage(content=self._build_reflection_prompt())]).content)
            except:
                catch_openai_api_error()
                print(self._build_reflection_prompt())
                print(len(self.enc.encode(self._build_reflection_prompt())))
                time.sleep(5)
    
    def _build_agent_prompt(self) -> str:
        return self.agent_prompt.format(
                            query = self.query,
                            text = self.text,
                            scratchpad = self.scratchpad,
                            reflections = self.reflections_str)
    
    def _build_reflection_prompt(self) -> str:
        return self.reflect_prompt.format(
                            query = self.query,
                            text = self.text,
                            scratchpad = self.scratchpad)
    
    def is_finished(self) -> bool:
        return self.finished

    def is_halted(self) -> bool:
        return ((self.curr_step > self.max_steps) or (
                    len(self.enc.encode(self._build_agent_prompt())) > 14000)) and not self.finished

    def reset(self) -> None:
        self.scratchpad = ''
        self.answer = ''
        self.curr_step = 1
        self.finished = False
        self.reflections = []
        self.reflections_str = ''
        self.env.reset()

def format_step(step: str) -> str:
    return step.strip('\n').strip().replace('\n', '')

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

def format_reflections(reflections: List[str],
                        header: str = REFLECTION_HEADER) -> str:
    if reflections == []:
        return ''
    else:
        return header + 'Reflections:\n- ' + '\n- '.join([r.strip() for r in reflections])

# if __name__ == '__main__':
    
# if __name__ == '__main__':
    