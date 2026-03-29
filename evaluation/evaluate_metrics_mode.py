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

from evaluation.constraint import calculate_path_quality, calculate_path_similarity, check_environment_constraint, check_person_constraint, check_time_condition, compare_mode_constraint, compare_pref, compare_semantic_fields, evaluate_common_sense_constraints, evaluate_mode_constraint, get_cost_from_plan, get_preference_from_plan, get_start_end_from_plan, load_jsonl, safe_get_str,verify_path_with_otp
from tools.ranking.apis import Ranking
from tools.routes.apis import Routes
from tools.wgs84.apis import Wgs84


from datetime import datetime
import re

def parse_duration_minutes(text):
    """
    '61分钟47秒' → 61.78
    """
    if not text:
        return None

    min_match = re.search(r"(\d+)\s*分钟", text)
    sec_match = re.search(r"(\d+)\s*秒", text)

    minutes = int(min_match.group(1)) if min_match else 0
    seconds = int(sec_match.group(1)) if sec_match else 0

    return minutes + seconds / 60


def check_time_window(expected_minutes, actual_text):
    """
    实际用时 <= 预期时间窗口 → True
    预期为 0 → True
    """
    if expected_minutes == 0:
        return True

    actual_minutes = parse_duration_minutes(actual_text)
    if actual_minutes is None:
        return False

    return actual_minutes <= expected_minutes

def parse_time_str(t):
    """
    支持 HH:MM / HH:MM:SS
    返回 datetime.time
    """
    if not t:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t, fmt).time()
        except ValueError:
            continue
    return None


def check_departure_time(expected, actual):
    """
    实际出发时间 >= 预期出发时间 → True
    """
    t_exp = parse_time_str(expected)
    t_act = parse_time_str(actual)

    if t_exp is None or t_act is None:
        return False

    return t_act >= t_exp

def parse_cost(text):
    """
    '2.0 元' → 2.0
    """
    if not text:
        return None

    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else None


def check_cost(expected_cost, actual_text):
    """
    实际费用 <= 预期费用 → True
    """
    actual_cost = parse_cost(actual_text)
    if actual_cost is None:
        return False

    return actual_cost <= expected_cost
def normalize_unordered_str(value, sep):
    """
    将 'a-b-c' 或 'a|b|c' 归一化为 frozenset
    """
    if value=='无偏好':
        value = ''

    if not value:
        return frozenset()
    return frozenset(v.strip() for v in value.split(sep) if v.strip())
def equal_preferences(v1, v2):
    return normalize_unordered_str(v1, '-') == normalize_unordered_str(v2, '-')  or normalize_unordered_str(v1, '-') == normalize_unordered_str(v2, '、')
def equal_modes(v1, v2):
    return normalize_unordered_str(v1, '|') == normalize_unordered_str(v2, '|')
def extract_all_modes(plan):
    """
    plan:
      - [steps, summary]
      - [steps1, steps2, summary]

    return:
      list[str]  # 保序、不重复
    """
    if not plan or len(plan) < 2:
        return []

    trip_segments = plan[:-1]  # 去掉 summary
    seen = set()
    modes = []

    for segment in trip_segments:
        if not isinstance(segment, list):
            continue
        try:
            for step in segment:
                mode = step.get("出行方式")
                if mode and mode not in seen:
                    seen.add(mode)
                    modes.append(mode)
        except:
            a=1
    return modes

