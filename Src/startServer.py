import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deepseek import sendTodeepSeek
from responseCopeNew import extract_itinerary_info
from sendGetHttp import send_otp_request
if __name__=="__main__":
    requestParameters = {
        "from_place": "22.578616343644665,113.86976723025911",
        "to_place": "22.663841801933415,113.86661334699603",
        "time": "6:02pm",
        "date": "03-09-2025"
    }
    str="我想今天下午18:00从大益广场出发,到黄麻布总站,请给我规划路线"
    while True:
        myinput=input("请说您的行程计划：")
        if myinput=="exit":
            print("再见！")
            break
        resp=sendTodeepSeek(myinput)
        print(resp)
        if True:
            response=send_otp_request(requestParameters)
            response = extract_itinerary_info(response.json())
            print(response)
        resp=sendTodeepSeek(response)
        print(resp)
        print("************************************")