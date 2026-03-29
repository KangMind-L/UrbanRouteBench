import re
import requests
import ast
import math
from datetime import datetime, timezone, timedelta
import json
from typing import Dict, Optional, Any

def ms_to_hhmmss(ms):
    if not ms:
        return ""
    # 添加8小时（8 * 3600 * 1000毫秒）
    dt = datetime.fromtimestamp(ms / 1000) + timedelta(hours=8)
    return dt.strftime("%H:%M:%S")
from datetime import datetime

def parse_time_flexible(time_str):
    """兼容 'HH:MM' 和 'HH:MM:SS' 两种格式"""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间字符串: {time_str}")

# 使用示例
depart_time_str = "16:05"      # 或 "16:05:27"
depart_time = parse_time_flexible(depart_time_str)
print(depart_time.time())  # 输出: 16:05:00 或 16:05:27
# 辅助函数应该定义为普通函数，而不是类方法
def extract_plan_lists_by_mode(result: str):
    """
    将路径规划结果解析成 list[dict] 形式
    """
    if not result:
        return []

    mode_pattern = re.compile(r"(?:\n|^).*?\(出行方式:\s*([A-Z_,]+)\)")
    plan_pattern = re.compile(
        r"(方案\s*\d+[:：]\s*时间[:：]\s*(\d{2}:\d{2}:\d{2})\s*→\s*(\d{2}:\d{2}:\d{2}).*?)(?=\n方案\s*\d+[:：]|$)",
        re.S
    )

    all_modes = []
    mode_positions = [(m.start(), m.group(1)) for m in mode_pattern.finditer(result)]
    mode_positions.append((len(result), None))

    for i in range(len(mode_positions) - 1):
        start_pos, mode_name = mode_positions[i]
        end_pos, _ = mode_positions[i + 1]
        mode_text = result[start_pos:end_pos]

        plans = []
        for m_plan in plan_pattern.finditer(mode_text):
            plan_text = m_plan.group(1).strip()
            start_time = datetime.strptime(m_plan.group(2), "%H:%M:%S")
            end_time = datetime.strptime(m_plan.group(3), "%H:%M:%S")
            plans.append({
                "startTime": start_time,
                "endTime": end_time,
                "text": plan_text
            })

        if plans:
            all_modes.append({
                "mode": mode_name,
                "plans": plans
            })

    return all_modes

def get_plan_end_time(plan: dict) -> datetime:
    """
    plan 来自 extract_plans
    返回 datetime
    """
    return plan.get("endTime")

def renumber_plan_text(plan_text: str, new_index: int) -> str:
    """
    将方案文本中的"方案 X"统一改为"方案 {new_index}"
    """
    return re.sub(
        r"方案\s*\d+([:：])",
        f"方案 {new_index}\\1",
        plan_text,
        count=1
    )
from datetime import datetime, timedelta

def check_plan_time_sequence(plan_text, max_wait_minutes=40):
    """
    校验方案中各步骤的时间顺序是否合理
    返回 True 表示可以保存，False 表示应丢弃
    """

    # 提取所有步骤的时间 (开始-结束)
    step_times = []
    for line in plan_text.splitlines():
        if "步骤" in line and "-" in line:
            # 例：17:44:07-17:49:51
            try:
                time_part = line.split()[-3]  # 倒数第三个通常是时间段
                start_str, end_str = time_part.split("-")
                start = datetime.strptime(start_str, "%H:%M:%S")
                end = datetime.strptime(end_str, "%H:%M:%S")
                step_times.append((start, end))
            except Exception:
                return False  # 时间解析失败，直接丢弃

    # 没有或只有一步，不需要校验
    if len(step_times) <= 1:
        return True

    for i in range(len(step_times) - 1):
        curr_start, curr_end = step_times[i]
        next_start, _ = step_times[i + 1]

        # 规则 1：当前步骤出发 < 到达，直接认为合法（不做拦截）
        if curr_start < curr_end:
            pass

        # 同一天情况
        if next_start >= curr_end:
            wait = next_start - curr_end
            if wait > timedelta(minutes=max_wait_minutes):
                return False
        else:
            # 跨天情况：下一步出发时间 +1天
            next_start_plus = next_start + timedelta(days=1)
            wait = next_start_plus - curr_end
            if wait > timedelta(minutes=max_wait_minutes):
                return False

    return True

