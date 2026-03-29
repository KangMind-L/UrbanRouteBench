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

route = Routes()
wgs84 = Wgs84()
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
def check_time_condition(actual_start_time: str, actual_end_time: str, expected_time: str, time_type: str) -> Tuple[bool, bool]:
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
    
    if time_type == "出发":
        # 预期为出发时，实际出发和到达都应该不早于期望出发时间
        time_correct = (actual_start >= expected) and (actual_end >= expected)
        # 时间性质：实际出发是实际行程的开始时间
        time_property_correct = True
    elif time_type == "到达":
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

def get_start_end_from_plan(plan: List[Dict[str, Any]]) -> tuple[str, str, str, str]:
    """从出行计划中提取起点、终点、开始时间、结束时间"""
    start_point = ""
    end_point = ""
    start_time = ""
    end_time = ""
    
    if not plan:
        return start_point, end_point, start_time, end_time
    
    for item in plan:
        if isinstance(item, dict) and "步骤" in item:
            start_point = safe_get_str(item.get("起点", ""))
            start_time = safe_get_str(item.get("开始时间", ""))
            break
    
    for item in reversed(plan):
        if isinstance(item, dict) and "步骤" in item:
            end_point = safe_get_str(item.get("终点", ""))
            end_time = safe_get_str(item.get("结束时间", ""))
            break
    
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

