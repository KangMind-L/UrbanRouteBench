
import requests
import math
from datetime import datetime
from typing import Dict, Optional,Any
import json
from datetime import datetime, timezone, timedelta
class Routes:
    DEFAULT_PARAMETERS = {
        "date": datetime.now().strftime("%m-%d-%Y"),  # 默认当天日期
        "mode": "TRANSIT,WALK",
        "arriveBy": "false",
        "fromPlace": "",
        "toPlace": "",
        "time": datetime.now().strftime("%I:%M%p").lower(),  # 当前时间
        "maxTransfers": "4",
        "numItineraries": "10",
        # "showIntermediateStops": "true",
        # "wheelchair": "false",
        # "walkSpeed": "1.34",  # 默认步行速度(m/s)
        # "optimize": "QUICK",  # 优化方式: QUICK/FLAT/SAFE
        # "walkReluctance": "5.0",
        # "maxWalkDistance": "1500"
    }

    def __init__(self):
        """
        初始化路径规划器
        
        Args:
            parameters (Dict[str, str]): 请求参数字典，包含以下可选键：
                - fromPlace: 起点坐标 (格式: "名称::纬度,经度")
                - toPlace: 终点坐标 (格式: "名称::纬度,经度")
                - date: 日期 (格式: "MM-DD-YYYY")
                - time: 时间 (格式: "HH:MMam/pm")
                - mode: 交通模式 (默认: "TRANSIT,WALK")
                - arriveBy: 是否指定到达时间 (默认: "false")
                - maxTransfers: 最大换乘次数 (默认: "3")
                - numItineraries: 返回方案数量 (默认: "3")
                - showIntermediateStops: 是否显示中间站点 (默认: "true")
                - wheelchair: 是否轮椅无障碍 (默认: "false")
                - walkSpeed: 步行速度 m/s (默认: "1.34")
                - optimize: 优化方式 (QUICK/FLAT/SAFE, 默认: "QUICK")
        """
        # self.parameters = {**self.DEFAULT_PARAMETERS, **parameters}
        # self.validate_parameters()
        print("路径规划器已初始化")

    def validate_parameters(self):
        """验证必要参数是否提供"""
        if not self.parameters["fromPlace"] or not self.parameters["toPlace"]:
            raise ValueError("必须提供 fromPlace 和 toPlace 参数")
        
        # 验证坐标格式
        for place in ["fromPlace", "toPlace"]:
            if "::" not in self.parameters[place]:
                raise ValueError(f"{place} 格式应为 '名称::纬度,经度'")

    def make_otp_request(self) -> Optional[Dict]:
        """
        发送OTP规划请求
        
        Returns:
            Optional[Dict]: 成功返回JSON响应，失败返回None
        """
        base_url = "http://localhost:8080/otp/routers/default/plan"
        try:
            response = requests.get(base_url, params=self.parameters, timeout=10)
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None

    @staticmethod
    def extract_itinerary_info(response_data: Dict) -> str:
        """
        从响应数据提取格式化行程信息
        
        Args:
            response_data (Dict): OTP API响应数据
            
        Returns:
            str: 格式化后的行程信息
        """
        if not response_data or "plan" not in response_data:
            return ''

        result = []
        plan = response_data["plan"]
        requestParameters=response_data["requestParameters"]
        requestParameters_info = [
                    f"{requestParameters['fromPlace'].split('::')[0]} → {requestParameters['toPlace'].split('::')[0]} (出行方式: {requestParameters['mode']})"
        ]

        # print(requestParameters_info)
        # 处理每个行程方案
        for idx, itinerary in enumerate(plan["itineraries"], 1):


            start = datetime.fromtimestamp(itinerary["startTime"]/1000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

            end = datetime.fromtimestamp(itinerary["endTime"]/1000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

           # 计算总距离（步行距离 + 各段交通距离）
            total_distance = 0  # 初始化步行距离
            walk_distance = 0
            walk_time = 0
            itinerary_info = []
            leg_info = []
            
            if requestParameters["mode"] == "CAR_PICKUP":


                
                for leg in itinerary["legs"]:
                    total_distance += leg['distance']  # 累加每段交通距离
                    
                    # 如果是步行路段，累加步行距离
                    if leg.get("mode") == "WALK":
                        walk_distance += leg['distance']
                        walk_time += leg['duration']
                        # print(walk_distance)
                
                # 构建行程信息
                fare = 10 + math.ceil(((total_distance-walk_distance)/1000 - 2)) * 2.4 if (total_distance/1000) > 2 else 10


                         
                itinerary_info =[
                    f"\n方案1: 时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟)"
                    f"  总距离: {total_distance:.2f}米"
                    f"  步行距离: {walk_distance:.2f}米"
                    f"  步行时间: {walk_time//60}分钟"
                    f"  总费用: {fare:.2f}元"
                ]
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {'CAR_PICKUP' if leg['mode'] == 'CAR' else leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  距离: {leg['distance']}米, 时长: {leg['duration']//60}分钟"
                    ]
                
                    itinerary_info.extend(leg_info)
                
                

            elif requestParameters["mode"] == "CAR":

                leg_info = []          # ← 一定要初始化
                total_distance = 0

                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    total_distance += leg["distance"]

                    leg_info.append(
                        f"  步骤{leg_id}: CAR"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  距离: {leg['distance']}米, 时长: {leg['duration']//60}分钟"
                    )

                # 构建行程信息
                itinerary_info = [
                    f"\n方案1: 时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟)"
                    f"  总距离: {total_distance:.2f}米"
                    f"  总费用: {(total_distance * 0.7) / 1000:.2f}元"
                ]

                itinerary_info.extend(leg_info)

                
            elif requestParameters["mode"] == "BICYCLE":

                for leg in itinerary["legs"]:
                    total_distance += leg['distance']  # 累加每段交通距离

                itinerary_info = [
                        f"\n方案 {idx}:" \
                        f"时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟)" \
                        f" 步行时间: 0分钟, 步行距离: 0米" \
                        f" 换乘: {itinerary['transfers']}次" \
                        f" 总距离: {total_distance:.2f}米" \
                        + (f" 总费用: {sum(p['amount']['cents'] for leg in itinerary.get('fare', {}).get('legProducts', []) for p in leg.get('products', [])) / 100:.2f}元" 
                        if 'fare' in itinerary and 'legProducts' in itinerary['fare'] 
                        else "")
                    ]
                # 处理每段行程
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}"
                        f"  距离: {leg['distance']}米, 时长: {leg['duration']//60}分钟"
                    ]
                
                    itinerary_info.extend(leg_info)
                # if leg['mode'] != "WALK":
                #     leg_info.append(f"  路线: {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}")
            elif requestParameters["mode"] == "TRANSIT,BICYCLE": 

                for leg in itinerary["legs"]:
                    total_distance += leg['distance']  # 累加每段交通距离

                itinerary_info = [
                        f"\n方案 {idx}:" \
                        f"时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟)" \
                        f" 步行时间: 0分钟, 步行距离: 0米" \
                        f" 换乘: {itinerary['transfers']}次" \
                        f" 总距离: {total_distance:.2f}米" \
                        + (f" 总费用: {sum(p['amount']['cents'] for leg in itinerary.get('fare', {}).get('legProducts', []) for p in leg.get('products', [])) / 100:.2f}元" 
                        if 'fare' in itinerary and 'legProducts' in itinerary['fare'] 
                        else "")
                    ]
                # 处理每段行程
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}"
                        f"  距离: {leg['distance']}米, 时长: {leg['duration']//60}分钟"
                    ]
                
                    itinerary_info.extend(leg_info)
                # if leg['mode'] != "WALK":
                #     leg_info.append(f"  路线: {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}")
                
            else: 

                for leg in itinerary["legs"]:
                    total_distance += leg['distance']  # 累加每段交通距离

                itinerary_info = [
                        f"\n方案 {idx}:" \
                        f"时间: {start} → {end} (总时长: {itinerary['duration']//60}分钟)" \
                        f" 步行时间: {itinerary['walkTime']//60}分钟, 步行距离: {itinerary['walkDistance']}米" \
                        f" 换乘: {itinerary['transfers']}次" \
                        f" 总距离: {total_distance:.2f}米" \
                        + (f" 总费用: {sum(p['amount']['cents'] for leg in itinerary.get('fare', {}).get('legProducts', []) for p in leg.get('products', [])) / 100:.2f}元" 
                        if 'fare' in itinerary and 'legProducts' in itinerary['fare'] 
                        else "")
                    ]
                # 处理每段行程
                for leg_id, leg in enumerate(itinerary["legs"], 1):
                    leg_info = [
                        f"  步骤{leg_id}: {leg['mode']}"
                        f"  {leg['from']['name']} → {leg['to']['name']}"
                        f"  {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}"
                        f"  距离: {leg['distance']}米, 时长: {leg['duration']//60}分钟"
                    ]
                
                    itinerary_info.extend(leg_info)
                # if leg['mode'] != "WALK":
                #     leg_info.append(f"  路线: {leg.get('routeShortName', '')} {leg.get('routeLongName', '')}")
                
            

            result.append("\n".join(itinerary_info))  

        if len(result)!=0:  # 检查结果是否为空
            result=requestParameters_info+result
        else:
            result=requestParameters_info+["未能搜索到相关路径"]
        
        return "".join(result)

    def run(self, parameters) -> str:
        """
        执行完整的路径规划流程
        
        Returns:
            str: 格式化后的行程信息或错误消息
        """

        # 使用转换后的参数
        # self.parameters = str_parameters
        # parameters = json.dumps(a, ensure_ascii=False)
        if isinstance(parameters, dict):
            # 如果是字典，直接使用
            parameters = parameters
        else:
            # 如果是字符串，解析为字典
            parameters = json.loads(parameters)
        self.parameters = {}
        for key in self.DEFAULT_PARAMETERS:
            if key in parameters and parameters[key] != "":
                self.parameters[key] = parameters[key]
            else:
                self.parameters[key] = self.DEFAULT_PARAMETERS[key]

        self.validate_parameters()
        response_data = self.make_otp_request()
        return (
            self.extract_itinerary_info(response_data) 
            if response_data 
            else "路径规划请求失败"
        )


# 使用示例
if __name__ == "__main__":
    # 定义请求参数 (只需覆盖默认值中需要修改的参数)


    try:

        planner = Routes()
        a_template = '{{"fromPlace": "民顺小学::22.63140993,114.0214274", "toPlace": "宝能城::22.5934193,113.993249", "time": "19:00", "arriveBy": "true", "mode": "{mode}"}}'

        modes = ['BUS', 'SUBWAY', 'TRANSIT', 'CAR', 'CAR_PICKUP','BICYCLE','TRANSIT,BICYCLE','WALK']

        for mode in modes:

            a = a_template.format( mode=mode)

            # a={"fromPlace":"深圳北站::22.6137223,114.0242094", "toPlace": "宝能城::22.5934193,113.993249","time":"12:15", "arriveBy":"false","mode":"BUS","walkLimit": 600 }


            result = planner.run(a)
            print(f"Mode: {mode}")
            print(result)
            print("-" * 40)
    except ValueError as e:
        print(f"参数错误: {e}")
        