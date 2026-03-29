import os
import re
import openai
import math
import sys
import time
from tqdm import tqdm
from typing import Iterable, List, TypeVar
import func_timeout
from func_timeout import func_set_timeout
import json
from datasets import load_dataset
import pandas as pd
# DEEPSEEK_API_URL = "https://api.deepseek.com/v1"
# DEEPSEEK_API_KEY = "sk-3f923be31588465eb1c7642ad3b50241"  # Replace with your actual DeepSeek API key
openai.api_base = "https://api.shredder.money/v1"

T = TypeVar('T')
# KEY_INDEX = 0
# KEY_POOL =  [
#    os.environ['OPENAI_API_KEY']
# ]# your key pool
openai.api_key = "sk-2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2"

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError(" 运行函数时间太长了")

@func_set_timeout(180)
def limited_execution_time(func,model,prompt,temp,max_tokens=2048, default=None,**kwargs):
    try:
        # if 'deepseek-chat' in model or 'gpt-4' in model:


        result = func(
                    model=model,
                    messages=prompt,    
                    temperature=temp
                )
        # else:
        #     result = func(model=model,prompt=prompt,max_tokens=max_tokens,**kwargs)
    except func_timeout.exceptions.FunctionTimedOut:
        return None
    # raise any other exception
    except Exception as e:
        raise e
    return result


def batchify(data: Iterable[T], batch_size: int) -> Iterable[List[T]]:
    # function copied from allenai/real-toxicity-prompts
    assert batch_size > 0
    batch = []
    for item in data:
        # Yield next batch
        if len(batch) == batch_size:
            yield batch
            batch = []
        batch.append(item)

    # Yield last un-filled batch
    if len(batch) != 0:
        yield batch


def openai_unit_price(model_name,token_type="prompt"):
    if 'gpt-4' in model_name:
        if token_type=="prompt":
            unit = 0.03
        elif token_type=="completion":
            unit = 0.06
        else:
            raise ValueError("Unknown type")
    elif 'gpt-3.5-turbo' in model_name:
        unit = 0.002
    elif 'davinci' in model_name:
        unit = 0.02
    elif 'curie' in model_name:
        unit = 0.002
    elif 'babbage' in model_name:
        unit = 0.0005
    elif 'ada' in model_name:
        unit = 0.0004
    else:
        unit = -1
    return unit


def calc_cost_w_tokens(total_tokens: int, model_name: str):
    unit = openai_unit_price(model_name,token_type="completion")
    return round(unit * total_tokens / 1000, 4)


def calc_cost_w_prompt(total_tokens: int, model_name: str):
    # 750 words == 1000 tokens
    unit = openai_unit_price(model_name)
    return round(unit * total_tokens / 1000, 4)


def get_perplexity(logprobs):
    assert len(logprobs) > 0, logprobs
    return math.exp(-sum(logprobs)/len(logprobs))


def keep_logprobs_before_eos(tokens, logprobs):
    keep_tokens = []
    keep_logprobs = []
    start_flag = False
    for tok, lp in zip(tokens, logprobs):
        if start_flag:
            if tok == "<|endoftext|>":
                break
            else:
                keep_tokens.append(tok)
                keep_logprobs.append(lp)
        else:
            if tok != '\n':
                start_flag = True
                if tok != "<|endoftext>":
                    keep_tokens.append(tok)
                    keep_logprobs.append(lp)

    return keep_tokens, keep_logprobs


def catch_openai_api_error(prompt_input: list):
    print("API出错，重试......")


