import re
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime
import sys
import os

# 将 tools 目录加入路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from routes.apis import Routes


class Ranking:
    def __init__(self):
        # 默认权重
        self.default_weights = {
            "time": 0.30,
            "walk": 0.20,
            "fee": 0.20,
            "transfer": 0.20,
            "distance": 0.05,
            "match": 0.05,  # 时间匹配指标
        }

        # 用户偏好 → 权重映射表（不动）
        self.preference_weights = {
            "步行最短": {
                "time": 0.10, "walk": 0.55, "fee": 0.10,
                "transfer": 0.10, "distance": 0.10, "match": 0.05
            },
            "时间最少": {
                "time": 0.50, "walk": 0.10, "fee": 0.10,
                "transfer": 0.15, "distance": 0.10, "match": 0.05
            },
            "费用最低": {
                "time": 0.10, "walk": 0.10, "fee": 0.55,
                "transfer": 0.10, "distance": 0.10, "match": 0.05
            },
            "换乘最少": {
                "time": 0.20, "walk": 0.10, "fee": 0.10,
                "transfer": 0.45, "distance": 0.10, "match": 0.05
            },
            "距离最短": {
                "time": 0.10, "walk": 0.20, "fee": 0.10,
                "transfer": 0.10, "distance": 0.45, "match": 0.05
            }
        }

    # --------- 解析所有“方案 x” ---------
    def parse_routes(self, text: str):
        pattern = r"(方案\s*\d+:[\s\S]*?)(?=(方案\s*\d+:|$))"
        blocks = re.findall(pattern, text)
        routes = [b[0].strip() for b in blocks]
        return routes

    # --------- 提取指标 ---------
    def extract_features(self, route_text: str) -> Dict[str, Any]:

        # 提取数字
        def find_float(pattern, default=0):
            m = re.search(pattern, route_text)
            return float(m.group(1)) if m else default

        # 时间格式：17:45:00 → 18:53:38
        time_match = re.search(r"时间:\s*([\d:]+)\s*→\s*([\d:]+)", route_text)
        start_time = time_match.group(1) if time_match else "00:00:00"
        end_time = time_match.group(2) if time_match else "00:00:00"

        return {
            "total_time": find_float(r"总时长:\s*([\d\.]+)分钟"),
            "walk_time": find_float(r"步行时间:\s*([\d\.]+)分钟"),
            "walk_dist": find_float(r"步行距离:\s*([\d\.]+)米"),
            "transfer": find_float(r"换乘:\s*(\d+)次"),
            "total_dist": find_float(r"总距离:\s*([\d\.]+)米"),
            "fee": find_float(r"总费用:\s*([\d\.]+)元", default=0),
            "start_str": start_time,
            "end_str": end_time,
        }

    # --------- HH:MM:SS 转分钟 ---------
    def to_minutes(self, t: str) -> int:
        dt = datetime.strptime(t, "%H:%M:%S")
        return dt.hour * 60 + dt.minute

    # --------- 归一化 ---------
    def normalize(self, values):
        mx = max(values)
        mn = min(values)
        if mx == mn:
            return [1.0] * len(values)
        return [(v - mn) / (mx - mn) for v in values]

    # --------- 计算评分（含 match 指标）---------
    def compute_scores(self, df, weights, user_time_min, arriveBy):

        # 基础 5 项
        df["T_n"] = self.normalize(df["total_time"])
        df["W_n"] = self.normalize(df["walk_time"])
        df["F_n"] = self.normalize(df["fee"])
        df["C_n"] = self.normalize(df["transfer"])
        df["D_n"] = self.normalize(df["total_dist"])

        # --------- 新增 match（与用户时间的差值）---------
        arriveBy = str(arriveBy).lower() == "true"
        if arriveBy:
            # 用户指定“到达” → 比较 end_time
            df["route_time"] = df["end_min"]
        else:
            # 用户指定“出发” → 比较 start_time
            df["route_time"] = df["start_min"]

        df["match_raw"] = (df["route_time"] - user_time_min).abs()
        df["M_n"] = self.normalize(df["match_raw"])

        # --------- 总分 ---------
        df["score"] = (
            weights["time"]     * df["T_n"] +
            weights["walk"]     * df["W_n"] +
            weights["fee"]      * df["F_n"] +
            weights["transfer"] * df["C_n"] +
            weights["distance"] * df["D_n"] +
            weights["match"]    * df["M_n"]
        )

        return df

    # --------- tie-break ---------
    def apply_tie_break(self, df):
        df = df.sort_values(
            by=["score", "total_time", "walk_time", "fee",
                "transfer", "total_dist", "match_raw"],
            ascending=[True] * 7
        )
        return df

    # --------- 主入口 ---------
    def run(self, text: str, time: str, arriveBy: bool, preference: Optional[str] = None):

        if not text.strip():
            return None

        first_line = text.strip().split("\n")[0]
        routes = self.parse_routes(text)
        if not routes:
            return first_line

        # 时间（用户输入）转分钟
        user_time_min = self.to_minutes(time + ":00") if len(time) == 5 else self.to_minutes(time)

        # 提取所有方案
        records = []
        for idx, r in enumerate(routes):
            f = self.extract_features(r)
            f["raw"] = r
            f["idx"] = idx
            f["start_min"] = self.to_minutes(f["start_str"])
            f["end_min"] = self.to_minutes(f["end_str"])
            records.append(f)

        df = pd.DataFrame(records)

        # 权重选择
        if preference in self.preference_weights:
            weights = self.preference_weights[preference]
        else:
            weights = self.default_weights

        # 打分
        df = self.compute_scores(df, weights, user_time_min, arriveBy)

        # 排序
        df = self.apply_tie_break(df)

        # 输出
        output = [first_line + "\n"]
        for rank, row in enumerate(df.itertuples(), 1):
            pref_name = preference if preference else "无偏好"
            output.append(
                f"Rank {rank} | Score: {row.score:.3f} | 距离原定时间差: {row.match_raw:.1f}分钟 | 出行偏好: {pref_name}\n{row.raw}\n"
            )

        return "\n".join(output)


