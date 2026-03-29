

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coordTransform_utils import gcj02_to_wgs84

from Src.Address2Point import Geocoding

def localtionGetWgs84(address):
    g = Geocoding('AP7a7cd7f85501689421ef31c632b1153cI_KEY')  # 这里填写你的高德Api_Key
    location=g.geocode(address)
    print(location)
    lng, lat = map(float, location.split(","))
    # 调用 gcj02_to_wgs84 函数
    wgs84_lng, wgs84_lat = gcj02_to_wgs84(lng, lat)
    # 将结果转换为字符串，格式为 "经度,纬度"
    wgs84_str = f"{wgs84_lng},{wgs84_lat}"
    print(wgs84_str)
    return wgs84_str

localtionGetWgs84("中科院深圳先进院")