def filter_mode_plans(mode_plans):
    """
    对 mode_plans 进行过滤
    """
    filtered_modes = []

    for mode_block in mode_plans:
        mode_name = mode_block["mode"]
        plans = mode_block["plans"]

        valid_plans = []

        for plan in plans:
            plan_text = plan["text"]

            if "未能搜索到相关路径" in plan_text:
                continue

            scheme_count = plan_text.count("方案 ")
            step_lines = [line for line in plan_text.splitlines() if line.strip().startswith("步骤")]
            step_modes = [line.split()[1] for line in step_lines if len(line.split()) >= 2]

            if mode_name in ["BUS", "SUBWAY", "TRANSIT"] and scheme_count == 1 and step_modes == ["WALK"]:
                continue

            if mode_name == "TRANSIT,BICYCLE" and step_modes and all(m == "BICYCLE" for m in step_modes):
                continue
            valid_plans.append(plan)
        # if check_plan_time_sequence(plan_text):
        


        if valid_plans:
            renumbered_plans = []
            for idx, plan in enumerate(valid_plans, start=1):
                new_plan = dict(plan)
                new_plan["text"] = renumber_plan_text(plan["text"], idx)
                renumbered_plans.append(new_plan)

            filtered_modes.append({
                "mode": mode_name,
                "plans": renumbered_plans
            })

    return filtered_modes

def filter_plans_by_depart_time(mode_plans, max_arrive_time):
    """
    过滤掉到达时间 > 用户设定最晚到达时间的方案
    """
    
    filtered_modes = []
    min_t = max_arrive_time.time()

    for mode_block in mode_plans:
        mode_name = mode_block["mode"]
        plans = mode_block["plans"]

        valid_plans = []

        for plan in plans:
            end_time = plan.get("endTime")
            if end_time is None:
                continue

            if end_time.time() <= min_t:
                valid_plans.append(plan)

        if valid_plans:
            filtered_modes.append({
                "mode": mode_name,
                "plans": valid_plans
            })

    return filtered_modes

def plans_to_text(mode_plans, from_name, to_name):
    """
    将过滤后的 mode_plans 转换为字符串
    """
    blocks = []

    for mode_block in mode_plans:
        mode_name = mode_block["mode"]
        plans = mode_block["plans"]

        blocks.append(f"{from_name} → {to_name} (出行方式: {mode_name})")

        for plan in plans:
            blocks.append(plan["text"])

        blocks.append("")

    return "\n".join(blocks).strip()