def prompt_gpt3(prompt_input: list, save_path,model_name='text-davinci-003', max_tokens=2048,
                clean=False, batch_size=16, verbose=False, **kwargs):
    # return: output_list, money_cost

    def request_api(prompts: list):
        # prompts: list or str

        total_tokens = 0
        results = []
        for batch in tqdm(batchify(prompt_input, batch_size), total=len(prompt_input) // batch_size):
            batch_response = request_api(batch)
            total_tokens += batch_response['usage']['total_tokens']
            if not clean:
                results += batch_response['choices']
            else:
                results += [choice['text'] for choice in batch_response['choices']]
            with open(save_path,'w+',encoding='utf-8') as f:
                for content in results:
                    content = content.replace("\n"," ")
                    f.write(content+'\n')
        return results, calc_cost_w_tokens(total_tokens, model_name)

import json
import re
def parse_int_safe(value, default=0):
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else default
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            # 先转 float 再转 int，以支持 "3.0"
            f = float(s)
            return int(f) if f.is_integer() else default
        except ValueError:
            return default
    return default

# 使用
def parse_llm_json_safe(text: str) -> dict:
    """
    将 LLM 输出的任意文本，安全解析并重建为稳定 JSON 结构
    """
    # ========= 1. 定义权威模板 =========
    result = {
        "起点": "",
        "途经点数量": "",
        "途经点": None,
        "停留时间": None,
        "终点": "",
        "出发时间": "",
        "时间窗口": "",
        "出行方式": None,
        "约束条件": {
            "出行偏好": None,
            "环境约束": None,
            "个体约束": None,
            "费用": None
        }
    }

    if not text or not text.strip():
        return result

    # ========= 2. 常见 LLM 错误修复 =========
    text = text.strip()
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r'""\s*null', 'null', text)
    text = re.sub(r'"\s*null\s*"', 'null', text)

    # ========= 3. 尝试解析 JSON =========
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict):
            return result
    except Exception:
        return result

    # ========= 4. 字段级安全读取 =========
    def norm(v):
        if v in ("", "null", None):
            return None
        return str(v).strip()

    result["起点"] = str(raw.get("起点", "")).strip()
    result["终点"] = str(raw.get("终点", "")).strip()
    result["停留时间"] = str(raw.get("停留时间", "")).strip()
    result["出发时间"] = str(raw.get("出发时间", "")).strip()
    result["时间窗口"] = str(raw.get("时间窗口", "")).strip()

    # 途经点
    try:
        # print(raw)
        # c= raw.get("途经点数量")
        # a = str(raw.get("途经点数量", "")).strip()
        # print (c)
        # print(a)
        result["途经点数量"] = parse_int_safe((raw.get("途经点数量", "")))
        # print(type(raw.get("途经点数量", 0)))
    except Exception:
        result["途经点数量"] = 0

    result["途经点"] = raw.get("途经点") if result["途经点数量"] != 0 else None

    # 出行方式
    result["出行方式"] = norm(raw.get("出行方式"))

    # ========= 5. 约束条件 =========
    constraint = raw.get("约束条件") or {}

    try:
        cost = float(constraint.get("费用")) if constraint.get("费用") is not None else None
    except Exception:
        cost = None

    result["约束条件"] = {
        "出行偏好": norm(constraint.get("出行偏好")),
        "环境约束": norm(constraint.get("环境约束")),
        "个体约束": norm(constraint.get("个体约束")),
        "费用": cost
    }

    return result


def prompt_chatgpt(system_input, user_input, temperature,index,save_path="",history=[], model_name='gpt-4-1106-preview',arg={}):
    '''
    :param system_input: "你是一个乐于助人的助手"
    :param user_input: 你的文本内容
    :param history: 以助手输出结束.
                    e.g. [{"role": "system", "content": xxx},
                          {"role": "user": "content": xxx},
                          {"role": "assistant", "content": "xxx"}]
    return: assistant_output, (updated) history, money cost
    '''
    if len(history) == 0:
        history = [{"role": "system", "content": system_input}]
    history.append({"role": "user", "content": user_input})
    while True:
        try:
            completion = limited_execution_time(openai.ChatCompletion.create,
                model=model_name,
                prompt=history,
                temp=temperature)
            assistant_output = completion['choices'][0]['message']['content']
            # print(assistant_output)
            if '转换失败' in assistant_output.strip():
    # 模型判断为：非完整出行计划
                assistant_output = ""
                break

            if "```json" not in assistant_output:
                history.append({"role": "assistant", "content": assistant_output})
                history.append({"role": "user", "content": "缺少json符号"})
                continue
            # if completion is None:
            #     raise TimeoutError
            break
        except:
            catch_openai_api_error(user_input)
            time.sleep(1)


    history.append({"role": "assistant", "content": assistant_output})
    total_prompt_tokens = completion['usage']['prompt_tokens']
    total_completion_tokens = completion['usage']['completion_tokens']
    with open(save_path,'a+',encoding='utf-8') as f:
        # assistant_output = str(index+75)+"\t"+"\t".join(x for x in assistant_output.split("\n"))
