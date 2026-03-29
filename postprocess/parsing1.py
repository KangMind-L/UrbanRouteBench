from tqdm import tqdm
import argparse
from openai_request import build_plan_format_conversion_prompt, prompt_chatgpt
import os

# if __name__ == '__main__':

#     parser = argparse.ArgumentParser()

#     parser.add_argument("--tmp_dir", type=str, default="./output_Result")
#     parser.add_argument("--set_type", type=str, default="train")
#     parser.add_argument("--output_dir", type=str, default="./output_12-20")
#     args = parser.parse_args()

#     # 需要遍历的 set_type
#     query_type_list = [
#         "args", 
#         # "query"
#         ]

#     # 4 个模型
#     model_list = [
#         # "llama3.1:8b",
#         # "gpt-5",
#         'qwen3-max'
#         # "deepseek-ai/DeepSeek-V3.2",
#         # "Qwen/Qwen3-Coder-480B-A35B-Instruct"
#     ]



#     # 策略（只影响输出名）
#     strategy_list = [
#         "ReAct",
#         # "direct",
#         # "cot"
#     ]

#     total_price_global = 0
#     os.makedirs(args.tmp_dir, exist_ok=True)

#     for query_type in query_type_list:  # ★★★ 自动遍历 args & query

#         for model_name in model_list:
#             # safe_model_name = model_name.split("/")[-1]

#             for strategy in strategy_list:
#                 for strategy in strategy_list:

#                     print(f"\n===== 处理 {query_type} | {model_name} | {strategy} | {args.set_type} |=====")

#                     # 构建 prompt 数据
#                     data = build_plan_format_conversion_prompt(
#                         directory=args.tmp_dir,
#                         query_type = query_type,
#                         set_type=args.set_type,
#                         strategy=strategy,
#                         model_name=model_name,
   
                       
#                     )

#                     # 输出文件名
#                     output_file = f"{args.output_dir}/{query_type}_{model_name}_{strategy}_{args.set_type}.txt"

#                     total_price = 0

#                     for idx, prompt in enumerate(tqdm(data)):

#                         # 如果为空直接写索引
#                         if prompt == "":
#                             with open(output_file, 'a+', encoding='utf-8') as f:
#                                 f.write(str(idx) + '\n')
#                             continue

#                         # 调用 deepseek-chat
#                         results, _, price = prompt_chatgpt(
#                             "你是一个乐于助人的助手.",
#                             index=idx,
#                             save_path=output_file,
#                             user_input=prompt,
#                             model_name='qwen-max',
#                             temperature=0
#                         )

#                         total_price += price

#                     print(f"当前任务花费: ${total_price}")
#                     total_price_global += total_price

#     print(f"\n===== 所有任务完成，总 Token 花费: ${total_price_global} =====")


import os
import argparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ========================
# 单个任务函数
# ========================
def run_one_task(query_type, model_name, strategy, args):
    print(f"\n===== 处理 {query_type} | {model_name} | {strategy} | {args.set_type} |=====")

    data,args_list = build_plan_format_conversion_prompt(
        directory=args.tmp_dir,
        query_type=query_type,
        set_type=args.set_type,
        strategy=strategy,
        model_name=model_name,
    )

    output_file = f"{args.output_dir}/{query_type}_{model_name}_{strategy}_{args.set_type}.txt"
    total_price = 0

    for idx, (prompt, arg) in enumerate(tqdm(zip(data, args_list), desc=f"{query_type}-{strategy}")):
        if prompt == "":
            with open(output_file, 'a+', encoding='utf-8') as f:
                arg_str  = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束条件', {})})
                f.write(str(idx) + '```json	['+arg_str+']	```\n')
            continue
        # assistant_output = str(index)+"\t"+"\t".join(arg).join(x for x in assistant_output.split("\n"))
        _, _, price = prompt_chatgpt(
            "你是一个乐于助人的助手.",
            index=idx,
            save_path=output_file,
            user_input=prompt,
            # model_name='qwen3-max',
            model_name="qwen3-max",
            temperature=0,
            arg = arg,

        )
        #                         results, _, price = prompt_chatgpt(
#                             "你是一个乐于助人的助手.",
#                             index=idx,
#                             save_path=output_file,
#                             user_input=prompt,
#                             model_name='qwen-max',
#                             temperature=0
#                         )
        total_price += price

    print(f"任务完成 {query_type} | {model_name} | {strategy}，花费 ${total_price}")
    return total_price


# ========================
# 主程序
# ========================
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp_dir", type=str, default="./output_Result_V1")
    parser.add_argument("--set_type", type=str, default="train")
    parser.add_argument("--output_dir", type=str, default="./output_V1")
    parser.add_argument("--num_threads", type=int, default=1)
    args = parser.parse_args()

    os.makedirs(args.tmp_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    query_type_list = [
        "query",
        "args"
        ]
    model_list = [
        # "deepseek-v3.2",
        # "llama3.1:8b",
        # "qwen3-max"
        # "glm-4.6"
        # "gpt-5",
        "gemini-2.5-pro"
        ]
    strategy_list = ["ReAct"]

    total_price_global = 0
    price_lock = Lock()

    tasks = []
    with ThreadPoolExecutor(max_workers=args.num_threads) as executor:
        for query_type in query_type_list:
            for model_name in model_list:
                for strategy in strategy_list:
                    tasks.append(
                        executor.submit(
                            run_one_task,
                            query_type,
                            model_name,
                            strategy,
                            args
                        )
                    )

        for future in as_completed(tasks):
            price = future.result()
            with price_lock:
                total_price_global += price

    print(f"\n===== 所有任务完成，总 Token 花费: ${total_price_global} =====")
