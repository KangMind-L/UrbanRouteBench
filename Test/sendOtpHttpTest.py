import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Src.sendGetHttp import OTPPlanner


if __name__ == "__main__":
    # 初始化 OTPPlanner 对象
    planner = OTPPlanner(
        from_place="22.578616343644665,113.86976723025911",
        to_place="22.663841801933415,113.86661334699603",
        time="6:02pm",
        date="03-09-2025"
    )

    # 发送请求
    response = planner.make_otp_request()

    """
    打印响应结果
    """
    if response.status_code == 200:
        print("请求成功！")
        print("响应内容：")
        print(response.json().get("plan"))
        print(response.requestParameters)
    else:
        print(f"请求失败，状态码: {response.status_code}")