# .join(arg).
        arg_str  = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束条件', {})})

        
        # assistant_output = str(index) + "\t" + "\t".join(assistant_output.split("\n")).rsplit("```", 1)[0] + "," + arg_str + "```"
        if assistant_output == "":
                arg_str  = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束条件', {})})
                f.write(str(index) + '```json	['+arg_str+']	```\n')
            
        else:
            assistant_output = str(index)+"\t"+"\t".join(x for x in assistant_output.split("\n")).replace("\t]\t```",",")+arg_str+"\t]\t```"
            f.write(assistant_output+'\n')

        
    return assistant_output, history, calc_cost_w_tokens(total_prompt_tokens, model_name) + calc_cost_w_prompt(total_completion_tokens, model_name)

def build_query_generation_prompt(data):
    prompt_list = []
    prefix = """Given a JSON, please help me generate a natural language query. In the JSON, 'org' denotes the departure city. When 'days' exceeds 3, 'visiting_city_number' specifies the number of cities to be covered in the destination state. Please disregard the 'level' attribute. Here are three examples.

-----EXAMPLE 1-----
JSON:
{"org": "Gulfport", "dest": "Charlotte", "days": 3, "visiting_city_number": 1, "date": ["2022-03-05", "2022-03-06", "2022-03-07"], "people_number": 1, "local_constraint": {"house rule": null, "cuisine": null, "room type": null}, "budget": 1800, "query": null, "level": "easy"}
QUERY:
Please design a travel plan departing Gulfport and heading to Charlotte for 3 days, spanning March 5th to March 7th, 2022, with a budget of $1800.
-----EXAMPLE 2-----
JSON:
{"org": "Omaha", "dest": "Colorado", "days": 5, "visiting_city_number": 2, "date": ["2022-03-14", "2022-03-15", "2022-03-16", "2022-03-17", "2022-03-18"], "people_number": 7, "local_constraint": {"house rule": "pets", "cuisine": null, "room type": null}, "budget": 35300, "query": null, "level": "medium"}
QUERY:
Could you provide a  5-day travel itinerary for a group of 7, starting in Omaha and exploring 2 cities in Colorado between March 14th and March 18th, 2022? Our budget is set at $35,300, and it's essential that our accommodations be pet-friendly since we're bringing our pets.
-----EXAMPLE 3-----
JSON:
{"org": "Indianapolis", "dest": "Georgia", "days": 7, "visiting_city_number": 3, "date": ["2022-03-01", "2022-03-02", "2022-03-03", "2022-03-04", "2022-03-05", "2022-03-06", "2022-03-07"], "people_number": 2, "local_constraint": {"flight time": null, "house rule": null, "cuisine": ["Bakery", "Indian"], "room type": "entire room", "transportation": "self driving"}, "budget": 6200, "query": null, "level": "hard"}
QUERY:
I'm looking for a week-long travel itinerary for 2 individuals. Our journey starts in Indianapolis, and we intend to explore 3 distinct cities in Georgia from March 1st to March 7th, 2022. Our budget is capped at $6,200. For our accommodations, we'd prefer an entire room. We plan to navigate our journey via self-driving. In terms of food, we're enthusiasts of bakery items, and we'd also appreciate indulging in genuine Indian cuisine.

JSON\n"""
    for unit in data:
        unit = str(unit).replace(", 'level': 'easy'",'').replace(", 'level': 'medium'",'').replace(", 'level': 'hard'",'')
        prompt = prefix + str(unit) + "\nQUERY\n"
        prompt_list.append(prompt)
    return prompt_list  