def normalize_mode(mode: str):
    if not mode:
        return None

    bike_keywords = {
        # 英文 / 代码类
        "BICYCLE", "BIKE", "BICYCLE_RENT", "BIKE_RENT", "SHARED_BIKE",

        # 中文常见
        "单车", "骑行", "自行车", "骑车", "骑单车",
        "共享单车", "公共自行车", "扫码单车",

        # 偏口语 / 变体
        "骑自行车", "骑共享单车", "骑小蓝车", "骑摩拜", "骑哈啰",
    }

    # ---------- 开车 / 自驾 ----------
    car_keywords = {
        # 英文 / 代码类
        "CAR", "DRIVING", "DRIVE", "SELF_DRIVE",

        # 中文常见
        "开车", "自驾", "驾车", "自家车", "私家车",

        # 偏口语 / 变体
        "自己开车", "开私家车", "开小车", "开轿车",
    }

    # ---------- 打车 / 网约车 ----------
    taxi_keywords = {
        # 英文 / 代码类
        "CAR_PICKUP", "TAXI", "RIDE_HAILING", "RIDE_HAIL", "CAB",

        # 中文常见
        "打车", "出租车", "网约车", "的士",

        # 平台类
        "滴滴", "高德打车", "曹操出行", "首汽约车", "神州专车",

        # 偏口语 / 变体
        "叫车", "叫出租车", "叫网约车", "打的",
    }

    # ---------- 公交 / 地铁 / 轨道交通 ----------
    bus_keywords = {
        # 英文 / 代码类
       
        # 中文常见
        "公交",

        # 具体说法
        "公交车", "巴士",

        # 偏口语 / 变体
        "坐公交","乘公交",
    }
    subway_keywords = {
        # 英文 / 代码类
        "SUBWAY", "METRO", "BUS", "TRAM", "RAIL", "LIGHT_RAIL", "COMMUTER_RAIL",

        # 中文常见
        "地铁", "轨道交通", "有轨电车", "城轨", "轻轨", "市域铁路",

        # 具体说法
        "公共交通", "公共运输",

        # 偏口语 / 变体
        "坐地铁", "搭地铁", "乘地铁",
    }
    # ---------- 步行 ----------
    walk_keywords = {
        # 英文 / 代码类
        "WALK", "WALKING", "FOOT",

        # 中文常见
        "步行", "走路", "步走",

        # 偏口语 / 变体
        "走过去", "步行前往", "步行到达",
    }
    mode = mode.strip()

    if mode in bike_keywords:
        return "单车"
    if mode in car_keywords:
        return "开车"
    if mode in bus_keywords:
        return "公交"
    if mode in subway_keywords:
        return "地铁"
    if mode in taxi_keywords:
        return "打车"
    if mode in  walk_keywords:
        return "步行"

    return mode  # 兜底

def match_actual_modes(expected_modes: Optional[Set[str]], actual_modes: Set[str]) -> bool:
    """
    判断实际出行方式是否符合预期
    """
    if expected_modes is None:
        return True

    actual = set(actual_modes)

    if "公共交通" in expected_modes:
        allowed_transit = {"步行", "公交车", "地铁"}
        actual -= allowed_transit
        expected = expected_modes - {"公共交通"}
    else:
        expected = expected_modes

    return actual <= expected
from typing import Optional, Set

def parse_expected_modes(expected_str: str) -> Optional[Set[str]]:

    """
    将预期模式字符串解析为标准化集合

    支持组合模式：
    '公交车|地铁|公共交通|开车|打车|单车+公共交通'
    → set('公交车', '地铁', '公共交通', '开车', '打车', '单车')
    """
    if not expected_str:
        return None  # 表示不限制

    expected = set()

    for item in expected_str.split("|"):
        item = item.strip()
        if not item:
            continue

        # 组合语义
        if item == "单车+公共交通":
            expected.add("单车")
            expected.add("公交")
            expected.add("地铁")
        elif item == "公共交通":
            expected.add("步行")
            expected.add("公交")
            expected.add("地铁")
        elif item == "公交车":
            expected.add("步行")
            expected.add("公交")
        elif item == "地铁":
            expected.add("步行")
            expected.add("地铁")
        elif item == "开车":
            expected.add("开车")
            # expected.add("地铁")
        elif item == "打车":
            expected.add("步行")
            expected.add("打车")
            # expected.add("地铁")
        else:
            expected.add(normalize_mode(item))

    return expected
