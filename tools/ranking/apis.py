import os
import re
import sys
from typing import Dict, List, Optional, Any
from collections import OrderedDict
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routes.apis import Routes

# ======================
# 基础参数
# ======================
ALPHA_TRANSFER = 5.0
ALPHA_COST = 2.0
BASE_WEIGHTS = {
    "total": 0.5,
    "walk": 0.2,
    "transfer": 0.15,
    "cost": 0.15
}

# ======================
# 约束映射
# ======================
SINGLE_CONSTRAINTS = {
    "时间最少": "total_time",
    "费用最低": "cost",
    "步行最少": "walk_time",
    "换乘最少": "transfer",
}

TIME_CONSTRAINTS = {
    "最早出发": ("start_min", min),
    "最早到达": ("end_min", min),
    "最晚出发": ("start_min", max),
    "最晚到达": ("end_min", max),
}

# ======================
# 工具函数
# ======================
def time_to_min(t: str) -> int:
    h, m = map(int, t.split(":")[:2])
    return h * 60 + m

def parse_plan_block(start:str, end:str,via_place:bool,block: str) -> Dict:
    plan = {}
    plan["plan_id"] = int(re.search(r"方案\s*(\d+)", block).group(1))
    t = re.search(r"时间:\s*(\d+:\d+:\d+)\s*→\s*(\d+:\d+:\d+)", block)
    if t:
        plan["start_min"] = time_to_min(t.group(1))
        plan["end_min"] = time_to_min(t.group(2))
    plan["total_time"] = int(re.search(r"总时长:\s*(\d+)", block).group(1)) if re.search(r"总时长:\s*(\d+)", block) else 0
    plan["walk_time"] = int(re.search(r"步行时间:\s*(\d+)", block).group(1)) if re.search(r"步行时间:\s*(\d+)", block) else 0
    plan["transfer"] = int(re.search(r"换乘:\s*(\d+)", block).group(1)) if re.search(r"换乘:\s*(\d+)", block) else 0
    cost = re.search(r"总费用:\s*([\d.]+)", block)
    plan["cost"] = float(cost.group(1)) if cost else 0.0
    if via_place:
        plan["raw_text"] = (
            # f"{row['起点']} → {row['终点']}\n"
            f"{block.strip()}"
    )
    else:
        plan["raw_text"] = (
            f"{start} → {end}\n"
            f"{block.strip()}"
        )
    return plan

def parse_all_plans(via_place:bool,text: str) -> List[Dict]:
    blocks = re.split(r"\n(?=方案\s*\d+)", text)
    start, end = re.search(r"^(.*?) → (.*?) \(", text).groups()
    return [parse_plan_block(start, end,via_place,b) for b in blocks if b.strip().startswith("方案")]

def is_all_walk_or_bicycle(plan: Dict) -> bool:
    """判断是否为纯 WALK 或纯 BICYCLE 方案"""
    if plan["walk_time"] == plan["total_time"]:
        return True
    if not re.search(r"\b(BUS|SUBWAY|CAR|CAR_PICKUP)\b", plan["raw_text"]):
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

def pick_min(plans, key):
    best = min(plans, key=lambda x: x[key])
    same = [p for p in plans if p[key] == best[key]]
    return min(same, key=lambda x: x["cost_total"])

def pick_two_constraints(plans, k1, k2):
    p1 = sorted(plans, key=lambda x: (x[k1], x[k2]))[0]
    p2 = sorted(plans, key=lambda x: (x[k2], x[k1]))[0]
    return p1 if p1["cost_total"] <= p2["cost_total"] else p2

# ======================
# 途经点相关函数
# ======================
def build_valid_combinations(plans_1, plans_2, time_stay):
    """
    输入：
        plans_1: 第一段方案列表
        plans_2: 第二段方案列表
        time_stay: 停留时间（分钟）
    输出：
        合法的组合方案列表
    """
    combos = []

    for p1 in plans_1:
        for p2 in plans_2:
            # 1️⃣ 第二段不能早于第一段到达
            if p2["start_min"] < p1["end_min"]:
                continue

            # 2️⃣ 停留时间约束
            if p2["start_min"] - p1["end_min"] < time_stay:
                continue

            combos.append({
                "p1": p1,
                "p2": p2
            })

    return combos

