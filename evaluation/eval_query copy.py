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

from evaluation.constraint import calculate_path_quality, check_environment_constraint, check_person_constraint, check_time_condition, compare_cost, compare_mode_constraint, compare_pref, evaluate_common_sense_constraints, evaluate_mode_constraint, get_cost_from_plan, get_preference_from_plan, get_start_end_from_plan, load_jsonl, safe_get_str, verify_path_with_otp
from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84


def evaluate_metrics(csv_data: pd.DataFrame, jsonl_data: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """评估指标"""
    total = len(csv_data)
    
    # 宏观指标
    macro_plan_generated = 0
    macro_semantic_correct = 0
    macro_constraint_correct = 0
    macro_common_sense_correct = 0
    macro_path_feasible = 0
    macro_path_quality_avg = 0.0
    
    # 微观指标
    micro_semantic_fields_total = 0
    micro_semantic_fields_correct = 0
    micro_common_sense_fields_total = 0
    micro_common_sense_fields_correct = 0
    
    # 每个语义字段的统计
    semantic_field_stats = {
        "起点": {"total": 0, "correct": 0},
        "终点": {"total": 0, "correct": 0},
        "时间": {"total": 0, "correct": 0},
        "时间性质": {"total": 0, "correct": 0},
        "出行方式": {"total": 0, "correct": 0},
        "费用": {"total": 0, "correct": 0},
        "出行偏好": {"total": 0, "correct": 0},
    }
    
    # 约束指标
    constraint_stats = {
        "出行偏好约束": {"total": 0, "correct": 0},
        "时间约束": {"total": 0, "correct": 0},
        "费用约束": {"total": 0, "correct": 0},
        "出行方式约束": {"total": 0, "correct": 0},
        "环境约束": {"total": 0, "correct": 0},
        "个体约束": {"total": 0, "correct": 0}
    }
    
    # 常识性约束指标
    common_sense_stats = {
        "时间连续性": {"total": 0, "correct": 0},
        "步行时间限制": {"total": 0, "correct": 0},
        "交通方式兼容性": {"total": 0, "correct": 0}
    }
    
    # 路径质量指标
    path_quality_scores = []
    
    for idx, csv_row in csv_data.iterrows():
        csv_idx = csv_row.get("idx")
        if pd.isna(csv_idx):
            csv_idx = idx + 1
        else:
            csv_idx = int(csv_idx)
        
        model_output = jsonl_data.get(csv_idx)
        
        # 1. 计划生成率
        has_plan = model_output is not None and model_output.get("出行计划") is not None
        if has_plan:
            macro_plan_generated += 1
        
        # 无论是否有计划，都需要计算其他指标
        plan = model_output.get("出行计划", []) if model_output else []
        
        # 获取期望值
        expected_start = safe_get_str(csv_row.get("起点", ""))
        expected_end = safe_get_str(csv_row.get("终点", ""))
        expected_time = safe_get_str(csv_row.get("时间", ""))
        expected_time_type = safe_get_str(csv_row.get("时间性质", ""))
        expected_mode = safe_get_str(csv_row.get("出行方式", ""))
        expected_cost = safe_get_str(csv_row.get("费用", ""))
        expected_preference = safe_get_str(csv_row.get("出行偏好", ""))
        optimal_plan = csv_row.get("plan", {})
        actual_preference_text = safe_get_str(csv_row.get("最优路径", ""))
        expected_text = safe_get_str(csv_row.get("出行路径", ""))
        expected_env = safe_get_str(csv_row.get("环境约束", ""))
        expected_person = safe_get_str(csv_row.get("个体约束", ""))


        
        # 检查每个语义字段
        fields_check = {}
        
        if has_plan and plan:
            # 如果有计划，进行正常检查
            actual_start, actual_end, actual_start_time, actual_end_time = get_start_end_from_plan(plan)
            actual_cost = get_cost_from_plan(plan)
            actual_preference = get_preference_from_plan(plan)
            
            # 起点检查
            fields_check["起点"] = actual_start == expected_start
            
            # 终点检查
            fields_check["终点"] = actual_end == expected_end
            
            # 时间检查
            time_ok, time_property_ok = check_time_condition(actual_start_time, actual_end_time, expected_time, expected_time_type)
            fields_check["时间"] = time_ok
            fields_check["时间性质"] = time_property_ok
            
            # 出行方式检查
            step_modes = set()
            for item in plan:
                if isinstance(item, dict) and "步骤" in item:
                    mode = safe_get_str(item.get("出行方式", ""))
                    if mode:
                        step_modes.add(mode)
            mode_ok = False
            if plan and expected_mode:

                
                expected_mode_str = safe_get_str(expected_mode)
                if expected_mode_str.lower() in ['null', 'none', 'nan', '', '无']:
                    mode_ok = True
                else:
                    mode_ok = evaluate_mode_constraint(expected_mode_str, step_modes)
            fields_check["出行方式"] = mode_ok
            
            # 费用检查
            cost_ok = compare_cost(actual_cost, expected_cost)
            fields_check["费用"] = cost_ok
            pref_ok = compare_pref(actual_preference, expected_preference)
            fields_check["出行偏好"] = pref_ok
            
        else:
            # 如果没有计划，所有字段都算失败
            fields_check["起点"] = False
            fields_check["终点"] = False
            fields_check["时间"] = False
            fields_check["时间性质"] = False
            fields_check["出行方式"] = False
            fields_check["费用"] = False
            time_ok = False
            mode_ok = False
            cost_ok = False
            actual_preference = ""
            step_modes = set() 
        
        # 更新语义字段统计
        for field, correct in fields_check.items():
            semantic_field_stats[field]["total"] += 1
            if correct:
                semantic_field_stats[field]["correct"] += 1
        
        # 2. 宏观语义理解准确性
        all_semantic_correct = all(fields_check.values())
        if all_semantic_correct:
            macro_semantic_correct += 1
        
        # 3. 微观语义理解准确性
        micro_semantic_fields_total += 6
        micro_semantic_fields_correct += sum(fields_check.values())
        
        # 4. 约束检查
        if expected_preference and expected_preference.strip():
            constraint_stats["出行偏好约束"]["total"] += 1
            ranking =Ranking()

            expected_preference_text = ranking.run(
            text=expected_text,
            time=expected_time,
            arriveBy=expected_time_type,
            preference=expected_preference
        )

            # actual_preference_text,expected_preference_text

            preference_ok = actual_preference_text==expected_preference_text
            if preference_ok:
                constraint_stats["出行偏好约束"]["correct"] += 1
                macro_constraint_correct += 1
        
        if expected_time and expected_time_type:
            constraint_stats["时间约束"]["total"] += 1
            if time_ok:
                constraint_stats["时间约束"]["correct"] += 1
        
        if expected_cost and expected_cost.strip():
            constraint_stats["费用约束"]["total"] += 1
            if cost_ok:
                constraint_stats["费用约束"]["correct"] += 1
        
        if expected_mode and expected_mode.strip():

            constraint_mode_ok = compare_mode_constraint(step_modes,expected_env,expected_person)

            constraint_stats["出行方式约束"]["total"] += 1
            if constraint_mode_ok:
                constraint_stats["出行方式约束"]["correct"] += 1

        # 环境和个体约束检查
        env_ok = check_environment_constraint(plan, expected_env)
        person_ok = check_person_constraint(plan, expected_person)

        # 更新约束统计
        if expected_env and expected_env != "-":
            constraint_stats["环境约束"]["total"] += 1
            if env_ok:
                constraint_stats["环境约束"]["correct"] += 1

        if expected_person and expected_person != "-":
            constraint_stats["个体约束"]["total"] += 1
            if person_ok:
                constraint_stats["个体约束"]["correct"] += 1

        # "环境约束": {"total": 0, "correct": 0},
        # "个体约束": {"total": 0, "correct": 0}
        
        # 5. 常识性约束检查
        if has_plan and plan:
            common_sense_result = evaluate_common_sense_constraints(plan, expected_time, expected_time_type)
        else:
            # 没有计划，常识性约束全部失败
            common_sense_result = {
                "time_continuity": {"valid": False},
                "walking_time": {"valid": False},
                "transport_compatibility": {"valid": False},
                "all_valid": False
            }
        
        # 宏观常识性约束
        if common_sense_result["all_valid"]:
            macro_common_sense_correct += 1
        
        # 微观常识性约束
        micro_common_sense_fields_total += 3
        micro_common_sense_fields_correct += sum([
            int(common_sense_result["time_continuity"]["valid"]),
            int(common_sense_result["walking_time"]["valid"]),
            int(common_sense_result["transport_compatibility"]["valid"])
        ])
        
        # 更新常识性约束统计
        for field, result in [
            ("时间连续性", common_sense_result["time_continuity"]["valid"]),
            ("步行时间限制", common_sense_result["walking_time"]["valid"]),
            ("交通方式兼容性", common_sense_result["transport_compatibility"]["valid"])
        ]:
            common_sense_stats[field]["total"] += 1
            if result:
                common_sense_stats[field]["correct"] += 1
        
        # 6. 路径可行性检查
        if has_plan and plan:
            # constraint_mode_ok = compare_mode_constraint(step_modes,expected_env,expected_person)
            path_feasible =  verify_path_with_otp(plan)  
        else:
            path_feasible = False
        
        if path_feasible:
            macro_path_feasible += 1

        # else:
        #     print("1")
        
        # 7. 成本时间合理性
        if has_plan and plan:
            path_quality = calculate_path_quality(plan, optimal_plan)
        else:
            path_quality = {
                "normalized_distance": 1.0,
                "cost_ratio": 1.0,
                "time_ratio": 1.0,
                "overall_score": 0.0
            }
        
        path_quality_scores.append(path_quality["overall_score"])
    
    # 计算路径质量平均值
    macro_path_quality_avg = sum(path_quality_scores) / len(path_quality_scores) if path_quality_scores else 0.0
    
    # 计算指标
    results = {
        "macro": {
            "计划生成率": macro_plan_generated / total if total > 0 else 0,
            "语义理解准确率": macro_semantic_correct / total if total > 0 else 0,
            "隐性约束满足率": macro_constraint_correct / total if total > 0 else 0,
            "常识性约束满足率": macro_common_sense_correct / total if total > 0 else 0,
            "路径可行性率": macro_path_feasible / total if total > 0 else 0,
            "平均路径质量": macro_path_quality_avg
        },
        "micro": {
            "语义字段正确率": micro_semantic_fields_correct / micro_semantic_fields_total if micro_semantic_fields_total > 0 else 0,
            "常识性约束字段正确率": micro_common_sense_fields_correct / micro_common_sense_fields_total if micro_common_sense_fields_total > 0 else 0,
        },
        "semantic_field_details": {
            field: {
                "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "correct": stats["correct"],
                "total": stats["total"]
            }
            for field, stats in semantic_field_stats.items()
        },
        "constraint_details": {
            field: {
                "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "correct": stats["correct"],
                "total": stats["total"]
            }
            for field, stats in constraint_stats.items()
        },
        "common_sense_details": {
            field: {
                "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "correct": stats["correct"],
                "total": stats["total"]
            }
            for field, stats in common_sense_stats.items()
        },
        "counts": {
            "total_samples": total,
            "plan_generated": macro_plan_generated,
            "semantic_correct": macro_semantic_correct,
            "common_sense_correct": macro_common_sense_correct,
            "path_feasible": macro_path_feasible,
            "semantic_fields_total": micro_semantic_fields_total,
            "semantic_fields_correct": micro_semantic_fields_correct,
            "common_sense_fields_total": micro_common_sense_fields_total,
            "common_sense_fields_correct": micro_common_sense_fields_correct,
        }
    }
    
    return results

def main():
    """主函数示例"""
    query_type_list = [
        "query",
        "args"
                ]
    model_list = ["qwen3-max", "llama3.1:8b","deepseek-v3.2"]
    strategy_list = ["ReAct"]
    set_type_list = ["train"]
    
    all_results = {}
    
    for set_type in set_type_list:
        if set_type == 'train':
            query_data_list = pd.read_csv('./12-20/train.csv')
        elif set_type == 'validation':
            query_data_list = pd.read_csv('./12-20/val.csv')
        elif set_type == 'test':
            query_data_list = pd.read_csv('./12-20/test.csv')
        else:
            continue
        
        jsonl_dir = "output_Result_combination_jsonl"
        
        for query_type in query_type_list:
            for model_name in model_list:
                for strategy in strategy_list:
                    jsonl_file = f"{jsonl_dir}/{query_type}_{model_name}_{strategy}_{set_type}_submission.jsonl"
                    
                    if not os.path.exists(jsonl_file):
                        print(f"文件不存在: {jsonl_file}")
                        continue
                    
                    print(f"\n{'='*60}")
                    print(f"文件: {jsonl_file}")
                    jsonl_data = load_jsonl(jsonl_file)
                    print(f"数据量: CSV={len(query_data_list)}, JSONL={len(jsonl_data)}")
                    print('='*60)
                    
                    results = evaluate_metrics(query_data_list, jsonl_data)
                    all_results[jsonl_file] = results
                    
                    # 打印结果
                    print(f"\n宏观指标:")
                    print(f"  计划生成率: {results['macro']['计划生成率']:.4f} ({results['counts']['plan_generated']}/{results['counts']['total_samples']})")
                    print(f"  语义理解准确率: {results['macro']['语义理解准确率']:.4f} ({results['counts']['semantic_correct']}/{results['counts']['total_samples']})")
                    print(f"  隐性约束满足率: {results['macro']['隐性约束满足率']:.4f}")
                    print(f"  常识性约束满足率: {results['macro']['常识性约束满足率']:.4f} ({results['counts']['common_sense_correct']}/{results['counts']['total_samples']})")
                    print(f"  路径可行性率: {results['macro']['路径可行性率']:.4f} ({results['counts']['path_feasible']}/{results['counts']['total_samples']})")
                    print(f"  平均路径质量: {results['macro']['平均路径质量']:.4f}")
                    
                    print(f"\n微观指标:")
                    print(f"  语义字段正确率: {results['micro']['语义字段正确率']:.4f} ({results['counts']['semantic_fields_correct']}/{results['counts']['semantic_fields_total']})")
                    print(f"  常识性约束字段正确率: {results['micro']['常识性约束字段正确率']:.4f} ({results['counts']['common_sense_fields_correct']}/{results['counts']['common_sense_fields_total']})")
                    
                    print(f"\n各语义字段准确率:")
                    for field, stats in results['semantic_field_details'].items():
                        print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")
                    
                    print(f"\n常识性约束准确率:")
                    for field, stats in results['common_sense_details'].items():
                        if stats['total'] > 0:
                            print(f"  {field}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")
    
    return all_results

if __name__ == "__main__":
    all_results = main()