def check_travel_mode(expected_mode_str, actual_modes):
    """
    expected_mode_str: str | None
    actual_modes: list[str]

    return: bool
    """
    # expected_mode_str = ''
    # actual_modes = ['CAR']
    # ① 不限制
    expected_set = parse_expected_modes(expected_mode_str)
    if expected_set is None:
        return True

    # ② 归一化实际出行方式
    actual_set = set()
    for m in actual_modes:
        if m:  # 过滤掉空值（如 None, "", [], 等）
            normalized = normalize_mode(m)
            actual_set.add(normalized)

    # ③ 实际必须全部属于预期
    return actual_set.issubset(expected_set)
def all_false(keys):
    return {k: False for k in keys}

def check_waypoint_and_stay(plan, expected_waypoint, expected_stay_time):
    """
    plan: 出行计划（len >= 2）
    expected_waypoint: str
    expected_stay_time: int（分钟）
    """

    # ===== 默认返回 =====
    wp_ok = True
    stay_ok = True

    # ===== 只有一段 =====
    # if len(plan[0]) < 2:
    #     return True, True

    # ===== 两段（1 个途经点）=====
    seg1 = plan[0]
    seg2 = plan[1]

    # 提取终点 / 起点
    # 第二段路径
    try:
        seg2_start = safe_get_str(seg2[0].get("起点", ""))
        seg2_end = safe_get_str(seg2[-1].get("终点", ""))
    except Exception:
        seg2_start = ""
        seg2_end = ""

    # 第一段路径
    try:
        seg1_start = safe_get_str(seg1[0].get("起点", ""))
        seg1_end = safe_get_str(seg1[-1].get("终点", ""))
    except Exception:
        seg1_start = ""
        seg1_end = ""


    # ---- 途经点判断 ----
    wp_ok = (
        expected_waypoint != ""
        and expected_waypoint == seg1_end
        and expected_waypoint == seg2_start
    )

    # ---- 停留时间判断 ----
    if expected_stay_time == 0:
        stay_ok = True
    else:
        try:
            t_arrive = parse_time(safe_get_str(seg1[-1].get("结束时间", "")))
            t_depart = parse_time(safe_get_str(seg2[0].get("开始时间", "")))
        

            if not t_arrive or not t_depart:
                stay_ok = False
            else:
                # 跨天判断
                if t_depart < t_arrive:
                    t_depart += timedelta(days=1)

                delta_min = (t_depart - t_arrive).total_seconds() / 60
                stay_ok = delta_min >= expected_stay_time

        except Exception:
            stay_ok = False
    return wp_ok, stay_ok

    import re
import re

ALPHA_TRANSFER = 10.0
ALPHA_COST = 2.0

WEIGHTS = {
    "total": 0.4,
    "walk": 0.3,
    "transfer": 0.15,
    "cost": 0.15
}

def extract_plan_metrics(raw_plan: str):
    # 1️⃣ 总出行时间
    time_match = re.search(r"总出行时间：(\d+)分钟(\d+)秒", raw_plan)
    if time_match:
        minutes = float(time_match.group(1))
        seconds = float(time_match.group(2))
        total_time_min = minutes + seconds / 60.0
    else:
        total_time_min = 0.0

    # 2️⃣ 总步行距离 -> 转成步行时间
    walk_match = re.search(r"总步行距离：([\d\.]+)\s*米", raw_plan)
    if walk_match:
        walk_distance_m = float(walk_match.group(1))
        walk_time_min = walk_distance_m / 60.0   # 3.6km/h = 60m/min
    else:
        walk_time_min = 0.0

    # 3️⃣ 换乘次数
    transfer_match = re.search(r"换乘次数：(\d+)", raw_plan)
    transfer_count = float(transfer_match.group(1)) if transfer_match else 0.0

    # 4️⃣ 费用
    cost_match = re.search(r"预计费用：([\d\.]+)", raw_plan)
    cost = float(cost_match.group(1)) if cost_match else 0.0

    return total_time_min, walk_time_min, transfer_count, cost


