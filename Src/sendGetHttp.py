import requests


class OTPPlanner:
    def __init__(self, from_place, to_place, time, date, mode="TRANSIT,WALK", arrive_by="false", show_intermediate_stops="true"):
        """
        初始化 OTP 规划请求的参数
        """
        self.from_place = from_place
        self.to_place = to_place
        self.time = time
        self.date = date
        self.mode = mode
        self.arrive_by = arrive_by
        self.show_intermediate_stops = show_intermediate_stops

    def make_otp_request(self):
        """
        发送 OTP 规划请求并返回响应结果
        """
        base_url = "http://localhost:8080/otp/routers/default/plan"
        params = {
            "fromPlace": self.from_place,
            "toPlace": self.to_place,
            "time": self.time,
            "date": self.date,
            "mode": self.mode,
            "arriveBy": self.arrive_by,
            "showIntermediateStops": self.show_intermediate_stops,
        }
        response = requests.get(base_url, params=params)
        return response

def send_otp_request(requestParameters):
    # 初始化 OTPPlanner 对象
    planner = OTPPlanner(
        from_place=requestParameters["from_place"],
        to_place=requestParameters["to_place"],
        time=requestParameters["time"],
        date=requestParameters["date"]
    )

    # 发送请求
    response = planner.make_otp_request()

    """
    打印响应结果
    """
    if response.status_code == 200:
        print("请求成功！")
        # print("响应内容：")
        # print(response.json().get("plan"))
        # print(response.requestParameters)
        
        return response
    else:
        print(f"请求失败，状态码: {response.status_code}")

