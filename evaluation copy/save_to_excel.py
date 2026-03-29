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

from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84

import pandas as pd


def save_all_results_to_excel(all_results, output_path="all_tables.xlsx"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sheet_name = "Results"
        current_row = 0

        # ======================================================
        # 工具函数：写表 + 空三行
        # ======================================================
        def write_block(title, headers, rows):
            nonlocal current_row

            # 写标题
            pd.DataFrame([[title]]).to_excel(
                writer, sheet_name=sheet_name,
                startrow=current_row, index=False, header=False
            )
            current_row += 1

            # 写表格
            df = pd.DataFrame(rows, columns=headers)
            df.to_excel(
                writer, sheet_name=sheet_name,
                startrow=current_row, index=False
                    )
            current_row += len(df) + 3  # 表后空三行

        # ======================================================
        # 表 1：宏观 + 微观指标
        # ======================================================
        headers1 = [
            "类型", "模型", "策略",
            "计划生成率",
            "语义理解准确率(宏观)", "语义字段正确率(微观)",
            "硬性约束满足率(宏观)", "硬性约束字段正确率(微观)",
            "隐性约束满足率(宏观)", "隐性约束字段正确率(微观)",
            "常识性约束满足率(宏观)", "常识性约束字段正确率(微观)",
            "路径可行性率",
            "平均路径质量"
        ]


        rows1 = []

        for jsonl_file, result in all_results.items():
            basename = os.path.basename(jsonl_file)
            parts = basename.replace("_submission.jsonl", "").split("_")
            if len(parts) < 4:
                continue

            query_type, model_name, strategy, set_type = parts[:4]
            if set_type != "train":
                continue

            macro = result["macro"]
            micro = result["micro"]

            rows1.append([
                query_type, model_name, strategy,
                f"{macro['计划生成率']:.4f}",

                f"{macro['语义理解准确率']:.4f}",
                f"{micro['语义字段正确率']:.4f}",

                f"{macro['硬性约束满足率']:.4f}",
                f"{micro['硬性约束字段正确率']:.4f}",

                f"{macro['隐性约束满足率']:.4f}",
                f"{micro['隐性约束字段正确率']:.4f}",

                f"{macro['常识性约束满足率']:.4f}",
                f"{micro['常识性约束字段正确率']:.4f}",

                f"{macro['路径可行性率']:.4f}",
                f"{macro['平均路径质量']:.4f}",
            ])


        write_block("【表1】宏观与微观综合指标", headers1, rows1)

        # ======================================================
        # 表 2：语义字段准确率（SA）
        # ======================================================
        headers2 = ["类型", "模型", "策略", "整体SA",
                    "起点", "终点", "时间", "时间性质",
                    "出行方式", "费用", "出行偏好", "环境约束", "个体约束"]

        rows2 = []

        for jsonl_file, result in all_results.items():
            basename = os.path.basename(jsonl_file)
            parts = basename.replace("_submission.jsonl", "").split("_")
            if len(parts) < 4:
                continue

            query_type, model_name, strategy, set_type = parts[:4]
            if set_type != "train":
                continue

            sd = result["semantic_field_details"]
            overall = sum(v["accuracy"] for v in sd.values()) / len(sd)

            rows2.append([
                query_type, model_name, strategy, f"{overall:.4f}",
                *[f"{sd[k]['accuracy']:.4f}" for k in
                  ["起点","终点","时间","时间性质","出行方式","费用","出行偏好","环境约束","个体约束"]]
            ])

        write_block("【表2】语义字段准确率（Semantic Accuracy, SA）", headers2, rows2)

        # ======================================================
        # 表 3：硬性约束字段准确率
        # ======================================================
        headers3 = ["类型", "模型", "策略", "整体SA",
                    "时间约束", "费用约束", "出行方式约束", "出行偏好约束"]

        rows3 = []

        for jsonl_file, result in all_results.items():
            basename = os.path.basename(jsonl_file)
            parts = basename.replace("_submission.jsonl", "").split("_")
            if len(parts) < 4:
                continue

            query_type, model_name, strategy, set_type = parts[:4]
            if set_type != "train":
                continue

            hd = result["hard_constraint_details"]
            overall = sum(v["accuracy"] for v in hd.values()) / len(hd)

            rows3.append([
                query_type, model_name, strategy, f"{overall:.4f}",
                *[f"{hd[k]['accuracy']:.4f}" for k in
                  ["时间约束","费用约束","出行方式约束","出行偏好约束"]]
            ])

        write_block("【表3】硬性约束字段准确率", headers3, rows3)

        # ======================================================
        # 表 4：隐性约束字段准确率
        # ======================================================
        headers4 = ["类型", "模型", "策略", "整体SA", "环境约束", "个体约束"]
        rows4 = []

        for jsonl_file, result in all_results.items():
            basename = os.path.basename(jsonl_file)
            parts = basename.replace("_submission.jsonl", "").split("_")
            if len(parts) < 4:
                continue

            query_type, model_name, strategy, set_type = parts[:4]
            if set_type != "train":
                continue

            ic = result["implicit_constraint_details"]
            overall = sum(v["accuracy"] for v in ic.values()) / len(ic)

            rows4.append([
                query_type, model_name, strategy, f"{overall:.4f}",
                f"{ic['环境约束']['accuracy']:.4f}",
                f"{ic['个体约束']['accuracy']:.4f}",
            ])

        write_block("【表4】隐性约束字段准确率", headers4, rows4)

        # ======================================================
        # 表 5：常识性约束准确率
        # ======================================================
        headers5 = ["类型", "模型", "策略", "整体SA",
                    "时间连续性", "步行时间限制", "交通方式兼容性"]

        rows5 = []

        for jsonl_file, result in all_results.items():
            basename = os.path.basename(jsonl_file)
            parts = basename.replace("_submission.jsonl", "").split("_")
            if len(parts) < 4:
                continue

            query_type, model_name, strategy, set_type = parts[:4]
            if set_type != "train":
                continue

            cs = result["common_sense_details"]
            overall = sum(v["accuracy"] for v in cs.values()) / len(cs)

            rows5.append([
                query_type, model_name, strategy, f"{overall:.4f}",
                f"{cs['时间连续性']['accuracy']:.4f}",
                f"{cs['步行或骑行距离限制']['accuracy']:.4f}",
                f"{cs['交通方式兼容性']['accuracy']:.4f}",
            ])

        write_block("【表5】常识性约束准确率", headers5, rows5)

    print(f"✅ 已保存单文件五表结构：{output_path}")