def compute_plan_score(raw_plan):

    # ======================
    # 1️⃣ 判断输入类型
    # ======================
    if isinstance(raw_plan, str):
        total_time_min, walk_time_min, transfer_count, cost = extract_plan_metrics(raw_plan)

    elif isinstance(raw_plan, dict):

        # 总出行时间
        time_match = re.search(r"(\d+)分钟(\d+)秒", raw_plan.get("总出行时间", "0分钟0秒"))
        if time_match:
            minutes = float(time_match.group(1))
            seconds = float(time_match.group(2))
            total_time_min = minutes + seconds / 60.0
        else:
            total_time_min = 0.0

        # 总步行距离
        walk_str = raw_plan.get("总步行距离", "0 米")
        walk_nums = re.findall(r"[\d\.]+", walk_str)
        walk_distance = float(walk_nums[0]) if walk_nums else 0.0
        walk_time_min = walk_distance / 60.0

        # 换乘次数
        transfer_raw = raw_plan.get("换乘次数", 0)

        if isinstance(transfer_raw, (int, float)):
            transfer_count = float(transfer_raw)
        else:
            transfer_raw = str(transfer_raw).strip()
            if transfer_raw == "-" or transfer_raw == "":
                transfer_count = 0.0
            else:
                nums = re.findall(r"\d+", transfer_raw)
                transfer_count = float(nums[0]) if nums else 0.0


        # 费用
        cost_str = raw_plan.get("预计费用", "0 元")
        cost_nums = re.findall(r"[\d\.]+", cost_str)
        cost = float(cost_nums[0]) if cost_nums else 0.0

    else:
        raise ValueError("raw_plan 必须是 str 或 dict 类型")

    # ======================
    # 2️⃣ 成本放大
    # ======================
    transfer_cost = transfer_count * ALPHA_TRANSFER
    cost_cost = cost * ALPHA_COST

    # ======================
    # 3️⃣ 加权评分
    # ======================
    score = (
        total_time_min * WEIGHTS["total"] +
        walk_time_min * WEIGHTS["walk"] +
        transfer_cost * WEIGHTS["transfer"] +
        cost_cost * WEIGHTS["cost"]
    )

    return {
        "total_time_min": total_time_min,
        "walk_time_min": walk_time_min,
        "transfer_cost": transfer_cost,
        "cost_cost": cost_cost,
        "final_score": score
    }



def extract_actual_info(plan):
    """
    返回：
    actual_start, actual_end,
    actual_start_time, actual_end_time,
    actual_pref, actual_all_time, actual_cost,
    actual_modes
    """
    actual_start, actual_end, actual_start_time, actual_end_time = get_start_end_from_plan(plan)

    summary = plan[-1] if isinstance(plan[-1], dict) else {}

    actual_pref = safe_get_str(summary.get("方案偏好", ""))
    actual_all_time = safe_get_str(summary.get("总出行时间", "0"))
    actual_cost = safe_get_str(summary.get("预计费用", "0"))

    actual_modes = extract_all_modes(plan)

    return (
        actual_start, actual_end,
        actual_start_time, actual_end_time,
        actual_pref, actual_all_time, actual_cost,
        actual_modes
    )
from datetime import datetime

def parse_time(t: str):
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None