# def build_plan_format_conversion_prompt(directory,  query_type ="query",set_type='validation',model_name='gpt4',strategy='ReAct'):
#     prompt_list = []
#     args_list = []
#     prefix = f"""请帮助我从给定的自然语言文本中提取有效信息，并以JSON格式重建它，如下面的示例所示，每一项应包括['步骤', '起点', '终点', '出行方式', '距离', '预计时间', '开始时间', '结束时间']最后一项包括[ '方案偏好','出发时间','到达时间','换乘次数','总出行时间','预计费用','总步行距离','骑行总距离','总距离'],距离单位用米表示,时间用分钟和秒表示，禁止对数据和名称进行修改。


#     -----示例-----
#       [{{
#         "步骤": 1,
#         "起点": "西丽丽新花园",
#         "终点": "丽新花园公交站",
#         "出行方式": "步行",
#         "距离": "200米",
#         "预计时间": "3分钟",
#         "开始时间": "13:00",
#         "结束时间": "13:03"
#       }},
#       {{
#         "步骤": 2,
#         "起点": "丽新花园公交站",
#         "终点": "翠景园站",
#         "出行方式": "公交",
#         "距离": "4500米",
#         "预计时间": "12分钟",
#         "开始时间": "13:03",
#         "结束时间": "13:15"
#       }},
#       {{
#         "步骤": 3,
#         "起点": "翠景园站",
#         "终点": "旭日小区站",
#         "出行方式": "公交",
#         "距离": "3000米",
#         "预计时间": "10分钟",
#         "开始时间": "13:15",
#         "结束时间": "13:25"
#       }},
#       {{
#         "步骤": 4,
#         "起点": "旭日小区站",
#         "终点": "旭日小区",
#         "出行方式": "步行",
#         "距离": "250米",
#         "预计时间": "4分钟",
#         "开始时间": "13:25",
#         "结束时间": "13:29"
#       }},
#         {{
#         "方案偏好": "无偏好",
#         "出发时间": "13:00",
#         "到达时间": "13:29",
#         "换乘次数": "1次",
#         "总出行时间": "29分钟",
#         "预计费用": "4 元",
#         "总步行距离": "450米",
#         "骑行总距离":"0.0 米",
#         "总距离": "7950米"
#         }}]

        

#     -----示例结束----
    
# """
#     # 请注意,最后的各种参数并不是由上面的步骤推断出，而是已经有的json文本，在结构化参数如下:和出行计划之间,转换时不允许有任何变化。

# # 一系列参数之后存在"出行计划："才能够解析出出行计划和步骤。结构化数据是都存在的。
# #         你的任务是：  
# #             从给定的自然语言文本中，提取并重组【结构化参数】和【出行计划步骤】，并严格输出 JSON。
# #             ⚠️ 关键规则（必须遵守）：
# #             1. 文本中【一定包含结构化参数】，该部分必须原样保留，禁止推断、禁止修改、禁止补充。
# #             2. 只有当原文中 **明确出现字符串“出行计划：”** 时，才允许解析并生成“步骤”。
# #             3. 如果原文 **没有出现“出行计划：”**：
# #             - 不允许生成任何步骤
# #             - “步骤”字段必须是空数组 []
# #             - 不允许根据参数或常识臆造路线
# #             4. 最终输出结构固定为一个 JSON 数组，包含两项：
# #             - 第 1 项：步骤数组（可能为空）
# #             - 第 2 项：结构化参数对象
#         # "结构化参数":{
#         # "起点": "西丽丽新花园",
#         # "途经点数量": 0,
#         # "途经点": null,
#         # "终点": "旭日小区",
#         # "时间": "12:56",
#         # "时间性质": "出发",
#         # "出行方式": "步行+公交",
#         # "出行偏好": "null",
#         # "环境约束": "null",
#         # "个体约束": "null",
#         # "费用": 4.0
#         # }
#     # if set_type == 'train':
#     # if set_type == 'validation':
#     #     query_data_list = pd.read_csv('./12-20/train.csv')
    
#     #     query_data_list  = load_dataset('osunlp/TravelPlanner','train')['train']
#     # elif set_type == 'validation':
#     if set_type == 'train':

