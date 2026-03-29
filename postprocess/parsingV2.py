from tqdm import tqdm
import argparse
from openai_request import build_plan_format_conversion_prompt, prompt_chatgpt
import os



import os
import argparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ========================
# 单个任务函数
# ========================
def run_one_task(query_type, model_name, strategy, args):
    task_desc = f"{query_type} | {model_name} | {strategy}"
    print(f"\n===== 处理 {args.set_type} | {query_type} | {model_name} | {strategy} |=====")

    data,args_list = build_plan_format_conversion_prompt(
        # directory=args.tmp_dir,
        directory=os.path.join(args.tmp_dir, args.set_type),
        query_type=query_type,
        set_type=args.set_type,
        strategy=strategy,
        model_name=model_name,
    )

    output_file = f"{args.output_dir}/{args.set_type}/{query_type}_{model_name}_{strategy}.txt"
    total_price = 0

#     for idx, (prompt, arg) in enumerate(tqdm(zip(data, args_list), desc=f"{query_type}-{strategy}")):
#         if prompt == "":
#             with open(output_file, 'a+', encoding='utf-8') as f:
#                 arg_str  = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束条件', {})})
#                 f.write(str(idx) + '```json	['+arg_str+']	```\n')
#             continue
#         # assistant_output = str(index)+"\t"+"\t".join(arg).join(x for x in assistant_output.split("\n"))
#         _, _, price = prompt_chatgpt(
#             "你是一个乐于助人的助手.",
#             index=idx,
#             save_path=output_file,
#             user_input=prompt,
#             # model_name='qwen3-max',
#             model_name="qwen3-max",
#             temperature=0,
#             arg = arg,

#         )
#         #                         results, _, price = prompt_chatgpt(
# #                             "你是一个乐于助人的助手.",
# #                             index=idx,
# #                             save_path=output_file,
# #                             user_input=prompt,
# #                             model_name='qwen-max',
# #                             temperature=0
# #                         )
#         total_price += price
    # ✅ 为当前子任务创建独立的 tqdm 进度条
    results = [None] * len(data)
    with tqdm(total=len(data), desc=f"进度 [{task_desc}]", unit="条") as pbar:
        for idx, (prompt, arg) in enumerate(zip(data, args_list)):
            if prompt == "":
                with open(output_file, 'a+', encoding='utf-8') as f:
                    arg_str = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束条件', {})})
                    f.write(str(idx) + '```json\t[' + arg_str + ']\t```\n')
                    # line = str(idx) + '```json\t[' + arg_str + ']\t```\n'
                    # results[idx] = line
            else:
                assistant_output, _, price = prompt_chatgpt(
                    "你是一个乐于助人的助手.",
                    index=idx,
                    save_path=output_file,
                    user_input=prompt,
                    model_name="qwen3-max",
                    temperature=0,
                    arg=arg,
                )
                # results[idx] = assistant_output

            # 更新当前子任务的进度条
            pbar.update(1)
    print(f"任务完成 {query_type} | {model_name} | {strategy}，花费 ${total_price}")
    return total_price


# ========================
# 主程序
# ========================
if __name__ == '__main__':
    global_pbar = None
    pbar_lock = Lock()
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp_dir", type=str, default="./output_Result_V5")
    parser.add_argument("--set_type", type=str, default="test")
    parser.add_argument("--output_dir", type=str, default="./output_V4")
    parser.add_argument("--num_threads_per_task", type=int, default=8, help="每个子任务内部的线程数")
    args = parser.parse_args()

    os.makedirs(args.tmp_dir, exist_ok=True)
    # os.makedirs(path.join(args.output_dir,args.set_type), exist_ok=True)
    import os

    os.makedirs(os.path.join(args.output_dir, args.set_type), exist_ok=True)

    query_type_list = [
        # "query",
        "args"
        ]
    model_list = [
        # "deepseek-v3.2",s
        # "llama3.1:8b",
        # "qwen3-max",
        # # "glm-4.6",
        "gpt-5.4",
        # # "gemini-2.5-pro",
        # "qwen3-32b",
        # "gemini-3-flash" ,
        # "gemini-3-flash-preview"


        ]
    strategy_list = [
        # "direct",
        # "cot",
        # "react",
        "reflect"
        # "not-tool-direct"


        ]

    total_price_global = 0
    price_lock = Lock()

    tasks = []
    with ThreadPoolExecutor(max_workers=args.num_threads_per_task) as executor:
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
# import os
# import argparse
# from tqdm import tqdm
# from concurrent.futures import ThreadPoolExecutor, as_completed

