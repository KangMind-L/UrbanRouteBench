import os
import json
from tqdm import tqdm
import pandas as pd


# =====================================
# 你的配置
# =====================================
query_type_list = [
    "args",
        "query"
        ]

model_list = [
    "llama3.1:8b",
    "gpt-5",
    "glm-4.6",
    # "DeepSeek-V3.2",
    "deepseek-v3.2",
    # "Qwen3-Coder-480B-A35B-Instruct"
    "qwen3-max",
    "gemini-2.5-pro",
]

strategy_list = [
    "ReAct",
    # "direct",
    # "cot"
]

set_type_list = [
    "train",
    # "validation",
    # "validation"
]


# =====================================
# 主流程：生成 JSONL
# =====================================
def generate_jsonl_for_one(query_type, model_name, strategy,set_type,
                           json_input_root="./result_50_combination",
                           csv_path="./8-22/test_llm.csv",
                           out_root="./result_50_jsonl"):

    df = pd.read_csv(csv_path)
    total = len(df)
    idx_list = list(range(1, total + 1))

    # 创建输出目录
    os.makedirs(out_root, exist_ok=True)

    save_path = f"{out_root}/{query_type}_{model_name}_{strategy}_{set_type}_submission.jsonl"

    key_name = f"{query_type}_{model_name}_{strategy}_{set_type}_parsed_results"

    with open(save_path, "w", encoding="utf-8") as w:

        for idx in tqdm(idx_list, desc=f"{query_type}-{model_name}-{strategy}"):

            json_path = (
                f"{json_input_root}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json"
            )

            if not os.path.exists(json_path):
                print(f"⚠ 缺少文件：{json_path}")
                continue

            data = json.load(open(json_path, "r", encoding="utf-8"))
            # plan = data[-1].get(key_name, None)

            plan = data[-1].get(key_name, None)

            if plan:
                arguments = plan[-1:]        # 最后一个元素作为 arguments
                plan = plan[:-1] if len(plan) > 1 else []  # 剩下的作为 plan
            else:
                arguments = []
                plan = []




# args_qwen3-max_ReAct_train_parsed_results
            obj = {
                "idx": idx,
                "query": df.iloc[idx - 1]["query"],
                "出行计划": plan,
                "参数":arguments
            }

            w.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"✅ 完成：{save_path}")


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
                        json_input_root="./output_Result_combination_V1",
                        csv_path="./test-V1/train.csv",
                        out_root="./output_Result_combination_jsonl_V1"
                    )

    print("\n🎉 全部生成完毕！")
