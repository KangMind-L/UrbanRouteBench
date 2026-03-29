import os
import re, sys
from typing import Dict, List, Optional
from collections import OrderedDict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routes.apis import Routes

# ======================
# 基础参数
# ======================
ALPHA_TRANSFER = 5.0
ALPHA_COST = 2.0
#只有一段路径
BASE_WEIGHTS = {
    "total": 0.5,
    "walk": 0.2,
    "transfer": 0.15,
    "cost": 0.15
}

# ======================
# 约束映射
# ======================
CONSTRAINT_MAP = {
    "时间最少": lambda p: p["total_time"],
    "步行最少": lambda p: p["walk_time"],
    "换乘最少": lambda p: p["transfer"],
    "费用最低": lambda p: p["cost"],
    "最早出发": lambda p: p["start_min"],
    "最早到达": lambda p: p["end_min"],
    "最晚出发": lambda p: -p["start_min"],  # 取负用于 min 找最大
    "最晚到达": lambda p: -p["end_min"]
}

# ======================
# 工具函数
# ======================
def time_to_min(t: str) -> int:
    h, m = map(int, t.split(":")[:2])
    return h * 60 + m

def parse_plan_block(block: str) -> Dict:
    plan = {}
    plan["plan_id"] = int(re.search(r"方案\s*(\d+)", block).group(1))
    t = re.search(r"时间:\s*(\d+:\d+:\d+)\s*→\s*(\d+:\d+:\d+)", block)
    plan["start_min"] = time_to_min(t.group(1))
    plan["end_min"] = time_to_min(t.group(2))
    plan["total_time"] = int(re.search(r"总时长:\s*(\d+)", block).group(1))
    plan["walk_time"] = int(re.search(r"步行时间:\s*(\d+)", block).group(1)) if "步行时间" in block else 0
    plan["transfer"] = int(re.search(r"换乘:\s*(\d+)", block).group(1)) if "换乘" in block else 0
    cost = re.search(r"总费用:\s*([\d.]+)", block)
    plan["cost"] = float(cost.group(1)) if cost else 0.0
    plan["raw_text"] = block.strip()
    return plan

def parse_all_plans(text: str) -> List[Dict]:
    blocks = re.split(r"\n(?=方案\s*\d+)", text)
    return [parse_plan_block(b) for b in blocks if b.strip().startswith("方案")]

def is_all_walk(plan: Dict) -> bool:
    if plan["walk_time"] == plan["total_time"]:
        return True
    if not re.search(r"\b(BUS|SUBWAY|CAR|BICYCLE|CAR_PICKUP)\b", plan["raw_text"]):
        return True
    return False

def compute_costs(plans: List[Dict], user_time: int):
    for p in plans:
        p["user_diff"] = abs(p["start_min"] - user_time)
        p["total_adj"] = p["total_time"] + p["user_diff"]
        p["transfer_time"] = p["transfer"] * ALPHA_TRANSFER
        p["cost_time"] = p["cost"] * ALPHA_COST

    def norm(k):
        vs = [p[k] for p in plans]
        mn, mx = min(vs), max(vs)
        for p in plans:
            p[k + "_norm"] = 0 if mn == mx else (p[k] - mn) / (mx - mn)

    for k in ["total_adj", "walk_time", "transfer_time", "cost_time"]:
        norm(k)

    for p in plans:
        p["cost_total"] = (
            BASE_WEIGHTS["total"] * p["total_adj_norm"]
            + BASE_WEIGHTS["walk"] * p["walk_time_norm"]
            + BASE_WEIGHTS["transfer"] * p["transfer_time_norm"]
            + BASE_WEIGHTS["cost"] * p["cost_time_norm"]
        )

# ======================
# Ranking 类（支持多偏好和时间约束）
# ======================
class Ranking:

    def run(
        self,
        text: str,
        time: str,
        arriveBy: bool,
        preference: Optional[str] = None
    ) -> Optional[str]:

        # 按出行方式拆分
        mode_blocks = re.split(r"\n(?=.*出行方式:\s*[A-Z_]+)", text)
        routes_by_mode = OrderedDict()
        for block in mode_blocks:
            m = re.search(r"出行方式:\s*([A-Z_,]+)", block)
            if not m:
                continue
            mode = m.group(1)
            routes_by_mode[mode] = block.strip()

        if not routes_by_mode:
            return None

        user_time = time_to_min(time)
        best_plans_all_modes = []

        pref_list = preference.split("|") if preference else []
        pref_list = re.split(r"[|\-]", preference) if preference else []

        for mode, route_text in routes_by_mode.items():
            plans = parse_all_plans(route_text)
            plans = [p for p in plans if not is_all_walk(p)]
            if not plans:
                continue

            compute_costs(plans, user_time)

            if not pref_list:
                best_plans_all_modes.append(min(plans, key=lambda x: x["cost_total"]))
                continue

            # 针对每个出现的约束计算最优
            pref_candidates = []
            for pref in pref_list:
                if pref in CONSTRAINT_MAP:
                    key_func = CONSTRAINT_MAP[pref]
                    best = min(plans, key=lambda x: key_func(x))
                    pref_candidates.append(best)

            if not pref_candidates:
                continue

            # 跨偏好选择 cost_total 最低
            best_final = min(pref_candidates, key=lambda x: x["cost_total"])
            best_plans_all_modes.append(best_final)

        if not best_plans_all_modes:
            return None

        # 跨模式最终选 cost_total 最低
        final_best = min(best_plans_all_modes, key=lambda x: x["cost_total"])
        return final_best["raw_text"]

# ======================
# 示例
# ======================
def build_preferences(arriveBy: bool):
    single = ["时间最少", "费用最低", "步行最少", "换乘最少"]

    if not arriveBy:
        time_keys = ["最早出发", "最早到达"]
    else:
        time_keys = ["最晚出发", "最晚到达"]

    prefs = []
    prefs.append(None)  # 空偏好（综合最优）

    # 单约束（4）
    prefs.extend(single)

    # 时间约束（2）
    prefs.extend(time_keys)

    # 双单约束（6）
    for i in range(len(single)):
        for j in range(i + 1, len(single)):
            prefs.append(f"{single[i]}|{single[j]}")

    # 单 × 时间（8）
    for s in single:
        for t in time_keys:
            prefs.append(f"{s}|{t}")

    return prefs  # 共 21 个

if __name__ == "__main__":
    planner = Routes()
    ranker = Ranking()

    query_template = '{{"fromPlace":"深圳北站::22.6137,114.0242",' \
                     '"toPlace":"宝能城::22.5934,113.9932",' \
                     '"time":"17:45","arriveBy":"{arriveBy}","mode":"BUS|SUBWAY|TRANSIT|CAR"}}'

    for arriveBy in [False, True]:
        print("\n" + "=" * 80)
        print(f"🚦 arriveBy = {arriveBy}")
        print("=" * 80)

        prefs = build_preferences(arriveBy)
        query = query_template.format(arriveBy=str(arriveBy).lower())

        result_text = planner.run(query)

        for i, pref in enumerate(prefs):
            label = pref if pref else "综合最优"

            best = ranker.run(
                result_text,
                time="17:45",
                arriveBy=arriveBy,
                preference=pref
            )
            
            status = "✅" if best else "❌"
            
            print(f"[{i+1:02d}] {label:<20} {status}")
            print(best)