#只有一段路径
class Routes:
    ALL_MODES = [
    'BUS',
    'SUBWAY',
    'TRANSIT',
    'CAR',
    'CAR_PICKUP',
    'TRANSIT,BICYCLE',
    ]

    DEFAULT_PARAMETERS = {
        "date": datetime.now().strftime("%m-%d-%Y"),  # 默认当天日期
        "mode": ALL_MODES,
        "arriveBy": "false",
        "fromPlace": "",
        "toPlace": "",
        "time": "",  # 当前时间

        # "time": datetime.now().strftime("%I:%M%p").lower(),  # 当前时间
        "maxTransfers": "4",
        "numItineraries": "10",
        "stayMinutes":"30",
        "window":"0"
    }

    def __init__(self):
        print("路径规划器已初始化")

    def validate_parameters(self):
        """验证必要参数是否提供"""
        if not self.parameters["fromPlace"] or not self.parameters["toPlace"]:
            raise ValueError("必须提供 fromPlace 和 toPlace 参数")
        
        for place in ["fromPlace", "toPlace"]:
            if "::" not in self.parameters[place]:
                raise ValueError(f"{place} 格式应为 '名称::纬度,经度'")

    def make_otp_request(self) -> Optional[Dict]:
        """
        发送OTP规划请求
        """
        base_url = "http://localhost:8080/otp/routers/default/plan"
        try:
            response = requests.get(base_url, params=self.parameters, timeout=10)
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None

    def extract_itinerary_info(self, response_data: Dict) -> str:
        """
        从响应数据提取格式化行程信息
        """
        if not response_data or "plan" not in response_data:
            return ''

        result = []
        plan = response_data["plan"]
        requestParameters = response_data["requestParameters"]
        
        from_name = requestParameters['fromPlace'].split('::')[0] if '::' in requestParameters['fromPlace'] else requestParameters['fromPlace']
        to_name = requestParameters['toPlace'].split('::')[0] if '::' in requestParameters['toPlace'] else requestParameters['toPlace']
        
        requestParameters_info = [
            f"{from_name} → {to_name} (出行方式: {requestParameters['mode']})"
        ]

        for idx, itinerary in enumerate(plan["itineraries"], 1):
            start = datetime.fromtimestamp(itinerary["startTime"]/1000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
            end = datetime.fromtimestamp(itinerary["endTime"]/1000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

            total_distance = 0
            walk_distance = 0
            itinerary_info = []
            
            if requestParameters["mode"] == "CAR_PICKUP":
                for leg in itinerary["legs"]:
                    total_distance += leg['distance']
                    if leg.get("mode") == "WALK":
                        walk_distance += leg['distance']
                
                fare = 10 + math.ceil(((total_distance-walk_distance)/1000 - 2)) * 2.4 if (total_distance/1000) > 2 else 10
                
                itinerary_info = [
                    f"\n方案1: 时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟{itinerary['duration']%60}秒)"
                    f"  总距离: {total_distance:.2f}米"
                    f"  步行距离: {walk_distance:.2f}米"
                    f" 步行时间: {itinerary['walkTime']//60}分钟{itinerary['walkTime']%60}秒, 步行距离: {itinerary['walkDistance']}米"
                    f"  总费用: {fare:.2f}元"
                ]
                
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {'CAR_PICKUP' if leg['mode'] == 'CAR' else leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  距离: {leg['distance']}米,"
                        f"  {ms_to_hhmmss(leg.get('startTime', ''))}-{ms_to_hhmmss(leg.get('endTime', ''))}"
                        f"  时长: {int(leg['duration']//60)}分钟{int(leg['duration']%60)}秒"
                    ]
                    itinerary_info.extend(leg_info)
                    
            elif requestParameters["mode"] == "CAR":
                total_distance = 0
                for leg in itinerary["legs"]:
                    total_distance += leg["distance"]
                
                itinerary_info = [
                    f"\n方案1: 时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟{itinerary['duration']%60}秒)"
                    f"  总距离: {total_distance:.2f}米"
                    f"  总费用: {(total_distance * 0.7) / 1000:.2f}元"
                ]
                
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: CAR"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  距离: {leg['distance']}米,"
                        f"  {ms_to_hhmmss(leg.get('startTime', ''))}-{ms_to_hhmmss(leg.get('endTime', ''))}"
                        f"  时长: {int(leg['duration']//60)}分钟{int(leg['duration']%60)}秒"
                    ]
                    itinerary_info.extend(leg_info)
                    
            elif requestParameters["mode"] in ["BICYCLE", "TRANSIT,BICYCLE"]:
                for leg in itinerary["legs"]:
                    total_distance += leg['distance']
                
                fare_text = ""
                if 'fare' in itinerary and 'legProducts' in itinerary['fare']:
                    total_fare = sum(
                        p['amount']['cents'] for leg in itinerary.get('fare', {}).get('legProducts', []) for p in leg.get('products', [])) / 100
                    fare_text = f" 总费用: {total_fare:.2f}元"
                
                itinerary_info = [
                    f"\n方案 {idx}:"
                    f"时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟{itinerary['duration']%60}秒)"
                    f" 步行时间: 0分钟, 步行距离: 0米"
                    f" 换乘: {itinerary['transfers']}次"
                    f" 总距离: {total_distance:.2f}米" + fare_text
                ]
                
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}"
                        f"  距离: {leg['distance']}米,"
                        f"  {ms_to_hhmmss(leg.get('startTime', ''))}-{ms_to_hhmmss(leg.get('endTime', ''))}"
                        f"  时长: {int(leg['duration']//60)}分钟{int(leg['duration']%60)}秒"
                    ]
                    itinerary_info.extend(leg_info)
                    
            else:
                for leg in itinerary["legs"]:
                    total_distance += leg['distance']
                
                fare_text = ""
                if itinerary.get('fare') and 'legProducts' in itinerary.get('fare', {}):
                    total_fare = sum(
                        p.get('amount', {}).get('cents', 0) for leg in itinerary.get('fare', {}).get('legProducts', []) for p in leg.get('products', [])) / 100
                    fare_text = f" 总费用: {total_fare:.2f}元"
                
                itinerary_info = [
                    f"\n方案 {idx}:"
                    f"时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟{itinerary['duration']%60}秒)"
                    f" 步行时间: {itinerary['walkTime']//60}分钟{itinerary['walkTime']%60}秒, 步行距离: {itinerary['walkDistance']}米"
                    f" 换乘: {itinerary['transfers']}次"
                    f" 总距离: {total_distance:.2f}米" + fare_text
                ]
                
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}"
                        f"  距离: {leg['distance']}米,"
                        f"  {ms_to_hhmmss(leg.get('startTime', ''))}-{ms_to_hhmmss(leg.get('endTime', ''))}"
                        f"  时长: {int(leg['duration']//60)}分钟{int(leg['duration']%60)}秒"
                    ]
                    itinerary_info.extend(leg_info)
            
            result.append("\n".join(itinerary_info))

        if len(result) != 0:
            result = requestParameters_info + result
        else:
            result = requestParameters_info + ["未能搜索到相关路径"]
        
        return "".join(result)
    
    def route_search(self, parameters) -> str:
        """
        基础路径搜索方法
        """
        if isinstance(parameters, str):
            parameters = json.loads(parameters)

        mode_list = parameters.get("mode")


        all_results = []

        for mode in mode_list:
            self.parameters = {}

            for key in self.DEFAULT_PARAMETERS:
                if key in parameters and parameters[key] != "":
                    self.parameters[key] = parameters[key]
                else:
                    self.parameters[key] = self.DEFAULT_PARAMETERS[key]

            self.parameters["mode"] = mode

            self.validate_parameters()
            response_data = self.make_otp_request()

            if response_data:
                result = self.extract_itinerary_info(response_data)
                all_results.append(result)
            else:
                all_results.append(f"\nMode: {mode}\n路径规划请求失败")

        if not any(result and (not isinstance(result, str) or result.strip()) for result in all_results):
            all_results = ["所有路径规划请求都失败或返回空结果"]
        return "\n\n".join(all_results)
    
    def run(self, parameters) -> str:
        """
        主运行方法，整合途经点和时间窗口逻辑
        """
        if isinstance(parameters, str):
            parameters = json.loads(parameters)
        
        from_place = parameters.get("fromPlace")
        to_place = parameters.get("toPlace")
        via_place = parameters.get("viaPlace")
        via_name = parameters.get("viaName", "")
        depart_time_str = parameters.get("time")
        window = int(parameters.get("window", 0))
        stay_minutes = int(parameters.get("stayMinutes", 30))
        user_mode = parameters.get("mode", "")
        from_name = parameters.get("fromName", from_place.split("::")[0] if "::" in from_place else from_place)
        to_name = parameters.get("toName", to_place.split("::")[0] if "::" in to_place else to_place)
        
        if via_place and not via_name:
            via_name = via_place.split("::")[0] if "::" in via_place else via_place
        
        if from_place is None or to_place is None:
            return ""
        
        # depart_time = datetime.strptime(depart_time_str, "%H:%M:%S")
        depart_time = parse_time_flexible(depart_time_str)
        arrival_time = depart_time + timedelta(minutes=window)
        
        if not user_mode or (isinstance(user_mode, str) and user_mode.strip() == ""):
            mode_list = self.ALL_MODES
        elif isinstance(user_mode, list):
            mode_list = user_mode
        elif isinstance(user_mode, str) and "|" in user_mode:
            mode_list = [m.strip() for m in user_mode.split("|") if m.strip()]
        else:
            mode_list = [user_mode]
        
        # =========================
        # 情况 1：无途经点
        # =========================
        if not via_place or via_place.strip() == "":
            params = {
                "fromPlace": from_place,
                "toPlace": to_place,
                "time": depart_time_str,
                "mode": mode_list
            }
            
            result = self.route_search(params)
            # print(result)
            
            plans = filter_mode_plans(extract_plan_lists_by_mode(result))
            if window != 0:
                plans = filter_plans_by_depart_time(plans, arrival_time)
            
            if len(plans) == 0:
                return "查询路径失败，找不到符合需求的路径"
            
            return plans_to_text(plans, from_name, to_name)
        
        # =========================
        # 情况 2：有途经点
        # =========================
        else:
            all_results = []
            
            params_1 = {
                "fromPlace": from_place,
                "toPlace": via_place,
                "time": depart_time_str,
                "arriveBy": "false",
                "mode": mode_list
            }
            
            result_1 = self.route_search(params_1)
            mode_plans_1 = filter_mode_plans(extract_plan_lists_by_mode(result_1))
            
            if window != 0:
                mode_plans_1 = filter_plans_by_depart_time(mode_plans_1, arrival_time)
            
            if len(mode_plans_1) == 0:
                return "查询路径失败，找不到符合需求的路径"
            
            for mode_block in mode_plans_1:
                first_leg_mode = mode_block["mode"]
                first_leg_texts = [p["text"] for p in mode_block["plans"]]
                
                seen_second_leg = set()
                texts_to_add = []
                plan_idx = 1
                
                for first_leg_plan in mode_block["plans"]:
                    arrive_v_time = get_plan_end_time(first_leg_plan)
                    arrive_v_time = arrive_v_time + timedelta(minutes=stay_minutes)
                    
                    params_2 = {
                        "fromPlace": via_place,
                        "toPlace": to_place,
                        "time": arrive_v_time.strftime("%H:%M:%S"),
                        "arriveBy": "false",
                        "mode": [first_leg_mode]
                    }
                    
                    result_2 = self.route_search(params_2)
                    mode_plans_2 = filter_mode_plans(extract_plan_lists_by_mode(result_2))
                    
                    if window != 0:
                        mode_plans_2 = filter_plans_by_depart_time(mode_plans_2, arrival_time)
                    
                    for second_mode_block in mode_plans_2:
                        for second_leg_plan in second_mode_block["plans"]:
                            key = (
                                second_mode_block["mode"],
                                second_leg_plan["startTime"],
                                second_leg_plan["endTime"]
                            )
                            if key not in seen_second_leg:
                                seen_second_leg.add(key)
                                
                                text = second_leg_plan["text"]
                                text = re.sub(
                                    r"方案\s*\d+:",
                                    f"方案 {plan_idx}:",
                                    text,
                                    count=1
                                )
                                texts_to_add.append(text)
                                plan_idx += 1
                
                if texts_to_add:
                    block = (
                        f"{from_name} → {via_name} (出行方式: {first_leg_mode})\n"
                        + "\n".join(first_leg_texts)
                        + "\n\n"
                        + f"{via_name} → {to_name} (出行方式: {first_leg_mode})\n"
                        + "\n".join(texts_to_add)
                    )
                    all_results.append(block)
            
            if not all_results:
                return "查询路径失败，找不到符合需求的路径"
            
            return "\n\n".join(all_results)

