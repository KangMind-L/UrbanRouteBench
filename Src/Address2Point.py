import requests

class Geocoding:
    def __init__(self, api_key):
        self.api_key =     api_key = "7a7cd7f85501689421ef31c632b1153c"  # 替换为你的高德 API Key

        self.base_url = "https://restapi.amap.com/v3/geocode/geo"
    def geocode(self, address):
        # 构造请求参数
        params = {
            "key": self.api_key,
            "address": address,
            "city": "深圳市"  # 固定查询范围为深圳市
        }

        # 发送请求
        response = requests.get(self.base_url, params=params)

        # 解析响应
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1" and data["count"] != "0":
                # 提取第一个结果的坐标
                location = data["geocodes"][0]["location"]
                #转换为大地坐标系
                # location_wgs84= gcj02_to_wgs84(lng, lat)
                # print(f"地址: {address}")
                # print(f"坐标: {location}")
                return location
            else:
                print(f"未找到结果: {data.get('info', '未知错误')}")
                return None
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return None


# 使用示例
if __name__ == "__main__":
    api_key = "7a7cd7f85501689421ef31c632b1153c"  # 替换为你的高德 API Key
    geocoding = Geocoding(api_key)
    address = "宝能城首末公交站"
    location = geocoding.geocode(address)
    print(location)