# def process_single_item(idx, prompt, arg, model_name):
#     """处理单条数据，返回 (idx, line, price)"""
#     if prompt == "":
#         arg_str = str({**{k: v for k, v in arg.items() if k != '约束条件'}, **arg.get('约束_condition', {})})
#         line = f"{idx}```json\t[{arg_str}]\t```\n"
#         return idx, line, 0.0
#     else:
#         # 注意：不再传 save_path！只返回生成内容
#         assistant_output, _, price = prompt_chatgpt(
#             "你是一个乐于助人的助手.",
#             index = idx,
#             user_input=prompt,
#             model_name=model_name,
#             temperature=0,
#             arg=arg,
#         )
#         # 假设你希望格式为：idx + 制表符 + 输出内容
#         # line = f"{idx}\t{assistant_output}\n"
#         return idx, assistant_output, price


# def run_one_task(query_type, model_name, strategy, args):
#     task_desc = f"{query_type} | {model_name} | {strategy}"
#     print(f"\n===== 开始处理子任务: {task_desc} | set={args.set_type} =====")

#     data, args_list = build_plan_format_conversion_prompt(
#         directory=args.tmp_dir,
#         query_type=query_type,
#         set_type=args.set_type,
#         strategy=strategy,
#         model_name=model_name,
#     )

#     output_file = f"{args.output_dir}/{query_type}_{model_name}_{strategy}_{args.set_type}.txt"
#     total_price = 0
#     results = [None] * len(data)

#     # ✅ 子任务内部多线程处理
#     with ThreadPoolExecutor(max_workers=args.num_threads_per_task) as executor:
#         futures = []
#         for idx, (prompt, arg) in enumerate(zip(data, args_list)):
#             future = executor.submit(process_single_item, idx, prompt, arg, model_name)
#             futures.append(future)

#         # 使用 tqdm 显示进度
#         with tqdm(total=len(futures), desc=f"并发处理 [{task_desc}]", unit="条") as pbar:
#             for future in as_completed(futures):
#                 idx, line, price = future.result()
#                 results[idx] = line
#                 total_price += price
#                 pbar.update(1)

#     # ✅ 按 idx 顺序写入文件（results 已按索引对齐）
#     with open(output_file, 'w', encoding='utf-8') as f:
#         for line in results:
#             f.write(line)

#     print(f"✅ 子任务完成: {task_desc}，花费 ${total_price:.4f}")
#     return total_price


# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--tmp_dir", type=str, default="./output_Result_V2")
#     parser.add_argument("--set_type", type=str, default="train")
#     parser.add_argument("--output_dir", type=str, default="./output_V2")
#     parser.add_argument("--num_threads_per_task", type=int, default=8, help="每个子任务内部的线程数")
#     args = parser.parse_args()

#     os.makedirs(args.tmp_dir, exist_ok=True)
#     os.makedirs(args.output_dir, exist_ok=True)

#     query_type_list = [
#         # "query",
#         "args"
#         ]
#     model_list = [
#         "deepseek-v3.2",
#         "llama3.1:8b",
#         "qwen3-max",
#         "glm-4.6",
#         # "gpt-5",
#         # "gemini-2.5-pro"
#         "qwen3-32b"
#         ]
#     strategy_list = [
#         # "direct",
#         # "cot",
#         # "ReAct",
#         #"reflect"
#         "not-tool-direct"


#         ]

#     total_price_global = 0

#     # ✅ 子任务之间串行执行（确保资源可控，避免 API 过载）
#     for query_type in query_type_list:
#         for model_name in model_list:
#             for strategy in strategy_list:
#                 price = run_one_task(query_type, model_name, strategy, args)
#                 total_price_global += price

#     print(f"\n===== 所有 {len(query_type_list)*len(model_list)*len(strategy_list)} 个子任务完成，总花费: ${total_price_global:.4f} =====")