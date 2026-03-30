import os
import json
from tqdm import tqdm
import pandas as pd


# =====================================
# 你的配置
# =====================================
query_type_list = [
    "args",
        # "query"
        ]

model_list = [
    # "llama3.1:8b",
    # "gpt-5.2",
    "gpt-5.4",

    # # "glm-4.7",
    # "deepseek-v3.2",
    # # "Qwen3-Coder-480B-A35B-Instruct"
    # "qwen3-max",
    # # "gemini-2.5-pro",
    # "qwen3-32b",
    # "gemini-3-flash" ,
    # "gemini-3-flash-preview"


]

strategy_list = [
    "reflect",
    "react",
    "direct",
    "cot",
    # "not-tool-direct"
]

set_type_list = [
    # "train",
    # "validation",
    "test",
    # "validation"
]


# =====================================
# 主流程：生成 JSONL
# =====================================
# def generate_jsonl_for_one(query_type, model_name, strategy,set_type,
#                            json_input_root="./result_50_combination",
#                            csv_path="./8-22/test_llm.csv",
#                            out_root="./result_50_jsonl"):

#     df = pd.read_csv(csv_path)
#     total = len(df)
#     idx_list = list(range(1, total + 1))

#     # 创建输出目录
#     os.makedirs(out_root, exist_ok=True)

#     save_path = f"{out_root}/{query_type}_{model_name}_{strategy}_{set_type}_submission.jsonl"

#     key_name = f"{query_type}_{model_name}_{strategy}_{set_type}_parsed_results"

#     with open(save_path, "w", encoding="utf-8") as w:

#         for idx in tqdm(idx_list, desc=f"{query_type}-{model_name}-{strategy}"):

#             json_path = (
#                 f"{json_input_root}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json"
#             )

#             if not os.path.exists(json_path):
#                 print(f"⚠ 缺少文件：{json_path}")
#                 continue

#             data = json.load(open(json_path, "r", encoding="utf-8"))
#             # plan = data[-1].get(key_name, None)

#             plan = data[-1].get(key_name, None)

#             if plan:
#                 arguments = plan[-1:]        # 最后一个元素作为 arguments
#                 plan = plan[:-1] if len(plan) > 1 else []  # 剩下的作为 plan
#                 # print(plan[0][0])
#             else:
#                 arguments = []
#                 plan = []




# # args_qwen3-max_ReAct_train_parsed_results
#             obj = {
#                 "idx": idx,
#                 "query": df.iloc[idx - 1]["query"],
#                 "出行计划": plan,
#                 "参数":arguments
#             }

#             w.write(json.dumps(obj, ensure_ascii=False) + "\n")

#     print(f"✅ 完成：{save_path}")
def generate_jsonl_for_one(query_type, model_name, strategy, set_type,
                           json_input_root="./result_50_combination",
                           csv_path="./8-22/test_llm.csv",
                           out_root="./result_50_jsonl"):

    import os, json
    import pandas as pd
    from tqdm import tqdm

    df = pd.read_csv(csv_path)
    total = len(df)
    idx_list = list(range(1, total + 1))

    # 创建输出目录
    os.makedirs(os.path.join(out_root,set_type), exist_ok=True)

    save_path = f"{out_root}/{set_type}/{query_type}_{model_name}_{strategy}_submission.jsonl"
    key_name = f"{query_type}_{model_name}_{strategy}_{set_type}_parsed_results"

    # 构造该 query_type/strategy 目录
    base_dir = os.path.join(json_input_root, set_type, query_type, strategy, model_name)
    if not os.path.exists(base_dir):
        print(f"⚠ 跳过：目录不存在 -> {base_dir}")
        return
    files_in_dir = os.listdir(base_dir)
    if len(files_in_dir) == 0:
        print(f"⚠ 跳过：目录为空 -> {base_dir}")
        return

    has_written = False  # 标记是否有写入内容

    with open(save_path, "w", encoding="utf-8") as w:

        for idx in tqdm(idx_list, desc=f"{query_type}-{model_name}-{strategy}"):

            json_path = os.path.join(base_dir, f"generated_plan_{idx}.json")

            if not os.path.exists(json_path):
                print(f"⚠ 缺少文件：{json_path}")
                continue

            # 读取 JSON 文件
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 解析失败 idx={idx}: {json_path} -> {e}")
                    continue

            plan = data[-1].get(key_name, None)

            if plan:
                arguments = plan[-1:]        # 最后一个元素作为 arguments
                plan = plan[:-1] if len(plan) > 1 else []  # 剩下的作为 plan
            else:
                arguments = []
                plan = []

            obj = {
                "idx": idx,
                "query": df.iloc[idx - 1]["query"],
                "出行计划": plan,
                "参数": arguments
            }

            w.write(json.dumps(obj, ensure_ascii=False) + "\n")
            has_written = True

    if has_written:
        print(f"✅ 完成：{save_path}")
    else:
        # 如果没有写入任何内容，删除空文件
        if os.path.exists(save_path):
            os.remove(save_path)
        print(f"⚠ 跳过保存：没有数据写入 -> {save_path}")


# =====================================
# 自动循环所有组合
# =====================================
if __name__ == '__main__':

    for query_type in query_type_list:
        for model_name in model_list:
            for strategy in strategy_list:
                for set_type in set_type_list:
                    generate_jsonl_for_one(
                        query_type=query_type,
                        model_name=model_name,
                        strategy=strategy,
                        set_type=set_type,
                        json_input_root="./output_Result_combination_V4",
                        csv_path="./test-V4/test.csv",
                        out_root="./output_Result_combination_jsonl_V4"
                    )

    print("\n🎉 全部生成完毕！")