# 使用示例
if __name__ == "__main__":
    # 定义请求参数 (只需覆盖默认值中需要修改的参数)
    
    try:
        planner = Routes()
        modes = [
            '',
            # 'BUS',
            # 'SUBWAY',
            # 'BUS|SUBWAY',
            # 'TRANSIT,BICYCLE'
        ]
        for mode in modes:
            print("="*60)
            print("测试无途经点场景")
            print("="*60)
            
            a_template = '{{"fromPlace": "深圳北站::22.6537223,114.0242094", "toPlace": "宝能城::22.5934193,113.993249", "time": "19:00", "mode": "{mode}"}}'

            a = a_template.format(mode=mode)
            result = planner.run(a)
            print(f"Mode: {mode}")
            print(result)
            print("-" * 40)
            
            print("\n" + "="*60)
            print("测试无途经点 + 时间窗口场景")
            print("="*60)
            
            window_template = '{{"fromPlace": "深圳北站::22.6537223,114.0242094", "toPlace": "宝能城::22.5934193,113.993249", "time": "19:00", "mode": "{mode}", "window": "60"}}'
            
            a = window_template.format(mode=mode)
            result = planner.run(a)
            print(f"Mode: {mode}, Window: 30分钟")
            print(result)
            print("-" * 40)
            
            print("\n" + "="*60)
            print("测试带途经点场景")
            print("="*60)
            
            via_template = '{{"fromPlace": "深圳北站::22.6537223,114.0242094", "toPlace": "市民中心::22.543096,114.057865", "viaPlace": "宝能城::22.5934193,113.993249", "time": "19:00", "mode": "{mode}", "stayMinutes": 20}}'
            
            a = via_template.format(mode=mode)
            result = planner.run(a)
            print(f"Mode: {mode} (带途经点)")
            print(result)
            print("-" * 40)
            
            print("\n" + "="*60)
            print("测试带途经点 + 时间窗口场景")
            print("="*60)
            
            # via_window_template = '{{"fromPlace": "深圳北站::22.6537223,114.0242094", "toPlace": "市民中心::22.543096,114.057865", "viaPlace": "宝能城::22.5934193,113.993249", "time": "19:00", "mode": "{mode}", "stayMinutes": 20, "window": "180"}}'
            via_window_template = '{{"fromPlace": "深圳市福田区福苑小学::22.51101389,114.0453771", "toPlace": "天虹商场(深圳松岗店)::22.76623001,113.8471188", "viaPlace": "山海湾::22.56631072,114.4607667", "time": "17:22:01", "mode": "{mode}", "stayMinutes": 35, "window": "0"}}'
            
            a = via_window_template.format(mode=mode)
            result = planner.run(a)
            print(f"Mode: {mode}, Window:40分钟 (带途经点)")
            print(result)
            print("-" * 40)
                    
    except ValueError as e:
        print(f"参数错误: {e}")
    except Exception as e:
        print(f"运行错误: {e}")