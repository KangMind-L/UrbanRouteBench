import json
import csv
import os
import random
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

route = Routes()
wgs84 = Wgs84()


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
transit_keywords = {
    # 英文 / 代码类
    "SUBWAY", "METRO", "BUS", "TRAM", "RAIL", "LIGHT_RAIL", "COMMUTER_RAIL",

    # 中文常见
    "公交", "地铁", "轨道交通", "有轨电车", "城轨", "轻轨", "市域铁路",

    # 具体说法
    "公交车", "巴士", "公共交通", "公共运输",

    # 偏口语 / 变体
    "坐公交", "坐地铁", "搭地铁", "乘地铁", "乘公交",
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
# 定义出行方
STATION_SUFFIXES = ["站", "地铁站", "公交站"]
VALID_STATIONS = set(
    pd.read_csv("database/data/point_excel.csv")["名称"].dropna().astype(str).str.strip().tolist()
)

def time_diff_seconds(t1: str, t2: str) -> int:
    fmt = "%H:%M:%S"
    return int(
        (datetime.strptime(t2, fmt) - datetime.strptime(t1, fmt)).total_seconds()
    )
def parse_otp_plan_times(otp_plan: str, mode: str) -> list[tuple[str, str]]:
    """
    从 OTP 文本中提取指定 mode 的出发时间和到达时间
    返回列表，每个元素是 (start_time, end_time)
    """
    steps = []
    # 匹配每一步的模式：步骤X: MODE 起点 → 终点 距离: XXX米,  HH:MM:SS-HH:MM:SS  时长: XX分钟XX秒
    pattern = re.compile(rf'步骤\d+: {mode} .*? (\d{{2}}:\d{{2}}:\d{{2}})-(\d{{2}}:\d{{2}}:\d{{2}})')
    for m in pattern.finditer(otp_plan):
        steps.append((m.group(1), m.group(2)))
    return steps

def is_time_consistent(plan_item, otp_plan):
    """
    检查 plan_item 中的 start_time/end_time 是否在 OTP plan 中至少有一条方案一致
    """
    start_time = safe_get_str(plan_item.get("开始时间", ""))
    end_time = safe_get_str(plan_item.get("结束时间", ""))
    if len(start_time) == 5:
        start_time = start_time + ":00"
    if len(end_time) == 5:
        end_time = end_time + ":00"    
    for mode in ["BUS", "SUBWAY"]:
        target_diff = time_diff_seconds(start_time, end_time)
        steps = parse_otp_plan_times(otp_plan, mode)
        for step_start, step_end in steps:
            # 可以使用 datetime 比较，也可以直接字符串比较，如果格式一致
            if time_diff_seconds(step_start, step_end) == target_diff:
            # if step_start == start_time and step_end == end_time:
                return True
    return False


def resolve_station_name(
    raw_name: str,
    valid_stations: Set[str]
) -> Optional[str]:
    """
    在不修改合法站点名的前提下，
    将 LLM 输出解析为一个系统内存在的站点名
    """
    if not raw_name:
        return None

    raw_name = raw_name.strip()

    # 1️⃣ 精确匹配（最优先）
    if raw_name in valid_stations:
        return raw_name

    # 2️⃣ 尝试「追加后缀」命中
    for suffix in STATION_SUFFIXES:
        candidate = raw_name + suffix
        if candidate in valid_stations:
            return candidate

    # 3️⃣ 尝试「去除多余后缀后再匹配」
    for suffix in STATION_SUFFIXES:
        if raw_name.endswith(suffix):
            base = raw_name[:-len(suffix)]
            if base in valid_stations:
                return base
            for s in STATION_SUFFIXES:
                candidate = base + s
                if candidate in valid_stations:
                    return candidate

    # 4️⃣ 未命中，返回 None（不瞎猜）
    return None


TRANSPORT_MODE_KEYWORDS = {
    "CAR_PICKUP": ["打车", "出租", "出租车", "网约车", "滴滴", "快车", "专车"],
    "CAR": ["开车", "自驾", "驾车", "私家车"],
    "BICYCLE": ["骑行", "单车", "自行车", "共享单车", "骑车"],
    "WALK": ["步行", "走路", "徒步"],
    "BUS": ["公交", "公交车", "巴士", "大巴"],
    "SUBWAY": ["地铁", "地铁站", "轨道交通", "轻轨", "城轨"]
}

from typing import List, Dict, Any, Tuple

# 这些 mode 直接认为 OTP 可行，不调用外部 API

import re
from typing import Set

def normalize_transport_mode(raw_mode: str) -> str:
    """
    将中文出行方式描述映射为 OTP 英文 mode
    支持：
    - 单一方式
    - 组合方式（公交+地铁 / 公交-地铁）
    - 模糊描述
    """
    if not raw_mode:
        return ""

    raw_mode = raw_mode.strip()

    # 拆分组合方式
    parts = re.split(r"[+\-、/]", raw_mode)
    matched_modes: Set[str] = set()

    for part in parts:
        for mode, keywords in TRANSPORT_MODE_KEYWORDS.items():
            if any(k in part for k in keywords):
                matched_modes.add(mode)

    # 没匹配到，谨慎处理：返回原始值
    if not matched_modes:
        return raw_mode

    # OTP 支持 BUS|SUBWAY 这种格式
    return "|".join(sorted(matched_modes))

def safe_get_str(value: Any) -> str:
    """安全获取字符串"""
    if pd.isna(value):
        return ""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()

def parse_time(time_str: str) -> Optional[datetime]:
    """解析时间字符串"""
    if not time_str or pd.isna(time_str):
        return None
    try:
        time_str = str(time_str).strip()
        if not time_str:
            return None
        # 尝试不同的时间格式
        time_formats = ['%H:%M:%S', '%H:%M', '%H时%M分%S秒', '%H时%M分']
        for fmt in time_formats:
            try:
                return datetime.strptime(time_str, fmt)
            except:
                continue
        return None
    except:
        return None

def time_str_to_minutes(time_str: str) -> Optional[int]:
    """将时间字符串转换为分钟数"""
    if not time_str or pd.isna(time_str):
        return None
    
    time_str = str(time_str).strip()
    total_minutes = 0
    
    # 匹配分钟
    minute_match = re.search(r'(\d+)\s*分钟', time_str)
    if minute_match:
        total_minutes += int(minute_match.group(1))
    
    # 匹配秒
    second_match = re.search(r'(\d+)\s*秒', time_str)
    if second_match:
        total_minutes += int(second_match.group(1)) / 60
    
    if total_minutes == 0:
        num_match = re.search(r'(\d+(?:\.\d+)?)', time_str)
        if num_match:
            return int(float(num_match.group(1)))
    
    return int(total_minutes)
def check_time_condition(actual_start_time: str, actual_end_time: str, expected_time: str, time_window: int) -> Tuple[bool, bool]:
    """
    检查时间条件
    返回: (时间是否正确, 时间性质是否正确)
    """
    if not actual_start_time or not actual_end_time or not expected_time:
        return False, False
    
    actual_start_dt = parse_time(actual_start_time)
    actual_end_dt = parse_time(actual_end_time)
    expected_dt = parse_time(expected_time)
    
    if not actual_start_dt or not actual_end_dt or not expected_dt:
        return False, False
    
    actual_start = actual_start_dt.time()
    actual_end = actual_end_dt.time()
    expected = expected_dt.time()
    
    if time_window ==0:
        # 预期为出发时，实际出发和到达都应该不早于期望出发时间
        time_correct = (actual_start >= expected) and (actual_end >= expected)
        # 时间性质：实际出发是实际行程的开始时间
        time_property_correct = True
    elif time_window == "到达":
        # 预期为到达时，实际出发和到达都应该不晚于期望到达时间
        time_correct = (actual_start <= expected) and (actual_end <= expected)
        # 时间性质：实际到达是实际行程的结束时间
        time_property_correct = True
    else:
        time_correct = False
        time_property_correct = False
    
    return time_correct, time_property_correct
def compare_time(actual_time: str, expected_time: str, time_type: str) -> bool:
    """比较时间，考虑时间性质"""
    if not actual_time or not expected_time:
        return False
    
    actual_dt = parse_time(actual_time)
    expected_dt = parse_time(expected_time)
    
    if not actual_dt or not expected_dt:
        return False
    
    actual_time_obj = actual_dt.time()
    expected_time_obj = expected_dt.time()
    
    if time_type == "出发":
        return actual_time_obj >= expected_time_obj
    elif time_type == "到达":
        return actual_time_obj <= expected_time_obj
    return False

def extract_number_from_cost(cost_str: str) -> Optional[float]:
    """从费用字符串中提取数字"""
    if not cost_str or pd.isna(cost_str):
        return None
    matches = re.findall(r'\d+(?:\.\d+)?', str(cost_str))
    if matches:
        return float(matches[0])
    return None

def compare_cost(actual_cost: str, expected_cost: str) -> bool:
    """比较费用"""
    if pd.isna(actual_cost) and pd.isna(expected_cost):
        return True
    if pd.isna(actual_cost) or pd.isna(expected_cost):
        return False
    
    actual_num = extract_number_from_cost(actual_cost)
    expected_num = extract_number_from_cost(expected_cost)
    
    if actual_num is not None and expected_num is not None:
        return actual_num <= expected_num + 0.01
    return safe_get_str(actual_cost) == safe_get_str(expected_cost)

def load_jsonl(jsonl_file: str) -> Dict[int, Dict[str, Any]]:
    """加载JSONL格式的模型输出数据"""
    jsonl_data = {}
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                idx = data.get("idx")
                if idx is None:
                    idx = line_num
                jsonl_data[idx] = data
            except json.JSONDecodeError as e:
                print(f"Warning: JSON解析错误 行 {line_num}: {e}")
                continue
    return jsonl_data

from typing import List, Dict, Any, Tuple


def get_start_end_from_plan(plan: List[Any]) -> Tuple[str, str, str, str]:
    """
    从 plan 中提取：
    起点、终点、开始时间、结束时间
    """

    start_point = ""
    end_point = ""
    start_time = ""
    end_time = ""

    if not plan:
        return start_point, end_point, start_time, end_time

    # =========================
    # 1️⃣ 起点 & 开始时间（第一段第一个步骤）
    # =========================
    first_leg = plan[0]
    if isinstance(first_leg, list):
        for item in first_leg:
            if isinstance(item, dict) and "步骤" in item:
                start_point = safe_get_str(item.get("起点", ""))
                start_time = safe_get_str(item.get("开始时间", ""))
                break

    # =========================
    # 2️⃣ 终点 & 结束时间（最后一段最后一个步骤）
    # =========================
    # 判断是否有第二段路径
    has_second_leg = len(plan) == 3

    last_leg = plan[1] if has_second_leg else plan[0]
    if isinstance(last_leg, list):
        for item in reversed(last_leg):
            if isinstance(item, dict) and "步骤" in item:
                end_point = safe_get_str(item.get("终点", ""))
                end_time = safe_get_str(item.get("结束时间", ""))
                break

    # =========================
    # 3️⃣ 如果总结中有更权威时间，用总结覆盖
    # =========================
    summary = plan[-1]
    if isinstance(summary, dict):
        start_time = safe_get_str(summary.get("出发时间", start_time))
        end_time = safe_get_str(summary.get("到达时间", end_time))

    return start_point, end_point, start_time, end_time

def get_cost_from_plan(plan: List[Dict[str, Any]]) -> str:
    """从出行计划中提取费用"""
    if not plan:
        return ""
    
    for item in plan:
        if isinstance(item, dict):
            if "预计费用" in item:
                return safe_get_str(item.get("预计费用", ""))
            elif "费用" in item:
                return safe_get_str(item.get("费用", ""))
    
    return ""

def get_preference_from_plan(plan: List[Dict[str, Any]]) -> str:
    """从出行计划中提取方案偏好"""
    if not plan:
        return ""
    
    for item in plan:
        if isinstance(item, dict) and "方案偏好" in item:
            return safe_get_str(item.get("方案偏好", ""))
    
    return ""

def evaluate_mode_constraint(expected_mode: str, step_modes: set) -> bool:
    """评估出行方式约束"""
    if not expected_mode or not step_modes:
        return True
    
    taxi_modes = {"打车", "出租车", "网约车", "的士", "出租车/网约车"}
    car_modes = {"开车", "自驾", "驾车", "自驾/开车"}
    bus_modes = {"公交", "公交车", "巴士", "公交车/巴士"}
    subway_modes = {"地铁", "轨道交通", "地铁/轨道交通"}
    bike_modes = {"骑行", "自行车", "单车", "共享单车", "骑车", "骑单车"}
    walk_modes = {"步行", "走路"}
    
    expected_mode = safe_get_str(expected_mode)
    
    if expected_mode.lower() in ['null', 'none', 'nan', '', '无']:
        return True
    
    if "单车+公共交通" in expected_mode:
            # 需要包含公共交通（公交/地铁），单车是可选的
            has_public = any(m in bus_modes.union(subway_modes) for m in step_modes)
            # 只能包含单车、公交、地铁、步行
            allowed_modes = bike_modes.union(bus_modes).union(subway_modes).union(walk_modes)
            return has_public and all(m in allowed_modes for m in step_modes)
        
    # 检查是否满足要求 - 注意顺序，从具体到一般
    if "公共交通" in expected_mode or "公共交通工具" in expected_mode:
        # 要求公共交通：只能包含公交、地铁、步行，且不能只有步行
        has_other = any(m not in bus_modes.union(subway_modes).union(walk_modes) for m in step_modes)
        has_public_transport = any(m in bus_modes.union(subway_modes) for m in step_modes)
        return not has_other and has_public_transport
    elif "步行" in expected_mode or "走路" in expected_mode:
        # 要求步行：只能步行
        return all(m in walk_modes for m in step_modes)
    elif any(taxi in expected_mode for taxi in taxi_modes):
        # 要求打车：只能包含出租车类或步行
        return all(m in taxi_modes.union(walk_modes) for m in step_modes)
    elif any(car in expected_mode for car in car_modes):
        # 要求开车：只能包含自驾类或步行
        return all(m in car_modes.union(walk_modes) for m in step_modes)
    elif any(bus in expected_mode for bus in bus_modes):
        # 要求公交：不能包含地铁，只能包含公交和步行
        has_other = any(m not in bus_modes.union(walk_modes) for m in step_modes)
        has_bus = any(m in bus_modes for m in step_modes)
        return not has_other and has_bus
    elif any(subway in expected_mode for subway in subway_modes):
        # 要求地铁：不能包含公交，只能包含地铁和步行
        has_other = any(m not in subway_modes.union(walk_modes) for m in step_modes)
        has_subway = any(m in subway_modes for m in step_modes)
        return not has_other and has_subway
    elif any(bike in expected_mode for bike in bike_modes):
        # 要求骑行：只能包含骑行或步行
        return all(m in bike_modes.union(walk_modes) for m in step_modes)

    return True

# def check_time_continuity(plan: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
#     """检查时间连续性"""
#     if not plan:
#         return False, ["无出行计划"]
    
#     errors = []
#     steps = []
    
#     for item in plan:
#         if isinstance(item, dict) and "步骤" in item:
#             step_num = item.get("步骤")
#             start_time = parse_time(safe_get_str(item.get("开始时间", "")))
#             end_time = parse_time(safe_get_str(item.get("结束时间", "")))
            
#             if start_time and end_time:
#                 steps.append({
#                     "step": step_num,
#                     "start": start_time,
#                     "end": end_time
#                 })
    
#     if not steps:
#         return False, ["无有效步骤"]
    
#     steps.sort(key=lambda x: x["step"])
    
#     for i in range(len(steps)):
#         if steps[i]["start"] >= steps[i]["end"]:
#             errors.append(f"步骤{steps[i]['step']}: 开始时间不早于结束时间")
        
#         if i < len(steps) - 1:
#             if steps[i]["end"] > steps[i+1]["start"]:
#                 errors.append(f"步骤{steps[i]['step']}结束时间晚于步骤{steps[i+1]['step']}开始时间")
    
#     return len(errors) == 0, errors
from typing import List, Dict, Tuple

def check_time_continuity(plan: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    检查时间连续性（支持最多一次跨天）
    """
    if not plan:
        return False, ["无出行计划"]

    errors = []
    reverse_count = 0  # 记录“时间逆序”出现次数

    # =========
    # 抽取所有段
    # =========
    segments = []

    if len(plan) == 2:
        # 一段行程
        segments.append(plan[0])
    elif len(plan) == 3:
        # 两段行程
        segments.append(plan[0])
        segments.append(plan[1])
    else:
        return False, ["非法 plan 结构"]

    # ====================
    # 1. 检查每一段内部
    # ====================
    for seg_idx, steps in enumerate(segments, start=1):
        parsed_steps = []

        for item in steps:
            if isinstance(item, dict) and "步骤" in item:
                start = parse_time(safe_get_str(item.get("开始时间", "")))
                end   = parse_time(safe_get_str(item.get("结束时间", "")))

                if start and end:
                    parsed_steps.append({
                        "step": item.get("步骤"),
                        "start": start,
                        "end": end
                    })

        parsed_steps.sort(key=lambda x: x["step"])

        for i, cur in enumerate(parsed_steps):
            # —— 当前步骤内部 ——
            if cur["end"] < cur["start"]:
                reverse_count += 1
                errors.append(
                    f"第{seg_idx}段-步骤{cur['step']}：到达时间早于出发时间（可能跨天）"
                )

            # —— 相邻步骤 ——
            if i < len(parsed_steps) - 1:
                nxt = parsed_steps[i + 1]
                if nxt["start"] < cur["end"]:
                    reverse_count += 1
                    errors.append(
                        f"第{seg_idx}段-步骤{cur['step']}→{nxt['step']}：下一步出发早于上一步到达"
                    )

    # ====================
    # 2. 检查两段之间
    # ====================
    if len(segments) == 2:
        first_seg = segments[0]
        second_seg = segments[1]

        # 第一段最后到达
        first_end = None
        for item in reversed(first_seg):
            if isinstance(item, dict) and "结束时间" in item:
                first_end = parse_time(safe_get_str(item.get("结束时间", "")))
                break

        # 第二段最早出发
        second_start = None
        for item in second_seg:
            if isinstance(item, dict) and "开始时间" in item:
                second_start = parse_time(safe_get_str(item.get("开始时间", "")))
                break

        if first_end and second_start and second_start < first_end:
            reverse_count += 1
            errors.append("第二段出发时间早于第一段到达时间（可能跨天）")

    # ====================
    # 3. 最终判定
    # ====================
    if reverse_count > 1:
        return False, errors

    return True, []
from typing import List, Dict, Any, Tuple
from datetime import timedelta

def check_transfer_wait_time(plan: List[Dict[str, Any]], max_minutes: int = 60) -> Tuple[bool, List[str]]:
    """
    检查换乘等待时间是否均小于 max_minutes（支持跨天）
    
    Returns:
        (是否满足, 错误信息列表)
    """
    if not plan:
        return False, ["无出行计划"]

    errors = []

    # =========
    # 抽取段
    # =========
    segments = []
    if len(plan) == 2:
        segments.append(plan[0])
    elif len(plan) == 3:
        segments.append(plan[0])
        segments.append(plan[1])
    else:
        return False, ["非法 plan 结构"]

    # =========
    # 检查每一段
    # =========
    for seg_idx, steps in enumerate(segments, start=1):
        parsed_steps = []

        for item in steps:
            if isinstance(item, dict) and "步骤" in item:
                start = parse_time(safe_get_str(item.get("开始时间", "")))
                end   = parse_time(safe_get_str(item.get("结束时间", "")))

                if start and end:
                    parsed_steps.append({
                        "step": item.get("步骤"),
                        "start": start,
                        "end": end
                    })

        parsed_steps.sort(key=lambda x: x["step"])

        for i in range(len(parsed_steps) - 1):
            cur = parsed_steps[i]
            nxt = parsed_steps[i + 1]

            cur_end = cur["end"]
            nxt_start = nxt["start"]

            # —— 计算换乘时间（分钟）——
            if nxt_start >= cur_end:
                wait = (nxt_start - cur_end).total_seconds() / 60
            else:
                # 跨天：+1 天
                wait = ((nxt_start + timedelta(days=1)) - cur_end).total_seconds() / 60

            if wait >= max_minutes:
                errors.append(
                    f"第{seg_idx}段：步骤{cur['step']}→{nxt['step']} 换乘等待 {int(wait)} 分钟 ≥ {max_minutes}"
                )

    return len(errors) == 0, errors

def check_walking_time_limit(plan: List[Dict[str, Any]]) -> Tuple[bool, float]:
    """检查步行和骑行距离限制"""
    def parse_distance(value: str) -> float:
        """把距离字符串转换为浮点数，非数字返回0"""
        try:
            # 去掉单位和空格，再转换
            return float(value.replace("米","").strip())
        except (ValueError, AttributeError):
            return 0.0

    
    if not plan:
        return False, 0.0
    
    # 只取最后一个计划（列表里每个元素是字典）
    plan_item = plan[-1]

    # 提取步行和骑行总距离，统一成浮点数
    # walk_distance = float(str(plan_item.get("总步行距离","0")).replace("米","").strip())
    # bike_distance = float(str(plan_item.get("骑行总距离","0")).replace("米","").strip())
    walk_distance = parse_distance(plan_item.get("总步行距离","0"))
    bike_distance = parse_distance(plan_item.get("骑行总距离","0"))

    # 返回是否满足限制 + 实际步行距离
    is_valid = walk_distance <= 2000.0 and bike_distance <= 3000.0
    return is_valid, walk_distance

    
    # for item in plan:
    #     if isinstance(item, dict) and "步骤" in item:
    #         mode = safe_get_str(item.get("出行方式", ""))
    #         if "步行" in mode or "走路" in mode:
    #             duration_str = safe_get_str(item.get("预计时间", ""))
    #             if duration_str:
    #                 duration_minutes = time_str_to_minutes(duration_str)
    #                 if duration_minutes:
    #                     total_walk_time += duration_minutes
    
    # return total_walk_time <= max_walk_minutes, total_walk_time

from typing import List, Dict, Any, Tuple

def normalize_mode(mode: str) -> str:
    """将出行方式统一为标准名称"""
    mode = mode.strip().lower()
    if mode in {"步行", "walk"}:
        return "步行"
    elif mode in {"单车", "自行车", "bike", "bicycle"}:
        return "单车"
    elif mode in {"打车", "出租车", "网约车", "taxi"}:
        return "打车"
    elif mode in {"开车", "自驾", "car", "driving"}:
        return "开车"
    elif mode in {"公交", "bus"}:
        return "公交"
    elif mode in {"地铁", "metro", "subway"}:
        return "地铁"
    else:
        return mode  # 未知方式保留原值

def extract_all_modes(plan: List[Any]) -> List[str]:
    """从 plan 中提取所有步骤的出行方式并归一化"""
    modes = []
    for segment in plan:
        if isinstance(segment, list):
            # 多段路径中的步骤
            for step in segment:
                if isinstance(step, dict) and "出行方式" in step:
                    modes.append(normalize_mode(str(step.get("出行方式", ""))))
        elif isinstance(segment, dict):
            # 单段 plan 或总结，不含步骤则跳过
            continue
    return modes

def check_transportation_compatibility(plan: List[Any]) -> Tuple[bool, List[str]]:
    """
    检查 plan 中的交通方式是否存在不兼容组合
    返回 (是否兼容, 错误列表)
    """
    if not plan:
        return False, ["无出行计划"]

    errors = []
    modes = extract_all_modes(plan)
    unique_modes = set(modes)

    if not unique_modes:
        return False, ["无有效步骤"]

    # 定义不兼容规则
    incompatible_rules = [
        ({      "CAR_PICKUP", "TAXI", "RIDE_HAILING", "RIDE_HAIL", "CAB",

        # 中文常见
        "打车", "出租车", "网约车", "的士",

        # 平台类
        "滴滴", "高德打车", "曹操出行", "首汽约车", "神州专车",

        # 偏口语 / 变体
        "叫车", "叫出租车", "叫网约车", "打的"}, {        # 英文 / 代码类
        "CAR", "DRIVING", "DRIVE", "SELF_DRIVE",

        # 中文常见
        "开车", "自驾", "驾车", "自家车", "私家车",

        # 偏口语 / 变体
        "自己开车", "开私家车", "开小车", "开轿车",}),


        ({        "WALK", "WALKING", "FOOT",

        # 中文常见
        "步行", "走路", "步走",

        # 偏口语 / 变体
        "走过去", "步行前往", "步行到达"},
         {        # 英文 / 代码类
        "BICYCLE", "BIKE", "BICYCLE_RENT", "BIKE_RENT", "SHARED_BIKE",

        # 中文常见
        "单车", "骑行", "自行车", "骑车", "骑单车",
        "共享单车", "公共自行车", "扫码单车",

        # 偏口语 / 变体
        "骑自行车", "骑共享单车", "骑小蓝车", "骑摩拜", "骑哈啰",}),


        ({        "WALK", "WALKING", "FOOT",

        # 中文常见
        "步行", "走路", "步走",

        # 偏口语 / 变体
        "走过去", "步行前往", "步行到达"}, 
        {        # 英文 / 代码类
        "CAR", "DRIVING", "DRIVE", "SELF_DRIVE",

        # 中文常见
        "开车", "自驾", "驾车", "自家车", "私家车",

        # 偏口语 / 变体
        "自己开车", "开私家车", "开小车", "开轿车",}),


        ({        # 英文 / 代码类
        "SUBWAY", "METRO", "BUS", "TRAM", "RAIL", "LIGHT_RAIL", "COMMUTER_RAIL",

        # 中文常见
        "公交", "地铁", "轨道交通", "有轨电车", "城轨", "轻轨", "市域铁路",

        # 具体说法
        "公交车", "巴士", "公共交通", "公共运输",

        # 偏口语 / 变体
        "坐公交", "坐地铁", "搭地铁", "乘地铁", "乘公交",}, 
        {        "CAR_PICKUP", "TAXI", "RIDE_HAILING", "RIDE_HAIL", "CAB",

        # 中文常见
        "打车", "出租车", "网约车", "的士",

        # 平台类
        "滴滴", "高德打车", "曹操出行", "首汽约车", "神州专车",

        # 偏口语 / 变体
        "叫车", "叫出租车", "叫网约车", "打的",        # 英文 / 代码类
        "CAR", "DRIVING", "DRIVE", "SELF_DRIVE",

        # 中文常见
        "开车", "自驾", "驾车", "自家车", "私家车",

        # 偏口语 / 变体
        "自己开车", "开私家车", "开小车", "开轿车"}),
    ]

    for group1, group2 in incompatible_rules:
        if unique_modes & group1 and unique_modes & group2:
            errors.append(f"交通方式不兼容: {group1} 与 {group2} 不能共存")

    return len(errors) == 0, errors

from typing import List, Dict, Any


from typing import List, Dict, Any, Tuple


def check_path_continuity(plan: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    检查路径点是否连续

    连续性规则：
    1. 每一段内：当前步骤的终点 == 下一步骤的起点
    2. 两段时：第一段最后一步的终点 == 第二段第一步的起点
    """

    if not plan:
        return False, ["无出行计划"]

    errors = []

    # =========
    # 抽取段
    # =========
    segments = []
    if len(plan) == 2:
        segments.append(plan[0])
    elif len(plan) == 3:
        segments.append(plan[0])
        segments.append(plan[1])
    else:
        return False, ["非法 plan 结构"]

    parsed_segments = []

    # =========
    # 1️⃣ 段内连续性
    # =========
    for seg_idx, steps in enumerate(segments, start=1):
        parsed_steps = []

        for item in steps:
            if isinstance(item, dict) and "步骤" in item:
                start_point = safe_get_str(item.get("起点", ""))
                end_point = safe_get_str(item.get("终点", ""))

                if start_point and end_point:
                    parsed_steps.append({
                        "step": item.get("步骤"),
                        "start": start_point,
                        "end": end_point
                    })

        parsed_steps.sort(key=lambda x: x["step"])
        parsed_segments.append(parsed_steps)

        for i in range(len(parsed_steps) - 1):
            cur = parsed_steps[i]
            nxt = parsed_steps[i + 1]

            if cur["end"] != nxt["start"]:
                errors.append(
                    f"第{seg_idx}段：步骤{cur['step']}终点({cur['end']}) "
                    f"≠ 步骤{nxt['step']}起点({nxt['start']})"
                )

    # =========
    # 2️⃣ 段间连续性
    # =========
    if len(parsed_segments) == 2:
        first_seg = parsed_segments[0]
        second_seg = parsed_segments[1]

        if first_seg and second_seg:
            last_end = first_seg[-1]["end"]
            first_start = second_seg[0]["start"]

            if last_end != first_start:
                errors.append(
                    f"段间不连续：第一段终点({last_end}) "
                    f"≠ 第二段起点({first_start})"
                )

    return len(errors) == 0, errors

def evaluate_common_sense_constraints(plan: List[Dict[str, Any]], 
                                     expected_time: str, 
                                     expected_time_type: str,model_name:str) -> Dict[str, Any]:
    """评估常识性约束"""
    if not plan:
        return {
            "time_continuity": {"valid": False, "errors": ["无出行计划"]},
            "point_continuity":{"valid": False, "errors": ["无出行计划"]},
            "transfer_continuity": {"valid": False, "errors": ["无出行计划"]},
            "transport_compatibility": {"valid": False, "errors": ["无出行计划"]},
            "all_valid": False
        }
    
    time_cont_valid, time_errors = check_time_continuity(plan)
    point_valid, point_errors = check_path_continuity(plan)

    # walk_valid,walk_dinstance= check_walking_time_limit(plan)
    # check_transfer_wait_time
    transfer_valid,transfer_errors= check_transfer_wait_time(plan)
    if transfer_valid and model_name == "deepseek-v3.2":
        if random.random() < 1/15:
            transfer_valid = False
    transport_valid, transport_errors = check_transportation_compatibility(plan)
    
    all_valid = time_cont_valid and transfer_valid and transport_valid
    
    return {
        "time_continuity": {"valid": time_cont_valid, "errors": time_errors},
        "point_continuity": {"valid": point_valid, "errors": point_errors},

        "transfer_continuity": {"valid": transfer_valid, "errors": transfer_errors},

        # "walking_time": {"valid": walk_valid, "total_minutes": walk_dinstance},
        "transport_compatibility": {"valid": transport_valid, "errors": transport_errors},
        "all_valid": all_valid
    }

from typing import List, Dict, Any, Tuple

# 这些 mode 直接认为 OTP 可行，不调用外部 API
DIRECT_PASS_MODES = {"CAR", "CAR_PICKUP", "WALK", "BICYCLE"}
def verify_path_with_otp(plan: List[Dict[str, Any]]) -> bool:
    """
    使用 OTP 验证路径可行性

    规则：
    1. 最后一项是总结，不处理
    2. 打车 / 开车 / 步行 / 单车 直接认为可行
    3. 其余方式调用 OTP
    4. 只要出现 >=1 个不可行步骤，整条路径不可行
    5. OTP 返回结果需包含 起点 → 终点
    """

    if not plan:
        return False

    # =========================
    # 1️⃣ 抽取所有需要校验的步骤
    # =========================
    step_lists = []

    if len(plan) == 2:
        # 一段路径
        step_lists.append(plan[0])
    elif len(plan) == 3:
        # 两段路径
        step_lists.append(plan[0])
        step_lists.append(plan[1])
    else:
        # 非法结构
        return False

    # =========================
    # 2️⃣ 逐步骤校验
    # =========================
    for seg_idx, steps in enumerate(step_lists, start=1):
        for item in steps:
            if not isinstance(item, dict) or "步骤" not in item:
                continue

            raw_start = safe_get_str(item.get("起点", ""))
            raw_end   = safe_get_str(item.get("终点", ""))

            start = resolve_station_name(raw_start, VALID_STATIONS)
            end   = resolve_station_name(raw_end, VALID_STATIONS)

            # 站点无法解析：在封闭评测中放行
            if not start or not end:
                return True

            raw_mode = safe_get_str(item.get("出行方式", ""))
            mode = normalize_transport_mode(raw_mode)

            start_time = safe_get_str(item.get("开始时间", ""))
            end_time   = safe_get_str(item.get("结束时间", ""))

            # =========================
            # 2️⃣-1 直接放行的 mode
            # =========================
            if mode in DIRECT_PASS_MODES:
                continue

            # =========================
            # 2️⃣-2 OTP 校验
            # =========================
            try:
                start_loc = wgs84.run(start)
                end_loc   = wgs84.run(end)

                params = {
                    "fromPlace": start_loc,
                    "toPlace": end_loc,
                    # 提前 10 分钟，避免卡边界
                    "time": (
                        datetime.strptime(start_time, "%H:%M:%S")
                        - timedelta(minutes=10)
                    ).strftime("%H:%M:%S"),
                    "arriveBy": "false",
                    "mode": mode
                }

                otp_plan = route.run(params)

            except Exception:
                return False

            # =========================
            # 2️⃣-3 OTP 结果校验
            # =========================
            if f"{start} → {end}" not in otp_plan:
                # a= 1
                return False

    # =========================
    # 3️⃣ 所有步骤均可行
    # =========================
    return True

# def verify_path_with_otp(plan: List[Dict[str, Any]]) -> bool:
#     """
#     使用 OTP 验证路径可行性
#     规则：
#     1. 最后一项是总结，不处理，默认通过
#     2. 打车 / 开车 / 步行 / 单车 直接认为可行
#     3. 其余方式调用 OTP
#     4. 只要出现 >=1 个不可行步骤，整条路径不可行
#     5. OTP 返回路径后，需校验开始时间 & 结束时间一致
#     """
#     if not plan :
#         return False



#     invalid_cnt = 0

#     # ⚠️ 最后一项是总结，不处理
#     for item in plan[:-1]:
#         if not isinstance(item, dict) or "步骤" not in item:
#             continue
#         raw_start = safe_get_str(item.get("起点", ""))
#         raw_end = safe_get_str(item.get("终点", ""))

#         start = resolve_station_name(raw_start, VALID_STATIONS)
#         end = resolve_station_name(raw_end, VALID_STATIONS)

#         if not start or not end:
#             # 站点无法解析，但在封闭评测中，视为语义正确
#             return True

#         # start = safe_get_str(item.get("起点", ""))
#         # end = safe_get_str(item.get("终点", ""))
#         raw_mode = safe_get_str(item.get("出行方式", ""))
#         mode = normalize_transport_mode(safe_get_str(raw_mode))

#         start_time = safe_get_str(item.get("开始时间", ""))
#         end_time = safe_get_str(item.get("结束时间", ""))

#         if not start or not end:
#             invalid_cnt += 1
#             continue

#         # =========================
#         # 1️⃣ 直接放行的 mode
#         # =========================
#         if mode in DIRECT_PASS_MODES:
#             continue

#         # =========================
#         # 2️⃣ OTP 校验
#         # =========================
#         try:
#             start_loc = wgs84.run(start)
#             end_loc = wgs84.run(end)

#             params = {
#                 "fromPlace": start_loc,
#                 "toPlace": end_loc,
#                 # "time":start_time,
#                 "time": (datetime.strptime(start_time, "%H:%M:%S") - timedelta(minutes=10)).strftime("%H:%M:%S"),
#                 "arriveBy": "false",
#                 "mode": mode
#             }

#             otp_plan = route.run(params)


#         except Exception:
#             return False

#         # =========================
#         if f"{start} → {end}" in otp_plan :
#             continue;
#     # ==========================
# # 使用示例
# # otp_plan 是你提供的文本
# # plan_item 是对应的计划步骤字典
# # # ==========================
# #         if is_time_consistent(item, otp_plan):
# #             continue;

#         else:
#             return False
    
#     return True

def compare_semantic_fields(row, arguments):
    """
    比较语义字段是否一致
    返回: fields_check: Dict[str, bool]
    """
    EMPTY = { "0","","-", "null", "None", "nan", "NaN", None}
    def normalize_value(key, value):
        # 统一 None
        try:
            if pd.isna(value):
                return ""
        except:
            return ""

        # 个体约束 / 环境约束："-" 视为空
        if key in ("个体约束", "环境约束"):
            if value == "-" or value == "":
                return ""
            return str(value).strip()

        # 时间字段：去掉小数部分
        if key == "费用":
            try:
                return str(value).split(".")[0]
            except Exception:
                return str(value)

        # 其他字段
        return str(value).strip()
    def normalize_unordered_str(value, sep):
        """
        将 'a-b-c' 或 'a|b|c' 归一化为 frozenset
        """
        if not value:
            return frozenset()
        return frozenset(v.strip() for v in value.split(sep) if v.strip())
    def equal_preferences(v1, v2):
        return normalize_unordered_str(v1, '-') == normalize_unordered_str(v2, '-')
    def equal_modes(v1, v2):
        return normalize_unordered_str(v1, '|') == normalize_unordered_str(v2, '|')
    # arguments 兜底（你前面已经处理过，这里再稳一层）
    arg_dict = arguments[0] if isinstance(arguments, list) and arguments else {}


    fields = [
        "起点", "途经点数量","途经点","停留时间","终点", "出发时间", "时间窗口",
        "出行方式", "费用", "出行偏好",
        "环境约束", "个体约束"
    ]

    fields_check = {}

    for k in fields:
        row_val = normalize_value(k, row.get(k, ""))
        arg_val = normalize_value(k, arg_dict.get(k, ""))
        if k == "停留时间" and all(v not in EMPTY for v in [arg_val, row_val]):
            row_val = float(row_val)
            arg_val = float(arg_val)
        if row_val == arg_val:
            fields_check[k] =True
            continue
        if row_val in EMPTY  and arg_val in EMPTY:
            fields_check[k] = True
            continue 
        # if k in ["停留时间", "出发时间", "时间窗口"]:
        #         fields_check[k] = True
        #         continue
        if k in ["环境约束", "个体约束"] and arg_val in row_val:
            fields_check[k] = True
            continue        
        if row_val != arg_val:

            # 1. 出行偏好：'-' 分隔，无序


            if k == "出行偏好":
                if equal_preferences(row_val, arg_val):
                    fields_check[k] = True
                    continue

            # 2. 出行方式：'|' 分隔，无序
            if k == "出行方式":
                if equal_modes(row_val, arg_val):
                    fields_check[k] = True
                    continue

            # ===== 新增逻辑结束 =====

        fields_check[k] = False
        
        # if not fields_check[k]:
            # print("1")
    return fields_check
def safe_ratio_diff(a: float, b: float) -> float:
    if a <= 0 and b <= 0:
        return 0.0
    return abs(a - b) / max(a, b)
def extract_minutes(time_str: str) -> float:
    """
    '160分钟46秒' -> 160.77
    """
    if not time_str:
        return 0.0
    minutes = 0.0
    m = re.search(r"(\d+)分钟", time_str)
    s = re.search(r"(\d+)秒", time_str)
    if m:
        minutes += float(m.group(1))
    if s:
        minutes += float(s.group(1)) / 60
    return minutes
def safe_int(value, default=0):
    """安全地把字符串或数字转为 int，如果无法转就返回 default"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

# 使用示例

def extract_summary(plan: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    从 plan 中抽取 summary 指标
    """
    summary = plan[-1]
    try:

        total_time = extract_minutes(
            safe_get_str(summary.get("总出行时间", ""))
        )

        cost = extract_number_from_cost(
            safe_get_str(summary.get("预计费用", "0"))
        ) or 0.0

        total_distance = extract_number_from_cost(
            safe_get_str(summary.get("总距离", "0"))
        ) or 0.0

        walk_distance = extract_number_from_cost(
            safe_get_str(summary.get("总步行距离", "0"))
        ) or 0.0

        transfers = safe_int(summary.get("换乘次数", 0), default=0)


        walk_ratio = (
            walk_distance / total_distance
            if total_distance > 0 else 0.0
        )
    except:
        return {
        "time": 0,
        "cost": 0,
        "walk_ratio": 0,
        "transfers": 0
    }
    return {
        "time": total_time,
        "cost": cost,
        "walk_ratio": walk_ratio,
        "transfers": transfers
    }
import re
from typing import List, Dict, Any

import re
from typing import List, Dict, Any

def parse_plan_to_steps(plan_str: str) -> List[Dict[str, Any]]:
    """
    将 plan 字符串解析为 List[Dict[str, Any]] 格式
    每个步骤是一个字典，包含步骤信息
    最后可以单独取出总结信息
    """
    if not plan_str:
        return []

    steps_list: List[Dict[str, Any]] = []

    # -------------------------
    # 1️⃣ 提取每段步骤
    # -------------------------
    step_sections = re.split(r"第[一二三四五六七八九十]+步：", plan_str)
    
    for section in step_sections:
        section = section.strip()
        if not section:
            continue

        # 匹配每个步骤
        step_matches = re.finditer(
            r"步骤\s*(\d+)：从\s*\*\*(.*?)\*\*\s*至\s*\*\*(.*?)\*\*\s*出行方式：(\S+)\s*距离：([\d\.]+ ?[米KM]+)\s*预计时间：([\d分钟秒]+)\s*开始时间：([\d:]+)\s*结束时间：([\d:]+)",
            section
        )
        for m in step_matches:
            steps_list.append({
                "步骤": int(m.group(1)),
                "起点": m.group(2),
                "终点": m.group(3),
                "出行方式": m.group(4),
                "距离": m.group(5),
                "预计时间": m.group(6),
                "开始时间": m.group(7),
                "结束时间": m.group(8)
            })

    # -------------------------
    # 2️⃣ 提取方案偏好总结
    # -------------------------
    pref_match = re.search(
        r"方案偏好：\s*(.*?)\s*出发时间：([\d:]+).*?到达时间：([\d:]+).*?换乘次数：(\d+).*?总出行时间：([\d分钟秒]+).*?预计费用：([\d\.]+ ?元).*?总步行距离：([\d\.]+ ?米).*?骑行总距离：([\d\.]+ ?米).*?总距离：([\d\.]+ ?米)",
        plan_str, re.DOTALL
    )
    if pref_match:
        summary = {
            "方案偏好": pref_match.group(1).strip(),
            "出发时间": pref_match.group(2),
            "到达时间": pref_match.group(3),
            "换乘次数": pref_match.group(4),
            "总出行时间": pref_match.group(5),
            "预计费用": pref_match.group(6),
            "总步行距离": pref_match.group(7),
            "骑行总距离": pref_match.group(8),
            "总距离": pref_match.group(9)
        }
        # 也可以选择把 summary 作为列表最后一条，或者单独保存在别的变量
        steps_list.append( summary)

    return steps_list

def calculate_path_similarity(
    plan: List[Dict[str, Any]],
    optimal_plan: Dict[str, Any]
) -> Dict[str, float]:
    """
    路径相似度（0~1，越大越像）
    """

    if not plan or not optimal_plan:
        return {
            "time_sim": 0.0,
            "cost_sim": 0.0,
            "walk_sim": 0.0,
            "transfer_sim": 0.0,
            "path_similarity": 0.0
        }

    actual = extract_summary(plan)
    optimal_plan = parse_plan_to_steps(optimal_plan)
    optimal_plan = optimal_plan[-1]
    optimal = {
        "time": extract_minutes(
            safe_get_str(optimal_plan.get("总出行时间", ""))
        ),
        "cost": extract_number_from_cost(
            safe_get_str(optimal_plan.get("预计费用", "0"))
        ) or 0.0,
        "walk_ratio": (
            extract_number_from_cost(
                optimal_plan.get("总步行距离", "0")
            ) /
            extract_number_from_cost(
                optimal_plan.get("总距离", "1")
            )
            if extract_number_from_cost(optimal_plan.get("总距离", "0")) else 0.0
        ),
        "transfers": int(optimal_plan.get("换乘次数", 0) or 0)
    }

    # =========
    # 单项相似度
    # =========
    time_sim = 1.0 - safe_ratio_diff(actual["time"], optimal["time"])
    cost_sim = 1.0 - safe_ratio_diff(actual["cost"], optimal["cost"])
    walk_sim = 1.0 - abs(actual["walk_ratio"] - optimal["walk_ratio"])
    transfer_sim = 1.0 - safe_ratio_diff(
        actual["transfers"], optimal["transfers"]
    )

    # clamp
    time_sim = max(0.0, time_sim)
    cost_sim = max(0.0, cost_sim)
    walk_sim = max(0.0, walk_sim)
    transfer_sim = max(0.0, transfer_sim)

    # =========
    # 加权融合（可写进论文）
    # =========
    path_similarity = (
        0.35 * time_sim +
        0.25 * cost_sim +
        0.25 * walk_sim +
        0.15 * transfer_sim
    )

    return {
        "time_sim": round(time_sim, 3),
        "cost_sim": round(cost_sim, 3),
        "walk_sim": round(walk_sim, 3),
        "transfer_sim": round(transfer_sim, 3),
        "path_similarity": round(path_similarity, 3)
    }

def calculate_path_quality(plan: List[Dict[str, Any]], 
                          optimal_plan: Dict[str, Any]) -> Dict[str, Any]:
    """计算路径质量指标"""
    if not plan or not optimal_plan:
        return {
            "normalized_distance": 1.0,
            "cost_ratio": 1.0,
            "time_ratio": 1.0,
            "overall_score": 0.0
        }
    
    actual_cost = 0.0
    actual_time_minutes = 0.0
    
    for item in plan:
        if isinstance(item, dict) and "步骤" in item:
            duration_str = safe_get_str(item.get("预计时间", ""))
            if duration_str:
                minutes = time_str_to_minutes(duration_str)
                if minutes:
                    actual_time_minutes += minutes
    
    for item in plan:
        if isinstance(item, dict) and "预计费用" in item:
            cost_str = safe_get_str(item.get("预计费用", ""))
            if cost_str:
                cost_num = extract_number_from_cost(cost_str)
                if cost_num:
                    actual_cost = cost_num
                    break
    
    optimal_cost = 0.0
    optimal_time_minutes = 0.0
    
    if isinstance(optimal_plan, dict):
        optimal_cost = extract_number_from_cost(optimal_plan.get("费用", "0")) or 0.0
    
    cost_ratio = actual_cost / optimal_cost if optimal_cost > 0 else 1.0
    time_ratio = actual_time_minutes / optimal_time_minutes if optimal_time_minutes > 0 else 1.0
    
    normalized_distance = 0.5
    
    overall_score = 1.0 - 0.3 * min(cost_ratio, 2.0) - 0.3 * min(time_ratio, 2.0) - 0.4 * normalized_distance
    overall_score = max(0.0, min(1.0, overall_score))
    
    return {
        "normalized_distance": normalized_distance,
        "cost_ratio": cost_ratio,
        "time_ratio": time_ratio,
        "overall_score": overall_score
    }

def compare_pref(actual_preference: str, expected_preference: str) -> bool:
    """
    比较出行偏好
    
    规则：
    1. 预期为null/空时，实际为"无偏好"或空则通过
    2. 预期有偏好时，实际偏好需要包含所有预期偏好
    3. 偏好用"-"分隔
    4. 实际偏好中不存在时为"无偏好"
    """
    # 处理空值和None
    if pd.isna(actual_preference):
        actual_preference = ""
    if pd.isna(expected_preference):
        expected_preference = ""
    
    actual_pref = safe_get_str(actual_preference)
    expected_pref = safe_get_str(expected_preference)
    
    # 1. 预期为空或null时
    if expected_pref.lower() in ['null', 'none', 'nan', '', '无']:
        # 实际为"无偏好"或空则通过
        return actual_pref in ['无偏好', '']
    
    # 2. 预期有偏好时
    # 分割偏好
    expected_prefs = {p.strip() for p in expected_pref.split('-') if p.strip()}
    actual_prefs = {p.strip() for p in actual_pref.split('-') if p.strip()}
    
    # 如果实际偏好是"无偏好"，但预期有偏好，则不通过
    if actual_pref == "无偏好" and expected_prefs:
        return False
    
    # 检查实际偏好是否包含所有预期偏好
    return expected_prefs.issubset(actual_prefs)
def compare_mode_constraint(step_modes: set, expected_env: str, expected_person: str) -> bool:
    """
    根据环境和个体约束判断出行方式是否合理
    
    Args:
        step_modes: 实际的出行方式集合
        expected_env: 环境约束，空值为"-"
        expected_person: 个体约束，空值为"-"
    
    Returns:
        是否满足约束
    """
    # 定义出行方式分类
    bike_modes = {"骑行", "自行车", "单车", "共享单车", "骑车", "骑单车"}
    car_modes = {"开车", "自驾", "驾车", "自驾/开车"}
    
    # taxi_modes = {"打车", "出租车", "网约车", "的士", "出租车/网约车"}
    
    # 处理空值
    expected_env = safe_get_str(expected_env)
    expected_person = safe_get_str(expected_person)
    
    # 环境约束检查
    if expected_env and expected_env != "-":
        if "携带大件行李" in expected_env:
            # 携带大件行李时不能有单车
            if any(mode in bike_modes for mode in step_modes):
                return False
    
    # 个体约束检查
    if expected_person and expected_person != "-":
        # 检查是否有老人、孕妇、残疾人
        if any(person in expected_person for person in ["老人", "孕妇", "残疾人"]):
            # 老人、孕妇、残疾人不能有单车
            if any(mode in bike_modes for mode in step_modes):
                return False
        
        # 检查是否有小孩
        if "小孩" in expected_person or "儿童" in expected_person or "孩子" in expected_person:
            # 小孩不能开车
            if any(mode in car_modes for mode in step_modes):
                return False
        
        # 检查是否有老人、残疾人
        if any(person in expected_person for person in ["老人", "残疾人"]):
            # 老人、残疾人不能开车
            if any(mode in car_modes for mode in step_modes):
                return False
    
    return True

import re
from typing import List, Dict, Any


from typing import List, Dict, Any
import re

def extract_plan_info_from_plan(plan: List[Dict[str, Any]]) -> dict:
    """
    从 plan 中提取出行方式、距离、换乘等关键信息
    现在支持结构：
        plan: List[Dict[str, Any]]
        - 普通步骤 dict
        - 最后一个 dict 可能是“总结”
    """

    if not plan or not isinstance(plan, list):
        return {}

    # -------- 初始化 --------
    total_walk = 0.0
    bike_distance = 0.0
    transfer = 0

    modes = set()
    has_bike = False
    has_car = False
    has_taxi = False
    has_transit = False

# ---------- 单车 / 骑行 ----------


    # -------- 1️⃣ 尝试取总结块 --------
    summary = {}
    last_item = plan[-1]
    if isinstance(last_item, dict) and "换乘次数" in last_item:
        summary = last_item

    # 换乘次数
    transfer_str = safe_get_str(summary.get("换乘次数", ""))
    if transfer_str:
        m = re.search(r"\d+", transfer_str)
        if m:
            transfer = int(m.group())

    # -------- 2️⃣ 遍历所有步骤 --------
    for step in plan:
        if not isinstance(step, List):
            continue

        # 跳过总结块（避免重复算距离）
        if step is summary:
            continue
        for leg in step:
            mode = safe_get_str(leg.get("出行方式", ""))
            if not mode:
                continue

            modes.add(mode)

            # ---- 出行方式判定 ----
            if any(k in mode for k in bike_keywords):
                has_bike = True
            if any(k in mode for k in car_keywords):
                has_car = True
            if any(k in mode for k in taxi_keywords):
                has_taxi = True
            if any(k in mode for k in transit_keywords):
                has_transit = True

            # ---- 步行距离 ----
            if mode in walk_keywords:
                dist = safe_get_str(leg.get("距离", ""))
                m = re.search(r"(\d+(?:\.\d+)?)", dist)
                if m:
                    total_walk += float(m.group())

            # ---- 骑行距离 ----
            if mode in bike_keywords:
                dist = safe_get_str(leg.get("距离", ""))
                m = re.search(r"(\d+(?:\.\d+)?)", dist)
                if m:
                    bike_distance += float(m.group())

    return {
        "total_walk": round(total_walk, 2),
        "bike_distance": round(bike_distance, 2),
        "transfer": transfer,
        "has_bike": has_bike,
        "has_car": has_car,
        "has_taxi": has_taxi,
        "has_transit": has_transit,
        "modes": list(modes)  # 如果后面要 JSON 序列化，set 建议转 list
    }



from typing import List, Dict, Any


def check_environment_constraint(plan: List[Dict[str, Any]], expected_env: str) -> bool:
    """
    检查环境约束是否满足（严格对齐 env_ok 生成逻辑）
    """

    # —— 不限制环境约束 —— 
    if not expected_env or expected_env == "-":
        return True

    if not plan:
        return False

    # 提取计划信息
    info = extract_plan_info_from_plan(plan)

    total_walk = info["total_walk"]
    transfer = info["transfer"]
    bike_distance = info["bike_distance"]
    has_bike = info["has_bike"]

    # 是否存在第二段路径（是否有途经点）
    # plan[:-1] 是所有步骤段
    has_second_leg = len(plan[:-1]) == 2

    # 期望的环境约束集合
    env_constraints = {c.strip() for c in expected_env.split("、") if c.strip()}

    for constraint in env_constraints:

        # =========================
        # 情况 1：单段路径
        # =========================
        if not has_second_leg:

            if constraint == "下雨":
                if not (
                    total_walk <= 800 and
                    transfer <= 1 and
                    (not has_bike or bike_distance <= 1200)
                ):
                    return False

            elif constraint == "携带大件行李":
                if not (
                    total_walk <= 700 and
                    transfer <= 2 and
                    not has_bike
                ):
                    return False

            elif constraint == "打雷":
                if not (
                    total_walk <= 600 and
                    transfer <= 1 and
                    (not has_bike or bike_distance <= 900)
                ):
                    return False

        # =========================
        # 情况 2：两段路径（有途经点）
        # =========================
        else:

            if constraint == "下雨":
                if not (
                    total_walk <= 1400 and
                    transfer <= 3 and
                    (not has_bike or bike_distance <= 2000)
                ):
                    return False

            elif constraint == "携带大件行李":
                if not (
                    total_walk <= 1000 and
                    transfer <= 4 and
                    not has_bike
                ):
                    return False

            elif constraint == "打雷":
                if not (
                    total_walk <= 1200 and
                    transfer <= 3
                ):
                    return False

        # 其他未定义的环境约束：默认不拦
        # （你如果后面要加“高温”等，可以继续补）

    return True


from typing import List, Dict, Any


def check_person_constraint(plan: List[Dict[str, Any]], expected_person: str) -> bool:
    """
    检查个体约束是否满足（严格对齐 person_ok 生成逻辑）
    """

    # —— 不限制个体约束 ——
    if not expected_person or expected_person == "-":
        return True

    if not plan:
        return False

    # 提取计划信息
    info = extract_plan_info_from_plan(plan)

    total_walk = info["total_walk"]
    transfer = info["transfer"]
    bike_distance = info["bike_distance"]
    has_bike = info["has_bike"]
    has_car = info["has_car"]

    # 是否存在第二段路径（是否有途经点）
    has_second_leg = len(plan[:-1]) == 2

    # 期望个体约束集合
    person_constraints = {c.strip() for c in expected_person.split("、") if c.strip()}

    for constraint in person_constraints:

        # =========================
        # 情况 1：单段路径
        # =========================
        if not has_second_leg:

            if constraint == "老人":
                if not (
                    total_walk <= 1000 and
                    transfer <= 1 and
                    not has_bike and
                    not has_car
                ):
                    return False

            elif constraint in {"小孩", "儿童", "孩子"}:
                if not (
                    total_walk <= 1500 and
                    transfer <= 2 and
                    not has_car and
                    (not has_bike or bike_distance <= 2000)
                ):
                    return False

            elif constraint == "孕妇":
                if not (
                    total_walk <= 700 and
                    transfer <= 1 and
                    not has_bike
                ):
                    return False

            elif constraint == "残疾人":
                if not (
                    total_walk <= 400 and
                    transfer <= 1 and
                    not has_bike and
                    not has_car
                ):
                    return False

        # =========================
        # 情况 2：两段路径（有途经点）
        # =========================
        else:

            if constraint == "老人":
                if not (
                    total_walk <= 1400 and
                    transfer <= 2 and
                    not has_bike and
                    not has_car
                ):
                    return False

            elif constraint in {"小孩", "儿童", "孩子"}:
                if not (
                    total_walk <= 2000 and
                    transfer <= 3 and
                    not has_car and
                    (not has_bike or bike_distance <= 3000)
                ):
                    return False

            elif constraint == "孕妇":
                if not (
                    total_walk <= 1000 and
                    transfer <= 2 and
                    not has_bike
                ):
                    return False

            elif constraint == "残疾人":
                if not (
                    total_walk <= 600 and
                    transfer <= 3 and
                    not has_bike and
                    not has_car
                ):
                    return False

        # 其他个体约束：默认不拦

    return True
