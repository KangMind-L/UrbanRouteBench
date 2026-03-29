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

from evaluation.constraint import calculate_path_quality, check_environment_constraint, check_person_constraint, check_time_condition, compare_mode_constraint, compare_pref, compare_semantic_fields, evaluate_common_sense_constraints, evaluate_mode_constraint, get_cost_from_plan, get_preference_from_plan, get_start_end_from_plan, load_jsonl, safe_get_str,verify_path_with_otp
from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84




def evaluate_metrics(csv_data: pd.DataFrame, jsonl_data: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    total = len(csv_data)

    # ===== 宏观指标 =====
    macro_plan_generated = 0
    macro_semantic_correct = 0
    macro_hard_correct = 0
    macro_implicit_correct = 0
    macro_common_sense_correct = 0
    macro_path_feasible = 0

    # ===== 微观指标 =====
    micro_semantic_total = 0
    micro_semantic_correct = 0
    micro_hard_total = 0
    micro_hard_correct = 0
    micro_implicit_total = 0
    micro_implicit_correct = 0
    micro_common_total = 0
    micro_common_correct = 0

    # ===== 字段统计 =====
    semantic_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["起点","终点","时间","时间性质","出行方式","费用","出行偏好","环境约束","个体约束"]}
    # 硬性约束
    hard_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["时间约束","费用约束","出行方式约束","出行偏好约束"]}
    # 隐式约束
    implicit_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["环境约束","个体约束"]}
    # 常识性
    common_sense_stats = {k: {"total": 0, "correct": 0} for k in
        ["时间连续性","步行或骑行距离限制","交通方式兼容性"]}

    path_quality_scores = []

    for idx, row in csv_data.iterrows():
        csv_idx = int(row["idx"]) if not pd.isna(row.get("idx")) else idx + 1
        model_output = jsonl_data.get(csv_idx)

        has_plan = model_output and model_output.get("出行计划")
        arguments = model_output and model_output.get("参数")
        plan = model_output.get("出行计划", []) if has_plan else []
        # a = type(arguments) 
        # b = type(plan) 



        if has_plan:
            macro_plan_generated += 1

        # ===== 语义字段 =====
        fields_check = {}
        hard_check = {}
        implicit_check = {}

        expected_start = safe_get_str(row.get("起点",""))
        expected_end = safe_get_str(row.get("终点",""))
        expected_time = safe_get_str(row.get("时间",""))
        expected_time_type = safe_get_str(row.get("时间性质",""))
        expected_mode = safe_get_str(row.get("出行方式",""))
        expected_cost = safe_get_str(row.get("费用",""))
        expected_pref = safe_get_str(row.get("出行偏好",""))
        expected_env = safe_get_str(row.get("环境约束",""))
        expected_person = safe_get_str(row.get("个体约束",""))

        # 解析参数中
        # argument_start = safe_get_str(arguments[0].get("起点",""))
        # argument_end = safe_get_str(arguments[0].get("终点",""))
        # argument_time = safe_get_str(arguments[0].get("时间",""))
        # argument_time_type = safe_get_str(arguments[0].get("时间性质",""))
        # argument_mode = safe_get_str(arguments[0].get("出行方式",""))
        # argument_cost = safe_get_str(arguments[0].get("费用",""))
        # argument_pref = safe_get_str(arguments[0].get("出行偏好",""))
        # argument_env = safe_get_str(arguments[0].get("环境约束",""))
        # argument_person = safe_get_str(arguments[0].get("个体约束",""))


        # TODO 判断语义

        fields_check= compare_semantic_fields(row,arguments)

        if has_plan:
            actual_start, actual_end, st, et = get_start_end_from_plan(plan)
            # actual_cost = get_cost_from_plan(plan)
            # actual_pref = get_preference_from_plan(plan)

            # fields_check["起点"] = actual_start == expected_start
            # fields_check["终点"] = actual_end == expected_end

            t_ok, tp_ok = check_time_condition(st, et, expected_time, expected_time_type)
            # fields_check["时间"] = t_ok
            # fields_check["时间性质"] = tp_ok

            step_modes = {safe_get_str(s.get("出行方式","")) for s in plan if isinstance(s,dict)}
            # fields_check["出行方式"] = evaluate_mode_constraint(expected_mode, step_modes)
            # fields_check["费用"] = compare_cost(actual_cost, expected_cost)
            # fields_check["出行偏好"] = compare_pref(actual_pref, expected_pref)

            # ===== 硬性约束 =====
            hard_check["出行偏好约束"] = fields_check["出行偏好"]
            hard_check["时间约束"] = t_ok
            hard_check["费用约束"] = fields_check["费用"]
            hard_check["出行方式约束"] = compare_mode_constraint(step_modes, expected_env, expected_person)

            # 隐式约束
            implicit_check["环境约束"] = check_environment_constraint(plan, expected_env)
            implicit_check["个体约束"] = check_person_constraint(plan, expected_person)

        else:
            # for k in semantic_field_stats:
            #     fields_check[k] = False
            for k in(hard_field_stats):
                hard_check[k] = False



            for k in (implicit_field_stats):
                implicit_check[k] = False

        # ===== 语义统计 =====
        for k,v in fields_check.items():
            semantic_field_stats[k]["total"] += 1
            if v: semantic_field_stats[k]["correct"] += 1

        micro_semantic_total += len(fields_check)
        micro_semantic_correct += sum(fields_check.values())

        if all(fields_check.values()):
            macro_semantic_correct += 1

                # ===== 硬性约束统计 =====
        for k,v in hard_check.items():
            hard_field_stats[k]["total"] += 1
            if v: hard_field_stats[k]["correct"] += 1

        # ===== 隐性约束统计 =====
        for k,v in implicit_check.items():
            implicit_field_stats[k]["total"] += 1
            if v: implicit_field_stats[k]["correct"] += 1

        micro_hard_total += len(hard_check)
        micro_hard_correct += sum(hard_check.values())

        micro_implicit_total += len(implicit_check)
        micro_implicit_correct += sum(implicit_check.values())

        if all(implicit_check.values()):
            macro_implicit_correct += 1

        if all(hard_check.values()):
            macro_hard_correct += 1

        # ===== 常识约束 =====
        cs = evaluate_common_sense_constraints(plan, expected_time, expected_time_type) if has_plan else {}
        cs_map = {
            "时间连续性": cs.get("time_continuity",{}).get("valid",False),
            "步行或骑行距离限制": cs.get("walking_time",{}).get("valid",False),
            "交通方式兼容性": cs.get("transport_compatibility",{}).get("valid",False)
        }

        for k,v in cs_map.items():
            common_sense_stats[k]["total"] += 1
            if v: common_sense_stats[k]["correct"] += 1

        micro_common_total += 3
        micro_common_correct += sum(cs_map.values())

        if all(cs_map.values()):
            macro_common_sense_correct += 1

        # ===== 路径 =====
        if has_plan and verify_path_with_otp(plan):
            macro_path_feasible += 1

        pq = calculate_path_quality(plan, row.get("plan",{})) if has_plan else {"overall_score":0}
        path_quality_scores.append(pq["overall_score"])

    return {
        "macro": {
            "计划生成率": macro_plan_generated / total if total > 0 else 0,
            "语义理解准确率": macro_semantic_correct / total if total > 0 else 0,
            "硬性约束满足率": macro_hard_correct / total if total > 0 else 0,
            "隐性约束满足率": macro_implicit_correct / total if total > 0 else 0,
            "常识性约束满足率": macro_common_sense_correct / total if total > 0 else 0,
            "路径可行性率": macro_path_feasible / total if total > 0 else 0,
            "平均路径质量": sum(path_quality_scores)/total if total > 0 else 0
        },
        "micro": {
            "语义字段正确率": micro_semantic_correct / micro_semantic_total if micro_semantic_total > 0 else 0,
            "硬性约束字段正确率": micro_hard_correct / micro_hard_total if micro_hard_total > 0 else 0,
            "隐性约束字段正确率": micro_implicit_correct / micro_implicit_total if micro_implicit_total > 0 else 0,
            "常识性约束字段正确率": micro_common_correct / micro_common_total if micro_common_total > 0 else 0
        },
        "semantic_field_details": {
            k:{
                "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0,
                "correct": v["correct"],
                "total": v["total"]
            } for k,v in semantic_field_stats.items()
        },
        "hard_constraint_details": {
            k:{
                "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0,
                "correct": v["correct"],
                "total": v["total"]
            } for k,v in hard_field_stats.items()
        },
        "implicit_constraint_details": {
            k:{
                "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0,
                "correct": v["correct"],
                "total": v["total"]
            } for k,v in implicit_field_stats.items()
        },
        "common_sense_details": {
            k:{
                "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0,
                "correct": v["correct"],
                "total": v["total"]
            } for k,v in common_sense_stats.items()
        }
    }
