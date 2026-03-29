import argparse
import os
import json
from tqdm import tqdm
import pandas as pd


# ---------------------------
# 从 text 中抽取 json 代码块
# ---------------------------
def extract_json_block(text):
    if "```json" not in text:
        return None
    try:
        return text.split("```json")[1].split("```")[0].strip()
    except:
        return None


# ---------------------------
# 处理单个配置（核心逻辑）
# ---------------------------
def process_single_config(query_type, model_name, strategy, set_type,output_dir, input_json_dir, output_json_dir):
    """
    自动处理一个 set_type + model_name + strategy
    """

    # TXT 输入
    txt_file = f"{output_dir}/{query_type}_{model_name}_{strategy}_{set_type}.txt"
    print(f"\n🟦 正在处理：{txt_file}")

    if not os.path.exists(txt_file):
        print(f"❌ 未找到 TXT：{txt_file}")
        return

    results = open(txt_file, "r", encoding="utf-8").read().strip().split("\n")

    # CSV 用来确定共有多少条 query
    csv_data = pd.read_csv("./test-V1/train.csv")
    total = len(csv_data)

    key_name = f"{query_type}_{model_name}_{strategy}_{set_type}_parsed_results"

    # 遍历每个 generated_plan
    for idx in tqdm(range(1, total + 1)):

        # JSON 输入路径（你指定的）
        plan_json_path = f"{input_json_dir}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json"

        if not os.path.exists(plan_json_path):
            print(f"⚠ JSON 输入不存在：{plan_json_path}")
            continue

        # 读取 JSON
        data = json.load(open(plan_json_path, "r", encoding="utf-8"))

        model_output = results[idx - 1].strip()

        # 提取 JSON block
        json_block = extract_json_block(model_output)

        if json_block is None or json_block == "" or "Max Token Length Exceeded" in json_block:
            data[-1][key_name] = None
        else:
            try:
                parsed = eval(json_block)
                data[-1][key_name] = parsed
            except Exception as e:
                print(f"❌ JSON 解析失败 idx={idx}: {e}")
                data[-1][key_name] = None

        # JSON 输出路径（你指定的）
        save_path = f"{output_json_dir}/{query_type}/{strategy}/{model_name}/generated_plan_{idx}.json"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))




# ======================================================
# 主入口（自动循环所有 set_type / model / strategy）
# ======================================================
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, default="./output_V1")                # TXT 所在目录
    parser.add_argument("--input_json_dir", type=str, default="./output_Result_V1")         # 输入 JSON 目录
    parser.add_argument("--output_json_dir", type=str, default="./output_Result_combination_V1")  # 输出 JSON 目录
    args = parser.parse_args()

    # ------------------ 配置列表 -----------------------

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

    # ------------------ 全自动循环 ---------------------

    for query_type in query_type_list:
        for model_name in model_list:
            for strategy in strategy_list:
                 for set_type in set_type_list:
                    process_single_config(
                        query_type=query_type,
                        model_name=model_name,
                        strategy=strategy,
                        set_type=set_type,
                        output_dir=args.output_dir,
                        input_json_dir=args.input_json_dir,
                        output_json_dir=args.output_json_dir
                    )