def compute_costs_with_via(start, via_place,end,combos, user_time, via_info=None):
    """
    计算途经点场景的方案成本
    via_info: 包含途经点信息的字典，如 {"from_name": "起点", "via_name": "途经点", "to_name": "终点"}
    """
    """
    combos: [{p1, p2}]
    """
    plans = []

    for c in combos:
        p1, p2 = c["p1"], c["p2"]

        plan = {
            "start_min": p1["start_min"],
            "end_min": p2["end_min"],
            "total_time": p2["end_min"] - p1["start_min"],
            "walk_time": p1["walk_time"] + p2["walk_time"],
            "transfer": p1["transfer"] + p2["transfer"]+1,
            "cost": p1["cost"] + p2["cost"],
            "raw_text": (
                        f"{start} → {via_place}\n"
                        f"{p1['raw_text']}\n\n"
                        "【途经点停留】\n\n"
                        f"{via_place} → {end}\n"
                        f"{p2['raw_text']}"
                )
        }

        plans.append(plan)

    # ===== 完全复用你原来的 cost 逻辑 =====
    compute_costs(plans, user_time)

    return plans

# ======================
# Ranking 类 - 整合途经点逻辑
# ======================
class Ranking:
    def __init__(self):
        print("路径排名器已初始化")
    
    def _extract_via_info(self, routes_text: str) -> Dict:
        """从路径文本中提取途经点信息"""
        # 匹配格式：起点 → 途经点 (出行方式: XXX) 和 途经点 → 终点 (出行方式: XXX)
        pattern1 = re.search(r"(.+?) → (.+?) \(出行方式:", routes_text)
        pattern2 = re.search(r"(.+?) → (.+?) \(出行方式:", routes_text[routes_text.find("→"):] if "→" in routes_text else "")
        
        if pattern1 and pattern2:
            from_name = pattern1.group(1).strip()
            via_name = pattern1.group(2).strip()
            to_name = pattern2.group(2).strip()
            
            return {
                "from_name": from_name,
                "via_name": via_name,
                "to_name": to_name,
                "has_via": True
            }
        return {"has_via": False}
    
    def rank_with_via(self, routes_text: str, user_time: int, time_window: int = 0, stay_time: int = 30) -> Dict[str, Dict]:
        """对有途经点的路径进行排名"""
        if not routes_text or not routes_text.strip():
            return {}
        
        # 1. 提取途经点信息
        via_info = self._extract_via_info(routes_text)
        if not via_info["has_via"]:
            return self.rank_single_mode(routes_text, user_time, time_window)
        
        # 2. 按出行方式拆分文本
        mode_blocks = re.split(r"\n(?=.*出行方式:\s*[A-Z_]+)", routes_text)
        routes_by_mode = OrderedDict()
        
        for block in mode_blocks:
            m = re.search(r"出行方式:\s*([A-Z_,]+)", block)
            if not m:
                continue
            mode = m.group(1)
            routes_by_mode.setdefault(mode, []).append(block.strip())
        
        if not routes_by_mode:
            return {}
        
        # 3. 对每个出行方式处理
        all_mode_res = {}
        
        for mode, route_text_list in routes_by_mode.items():
            if len(route_text_list) != 2:
                continue  # 途经点场景应该有两段
                
            # 解析两段路径
            plans_1 = parse_all_plans(route_text_list[0])
            plans_2 = parse_all_plans(route_text_list[1])
            
            # 过滤无效方案
            plans_1 = [p for p in plans_1 if not is_all_walk_or_bicycle(p)]
            plans_2 = [p for p in plans_2 if not is_all_walk_or_bicycle(p)]
            
            if not plans_1 or not plans_2:
                continue
            
            # 构建有效组合
            combos = build_valid_combinations(plans_1, plans_2, stay_time)
            if not combos:
                continue
            
            # 计算组合方案的成本
            via_info_with_names = {
                "from_name": via_info["from_name"],
                "via_name": via_info["via_name"],
                "to_name": via_info["to_name"]
            }
            plans = compute_costs_with_via(combos, user_time, via_info_with_names)
            
            # 应用时间窗口过滤
            if time_window > 0:
                max_arrive_time = user_time + time_window
                plans = [p for p in plans if p["end_min"] <= max_arrive_time]
            
            if not plans:
                continue
            
            # 生成各种偏好的最优方案
            res = {}
            res["无偏好"] = min(plans, key=lambda x: x["cost_total"])
            
            # 1 约束
            for name, key in SINGLE_CONSTRAINTS.items():
                res[name] = pick_min(plans, key)
            
            # 时间单约束
            if time_window == 0:
                res["最早出发"] = min(plans, key=lambda x: x["start_min"])
                res["最早到达"] = min(plans, key=lambda x: x["end_min"])
            else:
                res["最晚出发"] = max(plans, key=lambda x: x["start_min"])
                res["最晚到达"] = max(plans, key=lambda x: x["end_min"])
            
            # 双约束（4C2 = 6）
            keys = list(SINGLE_CONSTRAINTS.items())
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    n1, k1 = keys[i]
                    n2, k2 = keys[j]
                    res[f"{n1}-{n2}"] = pick_two_constraints(plans, k1, k2)
            
            # 单约束 × 时间约束（8）
            time_keys = ["最早出发", "最早到达"] if time_window == 0 else ["最晚出发", "最晚到达"]
            for n1, k1 in SINGLE_CONSTRAINTS.items():
                for tn in time_keys:
                    tk, _ = TIME_CONSTRAINTS[tn]
                    res[f"{n1}-{tn}"] = pick_two_constraints(plans, k1, tk)
            
            all_mode_res[mode] = res
        
        if not all_mode_res:
            return {}
        
        # 4. 跨出行方式比较
        final_res = {}
        constraint_keys = next(iter(all_mode_res.values())).keys()
        
        for key in constraint_keys:
            candidates = [res[key] for res in all_mode_res.values() if key in res]
            if candidates:
                final_res[key] = min(candidates, key=lambda p: p["cost_total"])
        
        return final_res
    
    def rank_single_mode(self, route_text: str, user_time: int, time_window: int = 0) -> Dict[str, Dict]:
        """对单个出行方式的路径进行排名（无途经点）"""
        if not route_text or not route_text.strip():
            return {}
        
        plans = parse_all_plans(route_text)
        plans = [p for p in plans if not is_all_walk_or_bicycle(p)]
        
        if not plans:
            return {}
        
        # 只有一条方案
        if len(plans) == 1:
            compute_costs(plans, user_time)
            return {"无偏好": plans[0]}
        
        compute_costs(plans, user_time)
        res = {}
        
        # 0 约束
        res["无偏好"] = min(plans, key=lambda x: x["cost_total"])
        
        # 1 约束
        for name, key in SINGLE_CONSTRAINTS.items():
            res[name] = pick_min(plans, key)
        
        # 时间单约束
        if time_window == 0:
            res["最早出发"] = min(plans, key=lambda x: x["start_min"])
            res["最早到达"] = min(plans, key=lambda x: x["end_min"])
        else:
            res["最晚出发"] = max(plans, key=lambda x: x["start_min"])
            res["最晚到达"] = max(plans, key=lambda x: x["end_min"])
        
        # 双约束（4C2 = 6）
        keys = list(SINGLE_CONSTRAINTS.items())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                n1, k1 = keys[i]
                n2, k2 = keys[j]
                res[f"{n1}-{n2}"] = pick_two_constraints(plans, k1, k2)
        
        # 单约束 × 时间约束（8）
        time_keys = ["最早出发", "最早到达"] if time_window == 0 else ["最晚出发", "最晚到达"]
        for n1, k1 in SINGLE_CONSTRAINTS.items():
            for tn in time_keys:
                tk, _ = TIME_CONSTRAINTS[tn]
                res[f"{n1}-{tn}"] = pick_two_constraints(plans, k1, tk)
        
        return res
    def select_best(self, route_text, user_time, time_window: int = 0, stay_time: int = 30):


        if len(route_text) ==1:
        # if via_nums == 0:
            
            plans = parse_all_plans(False,route_text[0])

            # ======================
            # 过滤纯 WALK 方案
            # ======================
            plans = [p for p in plans if not is_all_walk_or_bicycle(p)]

            if not plans:
                return {}

            # ======================
            # 🚗🚕 关键新增逻辑：只有一条方案
            # ======================
            if len(plans) == 1:
                compute_costs(plans, user_time)  # 确保 cost_total 存在
                return {"无偏好": plans[0]}




            compute_costs(plans, user_time)
            res = {}

            # 0 约束
            res["无偏好"] = min(plans, key=lambda x: x["cost_total"])

            # 1 约束
            for name, key in SINGLE_CONSTRAINTS.items():
                res[f"{name}"] = pick_min(plans, key)
        #         res[name] = (
        #     f"出行偏好为：{name},路径如下：\n"
        #     f"{pick_min(plans, key)}"
        # )

            # 时间单约束
            if int(time_window) == 0:
                res["最早出发"] = min(plans, key=lambda x: x["start_min"])
                res["最早到达"] = min(plans, key=lambda x: x["end_min"])
            else:
                res["最晚出发"] = max(plans, key=lambda x: x["start_min"])
                res["最晚到达"] = max(plans, key=lambda x: x["end_min"])

            # 双约束（4C2 = 6）
            keys = list(SINGLE_CONSTRAINTS.items())
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    n1, k1 = keys[i]
                    n2, k2 = keys[j]
                    res[f"{n1}-{n2}"] = pick_two_constraints(plans, k1, k2)

            # 单约束 × 时间约束（8）
            time_keys = ["最早出发", "最早到达"] if int(time_window) == 0 else ["最晚出发", "最晚到达"]
            for n1, k1 in SINGLE_CONSTRAINTS.items():
                for tn in time_keys:
                    tk, _ = TIME_CONSTRAINTS[tn]
                    res[f"{n1}-{tn}"] = pick_two_constraints(plans, k1, tk)

            return res


        if len(route_text) == 2:
            plans_1 = parse_all_plans(True,route_text[0])
            plans_2 = parse_all_plans(True,route_text[1])
            start, via_place = re.search(r"^(.*?) → (.*?) \(", route_text[0]).groups()
            via_place, end = re.search(r"^(.*?) → (.*?) \(", route_text[1]).groups()

            plans_1 = [p for p in plans_1 if not is_all_walk_or_bicycle(p)]
            plans_2 = [p for p in plans_2 if not is_all_walk_or_bicycle(p)]

            if not plans_1 or not plans_2:
                return {}

            combos = build_valid_combinations(plans_1, plans_2, stay_time)

            if not combos:
                return {}

            plans = compute_costs_with_via( start, via_place,end,combos, user_time)

            # ===== 选择逻辑完全复用 =====
            res = {}
            res["无偏好"] = min(plans, key=lambda x: x["cost_total"])

            for name, key in SINGLE_CONSTRAINTS.items():
                res[name] = pick_min(plans, key)

            if int(time_window) == 0:
                res["最早出发"] = min(plans, key=lambda x: x["start_min"])
                res["最早到达"] = min(plans, key=lambda x: x["end_min"])
            else:
                res["最晚出发"] = max(plans, key=lambda x: x["start_min"])
                res["最晚到达"] = max(plans, key=lambda x: x["end_min"])

            # 双约束（4C2 = 6）
            keys = list(SINGLE_CONSTRAINTS.items())
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    n1, k1 = keys[i]
                    n2, k2 = keys[j]
                    res[f"{n1}-{n2}"] = pick_two_constraints(plans, k1, k2)

            # 单约束 × 时间约束（8）
            time_keys = ["最早出发", "最早到达"] if int(time_window) == 0 else ["最晚出发", "最晚到达"]
            for n1, k1 in SINGLE_CONSTRAINTS.items():
                for tn in time_keys:
                    tk, _ = TIME_CONSTRAINTS[tn]
                    res[f"{n1}-{tn}"] = pick_two_constraints(plans, k1, tk)
            return res    
    def rank_multi_mode(self, routes_text: str, user_time: int, time_window: int = 0, stay_time: int = 30) -> Dict[str, Dict]:
        """对多个出行方式的路径进行排名（自动检测是否有途经点）"""

        mode_blocks = re.split(
            r"\n(?=.*出行方式:\s*[A-Z_]+)",
            routes_text
        )

        routes_by_mode = OrderedDict()

        for block in mode_blocks:
            m = re.search(r"出行方式:\s*([A-Z_,]+)", block)

            if not m:
                continue
            mode = m.group(1)
            routes_by_mode.setdefault(mode, []).append(block.strip())

        if not routes_by_mode:
            return {}

        # ======================
        # 2️⃣ 单一出行方式
        # ======================
        if len(routes_by_mode) == 1:
            _, route_text = next(iter(routes_by_mode.items()))
            return self.select_best(route_text,user_time, time_window, stay_time)

        # ======================
        # 3️⃣ 多出行方式
        # ======================
        all_mode_res = {}

        for mode, route_text in routes_by_mode.items():
            res = self.select_best(route_text,user_time, time_window, stay_time)
            # if res and "无偏好" in res:
            if res:

                all_mode_res[mode] = res

        if not all_mode_res:
            return {}
        final_res = {}


        
        constraint_keys = next(iter(all_mode_res.values())).keys()
        
        for key in constraint_keys:
            candidates = [res[key] for res in all_mode_res.values() if key in res]
            if candidates:
                final_res[key] = min(candidates, key=lambda p: p["cost_total"])
        
        return final_res
    
    def get_best_for_preference(self, result_text: str, time: str, time_window: int = 0, preference: str = "无偏好", stay_time: int = 30) -> Optional[str]:
        """获取特定偏好的最优路径"""
        user_time = time_to_min(time)
        ranked_plans = self.rank_multi_mode(result_text, user_time, time_window, stay_time)
        
        if preference in ranked_plans:
            plan = ranked_plans[preference]
            return f"出行偏好为：{preference}\n{plan['raw_text']}"
        return "出行偏好不符合条件"
    
    def get_all_ranked_results(self, result_text: str, time: str, time_window: int = 0, stay_time: int = 30) -> Dict[str, str]:
        """获取所有偏好的排名结果"""
        user_time = time_to_min(time)
        ranked_plans = self.rank_multi_mode(result_text, user_time, time_window, stay_time)
        
        ranked_texts = {}
        for preference, plan in ranked_plans.items():
            ranked_texts[preference] = f"出行偏好为：{preference}\n{plan['raw_text']}"
        
        return ranked_texts
    
    def run(self, text: str, time: str, time_window: int = 0, preference: Optional[str] = None, stay_time: int = 30) -> Optional[str]:
        """
        运行排名的主接口
        Args:
            text: 路径规划结果文本
            time: 出发时间 (格式: "HH:MM")
            time_window: 时间窗口（分钟），默认0表示无时间窗口
            preference: 出行偏好
            stay_time: 停留时间（分钟），默认30分钟
        Returns:
            返回该偏好的最优路径文本，如果未找到则返回None
        """
        # 处理所有空值情况
        if preference is None or (isinstance(preference, str) and not preference.strip()):
            preference = "无偏好"
        else:
            # 清理空格
            preference = preference.strip()
        
        return self.get_best_for_preference(text, time, time_window, preference, stay_time)