#         # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
#         query_data_list = pd.read_csv('./test-V2/train.csv')
#     elif set_type == 'validation':
#         query_data_list = pd.read_csv('./test-V2/val.csv')
#     elif set_type == 'test':
#         query_data_list = pd.read_csv('./test-V2/test.csv')
#         # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
#     # elif set_type == 'test':
#     #     query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']

#     idx_number_list = [i for i in range(1,len(query_data_list)+1)]
#     # idx_number_list = [66]

#     # if strategy == 'two-stage':
#     #     suffix = ''
#     # elif strategy == 'sole-planning':
#     #     suffix = f'_{strategy}'
#     for idx in tqdm(idx_number_list):
#     # for idx in tqdm([8,14,34]):    
#         # 
#         # generated_plan = json.load(open(f'{directory}agents/{set_type}/{model_name}/generated_plan_{idx}.json'))
#         # generated_plan = json.load(open(f'{directory}{set_type}/{model_name}/generated_plan_{idx}.json'))
#         generated_plan = json.load(open(
#     f'{directory}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json'
# ))


#         raw_text = generated_plan[-1][f'{model_name}_{strategy}_results']

#         # 1️⃣ 匹配“结构化参数如下:{...}”
#         # param_match = re.search(r"结构化参数如下:\s*(\{.*?\})", raw_text, re.S)
#         param_match = re.search(r"结构化参数如下:\s*(\{[^}]*\}[^}]*\})", raw_text)
#         if param_match:
#             param_json_str = param_match.group(1)
#             # param_data = json.loads(param_json_str)

#             try:
#                 param_data =parse_llm_json_safe(param_json_str)
#                 args_list.append(param_data);
#             except json.JSONDecodeError:
#                 args_list.append({});
#                 print("⚠️ 结构化参数 JSON 格式错误")
                 
#         else:
#             args_list.append({});
#             print("⚠️ 结构化参数 JSON 格式错误")
#             #  args_list.append({});

#         # 2️⃣ 匹配“出行计划：”及其内容（可选）
#         # plan_match = re.search(r"出行计划：\s*(.*)", raw_text, re.S)
#         plan_match = re.search(r"(出行计划\s*.*)", raw_text, re.S)

#         if plan_match:
#             plan_text = plan_match.group(1).strip()
#         else:
#             plan_text = ""  # 如果没有出行计划，置空字符串

#         # 3️⃣ 输出
#         # print("参数 JSON：", json.dumps(param_data, ensure_ascii=False, indent=2))
#         # print("出行计划文本：", plan_text)

#         generated_plan[-1][f'{model_name}_{strategy}_results']
#         if plan_text and plan_text != "":
#             prompt = prefix + "Text:\n"+plan_text+"\nJSON:\n"
#         else:
#             prompt = ""
#         prompt_list.append(prompt)
#     return prompt_list,args_list