# =========== 测试示例 ===========

if __name__ == "__main__":
#     text = """深圳北站 → 宝能城 (出行方式: TRANSIT)
# 方案 1:时间: 17:45:00 → 18:53:38 (总时长: 68分钟) 步行时间: 68分钟, 步行距离: 4838.81米 换乘: 0次 总距离: 4838.81米
#   步骤1: WALK  深圳北站 → 宝能城     距离: 4838.81米, 时长: 68.0分钟
# 方案 2:时间: 17:46:23 → 18:04:03 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 3:时间: 17:51:50 → 18:09:30 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 4:时间: 17:57:17 → 18:14:57 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 5:时间: 18:02:44 → 18:20:24 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 6:时间: 18:08:11 → 18:25:51 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 7:时间: 18:13:38 → 18:31:18 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 8:时间: 18:19:05 → 18:36:45 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 9:时间: 18:24:32 → 18:42:12 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟
# 方案 10:时间: 18:29:59 → 18:47:39 (总时长: 17分钟) 步行时间: 12分钟, 步行距离: 556.55米 换乘: 0次 总距离: 4443.88米 总费用: 3.00元
#   步骤1: WALK  深圳北站 → 深圳北站     距离: 181.93米, 时长: 4.0分钟
#   步骤2: SUBWAY  深圳北站 → 塘朗  5号线 黄贝岭-赤湾  距离: 3887.33米, 时长: 5.0分钟
#   步骤3: WALK  塘朗 → 宝能城     距离: 374.62米, 时长: 7.0分钟"""

    ranker = Ranking()
    
    planner = Routes()
#     print(ranker.run(
#         text,
#         time="17:45",     # 用户输入时间（24h）
#         arriveBy=False,   # False=按出发时间比较，True=按到达时间比较
#         preference="步行最短"
#     ))


    try:

        a_template = '{{"fromPlace": "深圳北站::22.6137223,114.0242094", "toPlace": "宝能城::22.5934193,113.993249", "time": "17:45", "arriveBy": "false", "mode": "{mode}"}}'

        modes = ['BUS', 'SUBWAY', 'TRANSIT', 'CAR', 'CAR_PICKUP','BICYCLE','TRANSIT,BICYCLE','WALK']

        for mode in modes:

            a = a_template.format( mode=mode)

            # a={"fromPlace":"深圳北站::22.6137223,114.0242094", "toPlace": "宝能城::22.5934193,113.993249","time":"12:15", "arriveBy":"false","mode":"BUS","walkLimit": 600 }


            result = planner.run(a)
                # 用户输入时间（24h）arriveBy=False,   # False=按出发时间比较，True=按到达时间比较preference="步行最短"))
            print(f"Mode: {mode}")
            print(result)
            print("-" * 40)
            print(ranker.run(result,time="17:45",arriveBy=False,preference="步行最短")) 
            print("-" * 40)

    except ValueError as e:
        print(f"参数错误: {e}")