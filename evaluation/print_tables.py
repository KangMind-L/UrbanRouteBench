
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

from evaluation.constraint import calculate_path_quality, check_environment_constraint, check_person_constraint, check_time_condition, compare_cost, compare_mode_constraint, compare_pref, compare_semantic_fields, evaluate_common_sense_constraints, evaluate_mode_constraint, get_cost_from_plan, get_preference_from_plan, get_start_end_from_plan, load_jsonl, safe_get_str, verify_path_with_otp
from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84



def print_tables(all_results):
    import os

    table1, table2, table3, table4, table5 = [], [], [], [], []

    for jsonl_file, results in all_results.items():
        basename = os.path.basename(jsonl_file)
        parts = basename.replace("_submission.jsonl", "").split("_")
        if len(parts) < 4:
            continue

        query_type, model, strategy, set_type = parts[:4]
        if set_type != "train":
            continue

        # ================= 表1：宏观 + 微观 =================
        if query_type == "query":
            macro, micro = results["macro"], results["micro"]
            table1.append([
                query_type, model, strategy,
                f"{macro['计划生成率']:.4f}",
                f"{macro['语义理解准确率']:.4f}",
                f"{macro['硬性约束满足率']:.4f}",
                f"{macro['隐性约束满足率']:.4f}",
                f"{macro['常识性约束满足率']:.4f}",
                f"{macro['路径可行性率']:.4f}",
                f"{macro['平均路径质量']:.4f}",
                f"{micro['语义字段正确率']:.4f}",
                f"{micro['硬性约束字段正确率']:.4f}",
                f"{micro['隐性约束字段正确率']:.4f}",
                f"{micro['常识性约束字段正确率']:.4f}"
            ])

        # ================= 表2：语义字段 =================
        if query_type == "query":
            sd = results["semantic_field_details"]
            overall = sum(v["accuracy"] for v in sd.values()) / len(sd)

            table2.append([
                query_type, model, strategy, f"{overall:.4f}",
                f"{sd['起点']['accuracy']:.4f}",
                f"{sd['终点']['accuracy']:.4f}",
                f"{sd['时间']['accuracy']:.4f}",
                f"{sd['时间性质']['accuracy']:.4f}",
                f"{sd['出行方式']['accuracy']:.4f}",
                f"{sd['费用']['accuracy']:.4f}",
                f"{sd['出行偏好']['accuracy']:.4f}",
                f"{sd['环境约束']['accuracy']:.4f}",
                f"{sd['个体约束']['accuracy']:.4f}"
            ])

        # ================= 表3：硬性约束 =================
        if query_type == "args":
            hc = results["hard_constraint_details"]
            overall = sum(v["accuracy"] for v in hc.values()) / len(hc)

            table3.append([
                query_type, model, strategy, f"{overall:.4f}",
                f"{hc['时间约束']['accuracy']:.4f}",
                f"{hc['费用约束']['accuracy']:.4f}",
                f"{hc['出行方式约束']['accuracy']:.4f}",
                f"{hc['出行偏好约束']['accuracy']:.4f}"
            ])

        # ================= 表4：隐性约束 =================
        if query_type == "args":
            ic = results["implicit_constraint_details"]
            overall = sum(v["accuracy"] for v in ic.values()) / len(ic)

            table4.append([
                query_type, model, strategy, f"{overall:.4f}",
                f"{ic['环境约束']['accuracy']:.4f}",
                f"{ic['个体约束']['accuracy']:.4f}"
            ])

        # ================= 表5：常识性约束 =================
        if query_type == "args":
            cc = results["common_sense_details"]
            overall = sum(v["accuracy"] for v in cc.values()) / len(cc)

            table5.append([
                query_type, model, strategy, f"{overall:.4f}",
                f"{cc['时间连续性']['accuracy']:.4f}",
                f"{cc['步行时间限制']['accuracy']:.4f}",
                f"{cc['交通方式兼容性']['accuracy']:.4f}"
            ])

    # ================= 通用打印 =================
    def print_table(title, headers, rows):
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 4 for i in range(len(headers))]
        sep = "-" * (sum(col_widths) + len(headers) + 1)

        print("\n" + title)
        print(sep)
        print("|" + "|".join(f"{headers[i]:^{col_widths[i]}}" for i in range(len(headers))) + "|")
        print(sep)
        for r in rows:
            print("|" + "|".join(f"{r[i]:^{col_widths[i]}}" for i in range(len(r))) + "|")
        print(sep)

    # ================= 打印五张表 =================
    print_table(
        "表1：宏观与微观综合指标",
        ["query", "模型", "策略", "计划生成率", "语义理解准确率", "硬性约束满足率",
         "隐性约束满足率", "常识性约束满足率", "路径可行性率", "平均路径质量",
         "语义字段正确率", "硬性约束正确率", "隐性约束正确率", "常识性约束字段正确率"],
        table1
    )

    print_table(
        "表2：语义字段准确率",
        ["query", "模型", "策略", "整体(SA)", "起点", "终点", "时间", "时间性质",
         "出行方式", "费用", "出行偏好", "环境约束", "个体约束"],
        table2
    )

    print_table(
        "表3：硬性约束字段准确率",
        ["args", "模型", "策略", "整体(SA)", "时间约束", "费用约束",
         "出行方式约束", "出行偏好约束"],
        table3
    )

    print_table(
        "表4：隐性约束字段准确率",
        ["args", "模型", "策略", "整体(SA)", "环境约束", "个体约束"],
        table4
    )

    print_table(
        "表5：常识性约束字段准确率",
        ["args", "模型", "策略", "整体(SA)", "时间连续性",
         "步行时间限制", "交通方式兼容性"],
        table5
    )