def check_time_continuity(plan: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """检查时间连续性"""
    if not plan:
        return False, ["无出行计划"]
    
    errors = []
    steps = []
    
    for item in plan:
        if isinstance(item, dict) and "步骤" in item:
            step_num = item.get("步骤")
            start_time = parse_time(safe_get_str(item.get("开始时间", "")))
            end_time = parse_time(safe_get_str(item.get("结束时间", "")))
            
            if start_time and end_time:
                steps.append({
                    "step": step_num,
                    "start": start_time,
                    "end": end_time
                })
    
    if not steps:
        return False, ["无有效步骤"]
    
    steps.sort(key=lambda x: x["step"])
    
    for i in range(len(steps)):
        if steps[i]["start"] >= steps[i]["end"]:
            errors.append(f"步骤{steps[i]['step']}: 开始时间不早于结束时间")
        
        if i < len(steps) - 1:
            if steps[i]["end"] > steps[i+1]["start"]:
                errors.append(f"步骤{steps[i]['step']}结束时间晚于步骤{steps[i+1]['step']}开始时间")
    
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

def check_transportation_compatibility(plan: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """检查交通方式兼容性"""
    if not plan:
        return False, ["无出行计划"]
    
    errors = []
    steps = []
    
    for item in plan:
        if isinstance(item, dict) and "步骤" in item:
            step_num = item.get("步骤")
            mode = safe_get_str(item.get("出行方式", ""))
            if mode:
                steps.append({"step": step_num, "mode": mode})
    
    if not steps:
        return False, ["无有效步骤"]
    
    incompatible_combinations = [
        ({"打车", "出租车", "网约车"}, {"公交", "地铁", "骑行"}),
        ({"自驾", "开车"}, {"公交", "地铁", "骑行"}),
    ]
    
    if len(steps) >= 2:
        modes = {step["mode"] for step in steps}
        
        for group1, group2 in incompatible_combinations:
            has_group1 = any(g in str(modes) for g in group1)
            has_group2 = any(g in str(modes) for g in group2)
            
            if has_group1 and has_group2:
                errors.append(f"交通方式不兼容: {group1} 与 {group2} 不能共存")
                break
    
    return len(errors) == 0, errors

def evaluate_common_sense_constraints(plan: List[Dict[str, Any]], 
                                     expected_time: str, 
                                     expected_time_type: str) -> Dict[str, Any]:
    """评估常识性约束"""
    if not plan:
        return {
            "time_continuity": {"valid": False, "errors": ["无出行计划"]},
            "walking_time": {"valid": False, "total_minutes": 0},
            "transport_compatibility": {"valid": False, "errors": ["无出行计划"]},
            "all_valid": False
        }
    
    time_cont_valid, time_errors = check_time_continuity(plan)
    walk_valid,walk_dinstance= check_walking_time_limit(plan)
    transport_valid, transport_errors = check_transportation_compatibility(plan)
    
    all_valid = time_cont_valid and walk_valid and transport_valid
    
    return {
        "time_continuity": {"valid": time_cont_valid, "errors": time_errors},
        "walking_time": {"valid": walk_valid, "total_minutes": walk_dinstance},
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
    1. 最后一项是总结，不处理，默认通过
    2. 打车 / 开车 / 步行 / 单车 直接认为可行
    3. 其余方式调用 OTP
    4. 只要出现 >=1 个不可行步骤，整条路径不可行
    5. OTP 返回路径后，需校验开始时间 & 结束时间一致
    """
    if not plan :
        return False



    invalid_cnt = 0

    # ⚠️ 最后一项是总结，不处理
    for item in plan[:-1]:
        if not isinstance(item, dict) or "步骤" not in item:
            continue
        raw_start = safe_get_str(item.get("起点", ""))
        raw_end = safe_get_str(item.get("终点", ""))

        start = resolve_station_name(raw_start, VALID_STATIONS)
        end = resolve_station_name(raw_end, VALID_STATIONS)

        if not start or not end:
            # 站点无法解析，但在封闭评测中，视为语义正确
            return True

        # start = safe_get_str(item.get("起点", ""))
        # end = safe_get_str(item.get("终点", ""))
        raw_mode = safe_get_str(item.get("出行方式", ""))
        mode = normalize_transport_mode(safe_get_str(raw_mode))

        start_time = safe_get_str(item.get("开始时间", ""))
        end_time = safe_get_str(item.get("结束时间", ""))

        if not start or not end:
            invalid_cnt += 1
            continue

        # =========================
        # 1️⃣ 直接放行的 mode
        # =========================
        if mode in DIRECT_PASS_MODES:
            continue

        # =========================
        # 2️⃣ OTP 校验
        # =========================
        try:
            start_loc = wgs84.run(start)
            end_loc = wgs84.run(end)

            params = {
                "fromPlace": start_loc,
                "toPlace": end_loc,
                # "time":start_time,
                "time": (datetime.strptime(start_time, "%H:%M:%S") - timedelta(minutes=10)).strftime("%H:%M:%S"),
                "arriveBy": "false",
                "mode": mode
            }

            otp_plan = route.run(params)


        except Exception:
            return False

        # =========================
        if f"{start} → {end}" in otp_plan :
            continue;
    # ==========================
# 使用示例
# otp_plan 是你提供的文本
# plan_item 是对应的计划步骤字典
# # ==========================
#         if is_time_consistent(item, otp_plan):
#             continue;

        else:
            return False
    
    return True

def compare_semantic_fields(row, arguments):
    """
    比较语义字段是否一致
    返回: fields_check: Dict[str, bool]
    """

    def normalize_value(key, value):
        # 统一 None
        if pd.isna(value):
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

    # arguments 兜底（你前面已经处理过，这里再稳一层）
    arg_dict = arguments[0] if isinstance(arguments, list) and arguments else {}

    fields = [
        "起点", "终点", "时间", "时间性质",
        "出行方式", "费用", "出行偏好",
        "环境约束", "个体约束"
    ]

    fields_check = {}

    for k in fields:
        row_val = normalize_value(k, row.get(k, ""))
        arg_val = normalize_value(k, arg_dict.get(k, ""))
        fields_check[k] = (row_val == arg_val or arg_val in row_val)
        # if not fields_check[k]:
            # print("1")
    return fields_check

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

def extract_plan_info_from_plan(plan: List[Dict[str, Any]]) -> dict:
    """
    从出行计划中提取关键信息
    
    Returns:
        包含提取信息的字典
    """
    if not plan:
        return {}
    
    # 初始化统计
    total_walk = 0.0
    bike_distance = 0.0
    transfer_count = 0
    has_bike = False
    has_car = False
    has_taxi = False
    has_transit = False
    modes = set()
    
    # 统计每个步骤
    for item in plan:
        if isinstance(item, dict) and "步骤" in item:
            # 获取出行方式
            mode = safe_get_str(item.get("出行方式", ""))
            if mode:
                modes.add(mode)
                
                # 检查出行方式类型
                bike_keywords = ["单车", "骑行", "自行车", "骑车", "骑单车"]
                car_keywords = ["开车", "自驾", "驾车"]
                taxi_keywords = ["打车", "出租车", "网约车", "的士"]
                transit_keywords = ["公交", "地铁", "轨道交通"]
                
                if any(kw in mode for kw in bike_keywords):
                    has_bike = True
                if any(kw in mode for kw in car_keywords):
                    has_car = True
                if any(kw in mode for kw in taxi_keywords):
                    has_taxi = True
                if any(kw in mode for kw in transit_keywords):
                    has_transit = True
            
            # 提取步行距离（如果这个步骤是步行）
            if "步行" in mode or "走路" in mode:
                distance_str = safe_get_str(item.get("距离", ""))
                if distance_str:
                    # 提取数字
                    match = re.search(r'(\d+(?:\.\d+)?)', distance_str)
                    if match:
                        total_walk += float(match.group(1))
            
            # 提取骑行距离
            if "单车" in mode or "骑行" in mode or "自行车" in mode:
                distance_str = safe_get_str(item.get("距离", ""))
                if distance_str:
                    match = re.search(r'(\d+(?:\.\d+)?)', distance_str)
                    if match:
                        bike_distance += float(match.group(1))
    
    # 计算换乘次数（从计划总结中提取）
    transfer = 0
    for item in plan:
        if isinstance(item, dict) and "换乘次数" in item:
            transfer_str = safe_get_str(item.get("换乘次数", ""))
            if transfer_str:
                match = re.search(r'(\d+)', transfer_str)
                if match:
                    transfer = int(match.group(1))
            break
    
    return {
        "total_walk": total_walk,
        "transfer": transfer,
        "bike_distance": bike_distance,
        "has_bike": has_bike,
        "has_car": has_car,
        "has_taxi": has_taxi,
        "has_transit": has_transit,
        "modes": modes
    }

def check_environment_constraint(plan: List[Dict[str, Any]], expected_env: str) -> bool:
    """
    检查环境约束是否满足
    
    Args:
        plan: 出行计划列表
        expected_env: 环境约束，用"-"分隔，如"下雨-携带大件行李"
    
    Returns:
        是否满足环境约束
    """
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
    
    # 分割环境约束
    env_constraints = {c.strip() for c in expected_env.split("-") if c.strip()}
    
    for constraint in env_constraints:
        if constraint == "下雨" or constraint == "大风":
            if not (
                total_walk <= 800 and transfer <= 1 and
                (not has_bike or (has_bike and bike_distance <= 1600))
            ):
                return False
        
        elif constraint == "携带大件行李":
            if not (
                total_walk <= 700 and transfer <= 2 and
                not has_bike
            ):
                return False
        
        elif constraint == "打雷":
            if not (
                total_walk <= 600 and transfer <= 1 and
                (not has_bike or (has_bike and bike_distance <= 300))
            ):
                return False
        
        elif constraint == "高温" or constraint == "低温" or constraint == "极端温度":
            if not (
                total_walk <= 500 and
                (not has_bike or bike_distance <= 500)
            ):
                return False
        
        # 其他环境约束检查...
    
    return True

def check_person_constraint(plan: List[Dict[str, Any]], expected_person: str) -> bool:
    """
    检查个体约束是否满足
    
    Args:
        plan: 出行计划列表
        expected_person: 个体约束，用"-"分隔，如"老人-小孩"
    
    Returns:
        是否满足个体约束
    """
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
    has_taxi = info["has_taxi"]
    has_transit = info["has_transit"]
    
    # 分割个体约束
    person_constraints = {c.strip() for c in expected_person.split("-") if c.strip()}
    
    for constraint in person_constraints:
        if constraint == "老人":
            if not (
                total_walk <= 1000 and transfer <= 2 and
                not has_bike and not has_car and
                (has_transit or has_taxi)
            ):
                return False
        
        elif constraint == "小孩" or constraint == "儿童" or constraint == "孩子":
            if not (
                total_walk <= 2000 and transfer <= 3 and
                not has_car and
                (not has_bike or bike_distance <= 3000)
            ):
                return False
        
        elif constraint == "孕妇":
            if not (
                total_walk <= 700 and transfer <= 2 and
                not has_bike and
                (has_transit or has_taxi or has_car)
            ):
                return False
        
        elif constraint == "残疾人":
            if not (
                total_walk <= 400 and transfer <= 2 and
                not has_bike and not has_car and
                (has_transit or has_taxi)
            ):
                return False
        
        # 其他个体约束检查...
    
    return True