def build_plan_format_conversion_prompt(directory,  query_type ="query",set_type='validation',model_name='gpt4',strategy='ReAct'):
    prompt_list = []
    args_list = []
    prefix = f"""请帮助我从给定的自然语言文本中提取完整的出行计划，并以 JSON 格式重建它。要求如下：

            1输出结构：
            - 如果文本中存在“第二步”，说明有途经点，则输出列表包含 **3 个元素**：
            1. 第一段的步骤列表
            2. 第二段的步骤列表
            3. 总结信息（方案偏好、出发时间、到达时间、换乘次数、总出行时间、预计费用、总步行距离、骑行总距离、总距离）
            - 如果文本中只有“第一步”，则输出列表包含 **2 个元素**：
            1. 步骤列表
            2. 总结信息  

            2步骤解析：
            - 每个步骤独立编号，从 1 开始
            - 字段包含：
            ['步骤', '起点', '终点', '出行方式', '距离', '预计时间', '开始时间', '结束时间']
            - 每段的步骤编号单独从 1 开始
            - 距离单位统一为“米”，时间单位为“分钟+秒”，保持原文格式
            - **禁止修改字段名称和数据值**

            3 总结信息解析：
            - 字段包含：
            ['方案偏好','出发时间','到达时间','换乘次数','总出行时间','预计费用','总步行距离','骑行总距离','总距离']
            - 直接从文本中提取对应信息，不依赖步骤内容

            4 完整性要求：
            - 文本必须包含至少“第一步”和总结信息
            - 如果缺失任一关键部分，则返回字符串："转换失败"

            5 特别说明：
            - 即使每段路径只有一个步骤，也必须单独输出为该段的第 1 步
            - 目的是让每段路径的步骤在 JSON 中独立存在，而不是将多段步骤合并
                -----示例-----
    [
        [
            {{
            "步骤": 1,
            "起点": "鹏城花园二区",
            "终点": "九尾岭隧道口",
            "出行方式": "步行",
            "距离": "790.95 米",
            "预计时间": "11分钟10秒",
            "开始时间": "16:46:12",
            "结束时间": "16:57:22"
            }},
           {{中间省略}},
            {{
            "步骤": 7,
            "起点": "通洲工业园",
            "终点": "李松蓢公交总站",
            "出行方式": "步行",
            "距离": "1243.43 米",
            "预计时间": "17分钟33秒",
            "开始时间": "19:46:58",
            "结束时间": "20:04:31"
            }}
        ],
        [
            {{
            "步骤": 1,
            "起点": "李松蓢公交总站",
            "终点": "公明李松蓢场站",
            "出行方式": "步行",
            "距离": "65.07 米",
            "预计时间": "0分钟57秒",
            "开始时间": "20:46:18",
            "结束时间": "20:47:15"
            }},
            {{
            "步骤": 2,
            "起点": "公明李松蓢场站",
            "终点": "松岗汽车站",
            "出行方式": "公交",
            "距离": "12825.21 米",
            "预计时间": "44分钟30秒",
            "开始时间": "20:47:15",
            "结束时间": "21:31:45"
            }},
             {{中间省略}},
            {{
            "步骤": 7,
            "起点": "宝安客运中心",
            "终点": "佳华新村",
            "出行方式": "步行",
            "距离": "1621.47 米",
            "预计时间": "23分钟2秒",
            "开始时间": "23:40:32",
            "结束时间": "00:03:34"
            }}
        ],
        {{
            "方案偏好": "换乘最少",
            "出发时间": "16:46:12",
            "到达时间": "20:04:31",
            "换乘次数": "2",
            "总出行时间": "198分钟19秒",
            "预计费用": "6.0 元",
            "总步行距离": "3281.35 米",
            "骑行总距离": "0.0 米",
            "总距离": "68676.73 米"
        }}
        ]



    -----示例结束----
    
"""

    #   {{{{
    #     "步骤": 1,
    #     "起点": "西丽丽新花园",
    #     "终点": "丽新花园公交站",
    #     "出行方式": "步行",
    #     "距离": "200米",
    #     "预计时间": "3分钟",
    #     "开始时间": "13:00",
    #     "结束时间": "13:03"
    #   }},
    #   {{
    #     "步骤": 2,
    #     "起点": "丽新花园公交站",
    #     "终点": "翠景园站",
    #     "出行方式": "公交",
    #     "距离": "4500米",
    #     "预计时间": "12分钟",
    #     "开始时间": "13:03",
    #     "结束时间": "13:15"
    #   }},
    #   {{
    #     "步骤": 3,
    #     "起点": "翠景园站",
    #     "终点": "旭日小区站",
    #     "出行方式": "公交",
    #     "距离": "3000米",
    #     "预计时间": "10分钟",
    #     "开始时间": "13:15",
    #     "结束时间": "13:25"
    #   }},
    #   {{
    #     "步骤": 4,
    #     "起点": "旭日小区站",
    #     "终点": "旭日小区",
    #     "出行方式": "步行",
    #     "距离": "250米",
    #     "预计时间": "4分钟",
    #     "开始时间": "13:25",
    #     "结束时间": "13:29"
    #   }}}},
    #   {{{{
    #     "步骤": 1,
    #     "起点": "西丽丽新花园",
    #     "终点": "丽新花园公交站",
    #     "出行方式": "步行",
    #     "距离": "200米",
    #     "预计时间": "3分钟",
    #     "开始时间": "13:00",
    #     "结束时间": "13:03"
    #   }},
    #   {{
    #     "步骤": 2,
    #     "起点": "丽新花园公交站",
    #     "终点": "翠景园站",
    #     "出行方式": "公交",
    #     "距离": "4500米",
    #     "预计时间": "12分钟",
    #     "开始时间": "13:03",
    #     "结束时间": "13:15"
    #   }},
    #   {{
    #     "步骤": 3,
    #     "起点": "翠景园站",
    #     "终点": "旭日小区站",
    #     "出行方式": "公交",
    #     "距离": "3000米",
    #     "预计时间": "10分钟",
    #     "开始时间": "13:15",
    #     "结束时间": "13:25"
    #   }},
    #   {{
    #     "步骤": 4,
    #     "起点": "旭日小区站",
    #     "终点": "旭日小区",
    #     "出行方式": "步行",
    #     "距离": "250米",
    #     "预计时间": "4分钟",
    #     "开始时间": "13:25",
    #     "结束时间": "13:29"
    #   }}}},
    #     {{
    #     "方案偏好": "无偏好",
    #     "出发时间": "13:00",
    #     "到达时间": "13:29",
    #     "换乘次数": "1次",
    #     "总出行时间": "29分钟",
    #     "预计费用": "4 元",
    #     "总步行距离": "450米",
    #     "骑行总距离":"0.0 米",
    #     "总距离": "7950米"
    #     }}]

    if set_type == 'train':

        # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
        query_data_list = pd.read_csv('./test-V4/train.csv')
    elif set_type == 'validation':
        query_data_list = pd.read_csv('./test-V4/val.csv')
    elif set_type == 'test':
        query_data_list = pd.read_csv('./test-V4/test.csv')
        # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
    # elif set_type == 'test':
    #     query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']

    idx_number_list = [i for i in range(1,len(query_data_list)+1)]
    # idx_number_list = [1,21]

    # if strategy == 'two-stage':
    #     suffix = ''
    # elif strategy == 'sole-planning':
    #     suffix = f'_{strategy}'
    for idx in tqdm(idx_number_list):
    # for idx in tqdm([8,14,34]):    
        # 
        # generated_plan = json.load(open(f'{directory}agents/{set_type}/{model_name}/generated_plan_{idx}.json'))
        # generated_plan = json.load(open(f'{directory}{set_type}/{model_name}/generated_plan_{idx}.json'))
        generated_plan = json.load(open(
    f'{directory}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json'
))


        raw_text = generated_plan[-1][f'{model_name}_{strategy}_results']

        # 1️⃣ 匹配“结构化参数如下:{...}”
        # param_match = re.search(r"结构化参数如下:\s*(\{.*?\})", raw_text, re.S)
        param_match = re.search(r"结构化参数如下:\s*(\{[^}]*\}[^}]*\})", raw_text)
        if param_match:
            param_json_str = param_match.group(1)
            # param_data = json.loads(param_json_str)

            try:
                param_data =parse_llm_json_safe(param_json_str)
                args_list.append(param_data);
            except json.JSONDecodeError:
                args_list.append({});
                print("⚠️ 结构化参数 JSON 格式错误")
                 
        else:
            args_list.append({});
            print("⚠️ 结构化参数 JSON 格式错误")
            #  args_list.append({});

        # 2️⃣ 匹配“出行计划：”及其内容（可选）
        # plan_match = re.search(r"出行计划：\s*(.*)", raw_text, re.S)
        plan_match = re.search(r"(出行计划\s*.*)", raw_text, re.S)

        if plan_match:
            plan_text = plan_match.group(1).strip()
        else:
            plan_text = ""  # 如果没有出行计划，置空字符串

        # 3️⃣ 输出
        # print("参数 JSON：", json.dumps(param_data, ensure_ascii=False, indent=2))
        # print("出行计划文本：", plan_text)

        generated_plan[-1][f'{model_name}_{strategy}_results']
        if plan_text and plan_text != "":
            prompt = prefix + "Text:\n"+plan_text+"\nJSON:\n"
        else:
            prompt = ""
        prompt_list.append(prompt)
    return prompt_list,args_list

