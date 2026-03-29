from datetime import datetime

from sendGetHttp import OTPPlanner

import json

# 假设 json_data 是已经加载的JSON数据
# 例如：json_data = json.loads(json_string) 或从文件加载

# 提取所需字段的函数


def extract_itinerary_info(json_data):
    
    response_result = ""
    # 检查是否存在 plan 和 itineraries
    if "plan" not in json_data or "itineraries" not in json_data["plan"]:
        print("JSON数据格式不符合预期")
        return

    # 遍历每个行程（itinerary）
    request_Parameters=json_data["requestParameters"]
    from_name=json_data["plan"]["from"]["name"]
    to_name=json_data["plan"]["to"]["name"]
    # print(f"请求参数: {request_Parameters}\t起点: {from_name}\t终点: {to_name}")
    response_result+=f"请求参数: {request_Parameters}\t起点: {from_name}\t终点: {to_name}"
    # print(response_result)
    # print(f"起点: {from_name}")
    # print(f"终点: {to_name}")


    for idx, itinerary in enumerate(json_data["plan"]["itineraries"]):
        # print(f"\n第{idx + 1} 条路径：")
        response_result+=f"\n\n第{idx + 1} 条路径："

        # 提取所需字段

        start_time = itinerary.get("startTime")  # 开始时间
        start_time = datetime.fromtimestamp(int(start_time) / 1000).strftime("%H:%M:%S")
        end_time = itinerary.get("endTime")      # 结束时间
        end_time = datetime.fromtimestamp(int(end_time) / 1000).strftime("%H:%M:%S")
        walk_time = itinerary.get("walkTime")    # 步行时间
        transit_time = itinerary.get("transitTime")  # 公交时间
        walk_distance = itinerary.get("walkDistance")  # 步行距离
        transfers = itinerary.get("transfers")   # 换乘次数

        # 打印提取的字段
        # print(f"开始时间: {start_time}\t结束时间: {end_time}\t步行时间: {walk_time}秒\t公交时间: {transit_time} 秒\t步行距离: {walk_distance} 米\t换乘次数: {transfers}")
        response_result+=f"开始时间: {start_time}\t结束时间: {end_time}\t步行时间: {walk_time}秒\t公交时间: {transit_time} 秒\t步行距离: {walk_distance} 米\t换乘次数: {transfers}"
        # print(f"结束时间: {end_time}")
        # print(f"步行时间: {walk_time} 秒")
        # print(f"公交时间: {transit_time} 秒")
        # print(f"步行距离: {walk_distance} 米")
        # print(f"换乘次数: {transfers}")


        for legId, leg in enumerate(itinerary.get("legs")):
            distance = leg.get("distance")
            generalizedCost = leg.get("generalizedCost")
            mode = leg.get("mode")
            route = leg.get("route")
            form_name=leg.get("from").get("name")
            to_name=leg.get("to").get("name")
            # print(f"第{legId+1}段行程：")
            response_result+=f"\n\t第{legId+1}段行程："
            # print(f"起点: {form_name}\t终点: {to_name}\t距离: {distance}\t成本: {generalizedCost}\t交通方式: {mode}\t路线: {route}")
            response_result+=f"[{form_name},{to_name},{distance},{generalizedCost},{mode},{route}]" 

            # print(f"终点: {to_name}")
            # print(f"距离: {distance}")
            # print(f"成本: {generalizedCost}")
            # print(f"交通方式: {mode}")
            # print(f"路线: {route}")

            # if mode=="WALK":
            #     response_result+="\n\t\t"
            #     for stepId, step in enumerate(leg.get("steps")):
            #         response_result+="["
            #         distance = step.get("distance")
            #         relativeDirection = step.get("relativeDirection")
            #         streerName = step.get("streerName")
            #         absoluteDirection = step.get("absoluteDirection")
            #         # print(f"第{stepId+1}步：")
            #         # print(f"距离: {distance}\t相对方向: {relativeDirection}\t街道名称: {streerName}\t绝对方向: {absoluteDirection}")
            #         response_result+=f"{distance}, {relativeDirection}, {streerName}, {absoluteDirection}; "
            #         # print(f"相对方向: {relativeDirection}")
            #         # print(f"街道名称: {streerName}")
            #         # print(f"绝对方向: {absoluteDirection}")
            #         response_result+="]"

            # else:
            #     # print(f"公共交通：")
            #     response_result+="["+leg.get("routeShortName")+"]"
            #     response_result+="\n\t\t"
            #     for intermediateStopId, intermediateStop in enumerate(leg.get("intermediateStops")):
            #         response_result+="["
            #         name = intermediateStop.get("name")
            #         stopId = intermediateStop.get("stopId")
            #         stopsequence = intermediateStop.get("stopSequence")
            #         # print(f"第{intermediateStopId}个中间站点：")
            #         # print(f"站点名称: {name}\t站点ID: {stopId}\t站点序号: {stopsequence}")
            #         response_result+=f"{name}, {stopId}, {stopsequence}; "
            #         # print(f"站点ID: {stopId}")
            #         # print(f"站点序号: {stopsequence}")
            #         response_result+="]"
            
    # print(response_result)
    return response_result   






# 调用函数处理JSON数据
# 假设 json_data 是已经加载的JSON数据
def cope_send_otp_request():
    # 初始化 OTPPlanner 对象
    planner = OTPPlanner(
        from_place="起点名字::22.578616343644665,113.86976723025911",
        to_place="终点名字::22.663841801933415,113.86661334699603",
        time="6:02pm",
        date="03-09-2025"
    )

    # 发送请求
    response = planner.make_otp_request()

    """
    打印响应结果
    """
    if response.status_code == 200:
        # print("请求成功！")
        # print("响应内容：")
        # print(response.json())
        response = extract_itinerary_info(response.json())
        return response
        # print(response.requestParameters)
    else:
        print(f"请求失败，状态码: {response.status_code}")





print(cope_send_otp_request())