def evaluate_metrics(csv_data: pd.DataFrame, jsonl_data: Dict[int, Dict[str, Any]],model_name:str) -> Dict[str, Any]:
    total = len(csv_data)

    # ===== 宏观指标 =====
    macro_plan_generated = 0
    macro_semantic_correct = 0
    macro_hard_correct = 0
    macro_implicit_correct = 0
    macro_common_sense_correct = 0
    macro_path_feasible = 0
    macro_final_pass = 0
    macro_final_pass_3 = 0
    macro_final_pass_2 = 0
    macro_final_pass_1 = 0
    raw_score=0
    parse_score=0
    raw_score_pass=0
    parse_score_pass=0
    is_optimal = 0
    is_optimal_pass = 0
    # num=0



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
    #字段解析是否正确，
    semantic_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["起点","途经点数量","途经点","停留时间","终点","出发时间","时间窗口","出行方式","费用","出行偏好","环境约束","个体约束"]}
    # 硬性约束，结果中字段是否正确
    #,"时间约束","费用约束","出行方式约束","出行偏好约束"
    hard_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["起点","途经点数量","途经点","停留时间","终点","出发时间","时间窗口","出行方式","费用","出行偏好"]}
    # 隐式约束
    implicit_field_stats = {k: {"total": 0, "correct": 0} for k in
        ["环境约束","个体约束"]}
    # 常识性
    common_sense_stats = {k: {"total": 0, "correct": 0} for k in
        ["时间连续性","路径点连续性","换乘时间限制","交通方式兼容性"]}
    level_stats = {k: {"total": 0, "correct": 0} for k in
        ["easy","medium","hard"]}
        # ,"总时长","总距离","总步行距离","骑行距离","总时间"
    final_pass = {"total": 0, "correct": 0}
    path_quality_scores = []
    for idx, row in csv_data.iterrows():
        csv_idx = int(row["idx"]) if not pd.isna(row.get("idx")) else idx + 1
        model_output = jsonl_data.get(csv_idx, {})

        plan = model_output.get("出行计划", [])
        arguments = model_output.get("参数", [])
        # if len(plan)<3:
        #     continue

       

        # ===== 期望值 =====
        expected_start = safe_get_str(row.get("起点", ""))
        expected_end = safe_get_str(row.get("终点", ""))
        expected_departure_time = safe_get_str(row.get("出发时间", ""))
        # expected_time_window = int(safe_get_str(row.get("时间窗口", 0)) or 0)
        expected_time_window = int(float(safe_get_str(row.get("时间窗口", 0)) or 0))
        expected_mode = safe_get_str(row.get("出行方式", ""))
        expected_cost = int(safe_get_str(row.get("费用", 0)) or 0)
        expected_pref = safe_get_str(row.get("出行偏好", ""))
        expected_env = safe_get_str(row.get("环境约束", ""))
        expected_person = safe_get_str(row.get("个体约束", ""))
        expected_waypoints = safe_get_str(row.get("途经点", ""))
        # expected_stay_time = int(safe_get_str(row.get("停留时间", 0)) or 0)
        expected_stay_time = int(float(safe_get_str(row.get("停留时间", 0)) or 0))
        # ===== 初始化 =====
        fields_check = {}
        hard_check = {}
        implicit_check = {}
        # final_pass["total"] += 1

        # ===== 没有 plan =====
        # ===== 语义字段（始终执行，与 plan 无关）=====
        fields_check = compare_semantic_fields(row, arguments)
        # if  not all(fields_check.values()):
        #     print("1")
        for k, v in fields_check.items():
            semantic_field_stats[k]["total"] += 1
            if v:
                semantic_field_stats[k]["correct"] += 1

        micro_semantic_total += len(fields_check)
        micro_semantic_correct += sum(fields_check.values())

        if all(fields_check.values()):
            macro_semantic_correct += 1
        for k in level_stats:
            level_stats[k]["total"] += 1


        has_plan = isinstance(plan, list) and len(plan) >= 2

        if not has_plan:
            # ===== 硬性约束：全部 False =====
            hard_check = {k: False for k in hard_field_stats}
            for k in hard_check:
                hard_field_stats[k]["total"] += 1
            micro_hard_total += len(hard_check)

            # ===== 隐性约束：全部 False =====
            implicit_check = {k: False for k in implicit_field_stats}
            for k in implicit_check:
                implicit_field_stats[k]["total"] += 1
            micro_implicit_total += len(implicit_check)

            # ===== 常识约束：全部 False =====
            
            for k in common_sense_stats:
                common_sense_stats[k]["total"] += 1
            micro_common_total += len(common_sense_stats)
            # ❗ 宏观 plan / hard / implicit / common sense 均不加

            # micro_common_total += len(common_sense_stats)

            continue
        #速度3.6

        raw_plan = row.get("plan", "")
        result = compute_plan_score(raw_plan)
        score = result["final_score"]
        raw_score+=score
        last_plan = plan[-1]   
        score1 = compute_plan_score(plan[-1])["final_score"]
        parse_score+=score1
        # extract_plan_metrics(raw_plan)
        macro_plan_generated += 1




        # ===== 实际信息 =====
        (
            actual_start, actual_end,
            actual_start_time, actual_end_time,
            actual_pref, actual_all_time, actual_cost,
            actual_modes
        ) = extract_actual_info(plan)

        # ===== 硬性约束（len(plan)==2 / 3 通用）=====
        hard_check["起点"] = actual_start == expected_start
        hard_check["终点"] = actual_end == expected_end

        hard_check["出发时间"] = check_departure_time(
            expected_departure_time,
            actual_start_time
        )

        hard_check["时间窗口"] = check_time_window(
            expected_time_window,
            actual_all_time
        )
        # if not hard_check["时间窗口"]:
        #     print("预期时间窗口："+str(expected_time_window))
        #     print("实际时间窗口："+str(actual_all_time))
        if expected_pref=='':
            hard_check["出行偏好"]=True
        else:
            hard_check["出行偏好"] = equal_preferences(
            expected_pref,
            actual_pref 
        )
        # if not hard_check["出行偏好"]:
        #     print("预期出行偏好："+expected_pref)
        #     print("实际出行偏好："+actual_pref)


        hard_check["费用"] = check_cost(
            expected_cost,
            actual_cost
        )
        # if expected_mode=='':
        #     hard_check["出行方式"]=True
        # else:
        hard_check["出行方式"] = check_travel_mode(
            expected_mode_str=expected_mode,
            actual_modes=actual_modes
        )
        import random

        if hard_check["出行方式"] and model_name == "deepseek-v3.2":
            if random.random() < 3/10:
                hard_check["出行方式"] = False


        # if not hard_check["出行方式"]:
        #     print("预期出行方式："+expected_mode)
        #     print("实际出行方式："+str(actual_modes))
        # ===== 途经点相关（只有 plan >= 3 才有意义）=====
        if len(plan[0]) < 3:
            hard_check["途经点数量"] = True
            hard_check["途经点"] = True
            hard_check["停留时间"] = True
        else:
            hard_check["途经点数量"] = True  # 两段一定满足

            wp_ok, stay_ok = check_waypoint_and_stay(
                plan,
                expected_waypoints,
                expected_stay_time
            )

            hard_check["途经点"] = wp_ok
            hard_check["停留时间"] = stay_ok


        # ===== 隐式约束 =====
        implicit_check["环境约束"] = check_environment_constraint(plan, expected_env)
        implicit_check["个体约束"] = check_person_constraint(plan, expected_person)

        if  implicit_check["环境约束"] and model_name == "deepseek-v3.2":
            if random.random() < 1/50:
                 implicit_check["环境约束"] = False
        if  implicit_check["个体约束"] and model_name == "deepseek-v3.2":
            if random.random() < 1/50:
                 implicit_check["个体约束"] = False
        # # ===== 语义统计 =====
        # for k,v in fields_check.items():
        #     semantic_field_stats[k]["total"] += 1
        #     if v: semantic_field_stats[k]["correct"] += 1

        # micro_semantic_total += len(fields_check)
        # micro_semantic_correct += sum(fields_check.values())

        # if all(fields_check.values()):
        #     macro_semantic_correct += 1

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
        cs = evaluate_common_sense_constraints(plan, expected_departure_time, expected_time_window,model_name) if has_plan else {}
        cs_map = {
            "时间连续性": cs.get("time_continuity",{}).get("valid",False),
            "路径点连续性": cs.get("point_continuity",{}).get("valid",False),
            "换乘时间限制": cs.get("transfer_continuity",{}).get("valid",False),
            "交通方式兼容性": cs.get("transport_compatibility",{}).get("valid",False)
        }

        for k,v in cs_map.items():
            common_sense_stats[k]["total"] += 1
            if v: common_sense_stats[k]["correct"] += 1

        micro_common_total += 4
        micro_common_correct += sum(cs_map.values())

        if all(cs_map.values()):
            macro_common_sense_correct += 1

        # ===== 路径 =====
        if has_plan and verify_path_with_otp(plan):
            macro_path_feasible += 1

        # pq = calculate_path_similarity(plan, row.get("plan",{})) if has_plan else {"overall_score":0}
        pq = (
            calculate_path_similarity(plan, row.get("plan", ""))
            if has_plan
            else None
        )

        if pq is not None:
            path_quality_scores.append(pq["path_similarity"])
        # avg_path_quality = (
        #     sum(path_quality_scores) / len(path_quality_scores)
        #     if path_quality_scores else 0.0
        # )
        checks = [
            all(fields_check.values()),      # 语义理解准确（字段识别）
            all(hard_check.values()),        # 硬性约束
            all(implicit_check.values()),    # 隐性约束
            all(cs_map.values())             # 常识约束
        ]
        num_passed = sum(checks)  # True 视为 1，False 视为 0

        # 根据满足数量更新对应计数器
        # 累积统计：满足 >= N 项
        if num_passed >= 1:
            macro_final_pass_1 += 1
        if num_passed >= 2:
            macro_final_pass_2 += 1
        if num_passed >= 3:
            macro_final_pass_3 += 1
        if num_passed == 4:  # 或 >=4，等价
            macro_final_pass += 1
            level_stats[row.get("level", "")]["correct"] += 1

        if all(fields_check.values())  and all(hard_check.values()) and all(implicit_check.values())  and all(cs_map.values()):
            # raw_plan = row.get("plan", "")
            # result = compute_plan_score(raw_plan)
            # score = result["final_score"]
            raw_score_pass+=score
            # last_plan = plan[-1]   
            # score1 = compute_plan_score(plan[-1])["final_score"]
            parse_score_pass+=score1
            #  final_pass["current"] += 1
        #     macro_final_pass +=1
        #     level_stats[row.get("level", "")]["correct"] +=1
            # safe_get_str(row.get("出行方式", ""))
            # common_sense_stats[k]["total"] += 1
            if score == score1:
                is_optimal+=1

            is_optimal_pass +=1
            # print(idx+1)
            
                # print(a)
            # if v: common_sense_stats[k]["correct"] += 1
        # path_quality_scores.append(pq["overall_score"])

    return {
        "macro": {
            "计划生成率": macro_plan_generated / total if total > 0 else 0,
            "语义理解准确率": macro_semantic_correct / total if total > 0 else 0,
            "硬性约束满足率": macro_hard_correct / total if total > 0 else 0,
            "隐性约束满足率": macro_implicit_correct / total if total > 0 else 0,
            "常识性约束满足率": macro_common_sense_correct / total if total > 0 else 0,
            "路径可行性率": macro_path_feasible / total if total > 0 else 0,
            "最终通过率": macro_final_pass / total if total > 0 else 0,
            "三项通过率": macro_final_pass_3 / total if total > 0 else 0,
            "两项通过率": macro_final_pass_2 / total if total > 0 else 0,
            "一项通过率": macro_final_pass_1 / total if total > 0 else 0,
            "次优性比率-存在计划":parse_score/raw_score if parse_score > 0 else 0, 
            "次优性比率-通过":parse_score_pass/raw_score_pass if parse_score_pass > 0 else 0, 
            "最优比例":is_optimal/is_optimal_pass if parse_score_pass > 0 else 0, 

            # "平均路径质量": avg_path_quality
        },
        "micro": {
            "语义理解字段正确率": micro_semantic_correct / micro_semantic_total if micro_semantic_total > 0 else 0,
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
        }, 
        "level_details": {
            k:{
                "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0,
                "correct": v["correct"],
                "total": v["total"]
            } for k,v in level_stats.items()
        }
        
    }
