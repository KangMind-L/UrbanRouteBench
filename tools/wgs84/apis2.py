import pandas as pd
from pandas import DataFrame
from typing import Optional
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

class Wgs84:
    def __init__(self,path="D:\project\Python\TripPlannerGPT\database\data\point_excel.csv"):
        self.path = path
        self.data = pd.read_csv(self.path).dropna()[['名称','纬度','经度']]
        print("坐标转换工具已加载！")


    def load_db(self):
        self.data = pd.read_csv(self.path).dropna()


    def run(self, name:str):
        # 1. 初始化客户端（必须设置自定义 user_agent）
        geolocator = Nominatim(
            user_agent="my_app_name",  # 替换为你的应用名称
            timeout=10  # 超时时间（秒）
        )

        # 2. 启用请求速率限制（遵守API规则）
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

        # 3. 获取地点经纬度
        try:
            query = f"{name}, 深圳市"
            location = geocode(query)
            # location = geocode(name)  # 替换为你的查询地址
            if location:
                return name+":"f"{location.latitude},{location.longitude}"
            else:
                return
        except Exception as e:
            return

        return 

# 使用示例
if __name__ == "__main__":
    Wgs84 = Wgs84()  # 创建实例
    print(Wgs84.run("中国海油月亮湾加油站") )
    print(Wgs84.run("多家福商城"))  # 输出: 高新奇南门::22.57697992,113.9208391
    print(Wgs84.run("新村后门"))   # 输出: None
    print(Wgs84.run("南山天虹商场")) 

