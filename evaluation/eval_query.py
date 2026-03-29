import json
import csv
import os
import re
import math
import sys
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
import sys
import os
import re
from typing import Optional, Set
from datetime import datetime


# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（上一级目录）
project_root = os.path.dirname(current_dir)
# 添加到Python路径
sys.path.insert(0, project_root)
from evaluation import print_tables
from evaluation.save_to_excel import save_all_results_to_excel


from evaluation.evaluate_metrics_mode import evaluate_metrics
from evaluation.constraint import calculate_path_quality, check_environment_constraint, check_person_constraint, check_time_condition, compare_cost, compare_mode_constraint, compare_pref, compare_semantic_fields, evaluate_common_sense_constraints, evaluate_mode_constraint, get_cost_from_plan, get_preference_from_plan, get_start_end_from_plan, load_jsonl, safe_get_str, verify_path_with_otp
from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84




def main():
    query_type_list = [
        "query", 
        "args"
        ]
    model_list = [
        "llama3.1:8b",

        # # # "gemini-2.5-pro",
        "qwen3-32b",        
        # # "glm-4.6",
        # # # "DeepSeek-V3.2",
        # # # "Qwen3-Coder-480B-A35B-Instruct",
        # "gemini-3-flash" ,
        "qwen3-max",
        "deepseek-v3.2",


        "gemini-3-flash-preview",
        # "gpt-5.2",
        "gpt-5.4",




    ]
    strategy_list = [
        "direct",
        "cot",
        "react",
        "reflect",
        "not-tool-direct"




        ]
    set_type_list = [
        # "train",
        # "validation",
        "test",
        ]


    jsonl_dir = "output_Result_combination_jsonl_V4"

    all_results = {}

    for set_type in set_type_list:
        if set_type == "train":
            query_data_list = pd.read_csv("./test-V4/train.csv")
        elif set_type == "validation":
            query_data_list = pd.read_csv("./test-V4/val.csv")
        elif set_type == "test":
            query_data_list = pd.read_csv("./test-V4/test.csv")
        else:
            continue
        # query_data_list = query_data_list.iloc[:-1]
        total_samples = len(query_data_list)


        for query_type in query_type_list:
            for model_name in model_list:
                for strategy in strategy_list:
                    jsonl_file = f"{jsonl_dir}/{set_type}/{query_type}_{model_name}_{strategy}_submission.jsonl"

                    if not os.path.exists(jsonl_file):
                        print(f"文件不存在: {jsonl_file}")
                        continue

                    print(f"\n{'=' * 60}")
                    print(f"文件: {jsonl_file}")
                    jsonl_data = load_jsonl(jsonl_file)
                    print(f"数据量: CSV={len(query_data_list)}, JSONL={len(jsonl_data)}")
                    print('=' * 60)

                    results = evaluate_metrics(query_data_list, jsonl_data,model_name)
                    all_results[jsonl_file] = results

                    # ========= 宏观指标 =========
                    macro = results["macro"]

                    plan_gen = int(round(macro["计划生成率"] * total_samples))
                    semantic_ok = int(round(macro["语义理解准确率"] * total_samples))
                    hard_ok = int(round(macro["硬性约束满足率"] * total_samples))
                    implicit_ok = int(round(macro["隐性约束满足率"] * total_samples))
                    common_ok = int(round(macro["常识性约束满足率"] * total_samples))
                    feasible_ok = int(round(macro["路径可行性率"] * total_samples))
                    pass_ok = int(round(macro["最终通过率"] * total_samples))
                    pass_3 = int(round(macro["三项通过率"] * total_samples))
                    pass_2 = int(round(macro["两项通过率"] * total_samples))
                    pass_1 = int(round(macro["一项通过率"] * total_samples))

                    


                    print("\n宏观指标:")
                    print(f"  计划生成率: {macro['计划生成率']:.4f} ({plan_gen}/{total_samples})")
                    print(f"  语义理解准确率: {macro['语义理解准确率']:.4f} ({semantic_ok}/{total_samples})")
                    print(f"  硬性约束满足率: {macro['硬性约束满足率']:.4f} ({hard_ok}/{total_samples})")
                    print(f"  隐性约束满足率: { macro['隐性约束满足率']:.4f} ({implicit_ok}/{total_samples})")
                    print(f"  常识性约束满足率: { macro['常识性约束满足率']:.4f} ({common_ok}/{total_samples})")
                    print(f"  路径可行性率: { macro['路径可行性率']:.4f} ({feasible_ok}/{total_samples})")
                    print(f"  最终通过率: { macro['最终通过率']:.4f} ({pass_ok}/{total_samples})")
                    print(f"  最终通过率: { macro['三项通过率']:.4f} ({pass_3}/{total_samples})")
                    print(f"  最终通过率: { macro['两项通过率']:.4f} ({pass_2}/{total_samples})")
                    print(f"  最终通过率: { macro['一项通过率']:.4f} ({pass_1}/{total_samples})")
                    print(f"  次优性比率-存在计划: { macro['次优性比率-存在计划']:.4f} ")
                    print(f"  次优性比率-通过: { macro['次优性比率-通过']:.4f} ")
                    print(f"  最优比例: { macro['最优比例']:.4f} ")




                    #  "最终通过率": macro_final_pass / total if total > 0 else 0,
                    # print(f"  平均路径质量: {macro['平均路径质量']:.4f}")

                    # ========= 微观指标 =========
                    micro = results["micro"]

                    semantic_correct = sum(
                        v["correct"] for v in results["semantic_field_details"].values()
                    )
                    semantic_total = sum(
                        v["total"] for v in results["semantic_field_details"].values()
                    )                    
                    hard_correct = sum(
                        v["correct"] for v in results["hard_constraint_details"].values()
                    )
                    hard_total = sum(
                        v["total"] for v in results["hard_constraint_details"].values()
                    )

                    implicit_correct = sum(
                        v["correct"] for v in results["implicit_constraint_details"].values()
                    )
                    implicit_total = sum(
                        v["total"] for v in results["implicit_constraint_details"].values()
                    )

                    common_correct = sum(
                        v["correct"] for v in results["common_sense_details"].values()
                    )
                    common_total = sum(
                        v["total"] for v in results["common_sense_details"].values()
                    )

                    level_correct = sum(
                        v["correct"] for v in results["level_details"].values()
                    )
                    level_total = sum(
                        v["total"] for v in results["level_details"].values()
                    )
                    print("\n微观指标:")
                    print(f"  语义理解字段正确率: {micro['语义理解字段正确率']:.4f} ({semantic_correct}/{semantic_total})")
                    print(f"  硬性约束正确率: {micro['硬性约束字段正确率']:.4f} ({hard_correct}/{hard_total})")
                    print(f"  隐性约束正确率: {micro['隐性约束字段正确率']:.4f} ({implicit_correct}/{implicit_total})")
                    print(f"  常识性约束字段正确率: {micro['常识性约束字段正确率']:.4f} ({common_correct}/{common_total})")

                    # ========= 各语义字段 =========
                    print("\n各语义字段准确率:")
                    for field, stats in results["semantic_field_details"].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")

                    # ========= 各约束字段 =========
                    print("\n硬性约束字段准确率:")
                    for field, stats in results["hard_constraint_details"].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")

                                        # ========= 各约束字段 =========
                    print("\n隐性约束字段准确率:")
                    for field, stats in results["implicit_constraint_details"].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")

                    # ========= 常识性约束 =========
                    print("\n常识性约束准确率:")
                    for field, stats in results["common_sense_details"].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")
                    print("\nlevel:")
                    for field, stats in results["level_details"].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")
    return all_results




if __name__ == "__main__":
    all_results = main()
    print("******************************************************************************************************************")
    # print_tables(all_results)
    save_all_results_to_excel(all_results, "./test-V4/TripPlanner_Evaluation_Test2.xlsx")



    print("1")