# ======================
# 构建所有偏好组合
# ======================
def build_all_preferences(time_window: int = 0) -> List[str]:
    """构建所有可能的偏好组合"""
    single = ["时间最少", "费用最低", "步行最少", "换乘最少"]
    
    if time_window == 0:
        time_keys = ["最早出发", "最早到达"]
    else:
        time_keys = ["最晚出发", "最晚到达"]
    
    prefs = []
    prefs.append("无偏好")  # 无偏好（综合最优）
    
    # 单约束（4）
    prefs.extend(single)
    
    # 时间约束（2）
    prefs.extend(time_keys)
    
    # 双单约束（6）
    for i in range(len(single)):
        for j in range(i + 1, len(single)):
            prefs.append(f"{single[i]}-{single[j]}")
    
    # 单 × 时间（8）
    for s in single:
        for t in time_keys:
            prefs.append(f"{s}-{t}")
    
    return prefs  # 共 21 个

# ======================
# 主函数 - 演示如何使用
# ======================
if __name__ == "__main__":
    try:
        planner = Routes()
        ranker = Ranking()
        
        modes = ['CAR']
        
        for mode in modes:
            print("\n" + "="*60)
            print("测试带途经点 + 时间窗口场景（两步：先查询，后排名）")
            print("="*60)
            
            via_window_template = '{{"fromPlace": "深圳北站::22.6537223,114.0242094", "toPlace": "市民中心::22.543096,114.057865", "time": "19:00", "mode": "{mode}", "stayMinutes": 20, "window": "180"}}'
            
            a = via_window_template.format(mode=mode)
            
            # 步骤1: 查询路径
            print("\n步骤1: 查询路径...")
            result_text = planner.run(a)
            print(f"Mode: {mode}, Window: 180分钟 (带途经点)")
            print("原始规划结果:")
            print(result_text[:5000] + "..." if len(result_text) > 500 else result_text)
            print("\n" + "-" * 40)
            
            # 测试不同偏好的排名
            test_preferences = [
                None,  # 综合最优
                "时间最少",  # 单约束
                # "费用最低",  # 单约束
                # "步行最少",  # 单约束
                # "换乘最少",  # 单约束
                # "最晚到达",  # 时间约束 (time_window>0)
                # "时间最少-费用最低",  # 双约束
                "时间最少-最晚到达",  # 单约束+时间约束
            ]
            
            print("\n步骤2: 测试不同偏好的排名结果（有途经点）...")
            for preference in test_preferences:
                print(f"\n偏好: {preference}")
                ranked_result = ranker.run(
                    result_text,
                    time="19:00",
                    time_window=180,
                    preference=preference,
                    stay_time=20
                )
                
                if ranked_result:
                    print(ranked_result[:5000] + "..." if len(ranked_result) > 300 else ranked_result)
                else:
                    print(f"❌ 未找到符合偏好 '{preference}' 的路径")
                print("-" * 40)
                    
    except Exception as e:
        print(f"运行错误: {e}")