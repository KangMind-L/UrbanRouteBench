import pandas as pd
from typing import Optional
import os
import sys
# PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
# PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)
class Wgs84:
    def __init__(self, path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # tools/wgs84/apis.py → tools/wgs84 → tools → TripPlannerGPT
        project_root = os.path.abspath(os.path.join(base_dir, "../../"))

        if path is None:
            path = os.path.join(
                project_root,
                "database/data/point_excel.csv"
            )

        """初始化时加载CSV坐标数据"""
        self.path = path
        try:
            # 读取CSV文件，确保包含名称、纬度、经度三列
            self.data = pd.read_csv(self.path, usecols=['名称', '纬度', '经度']).dropna()
            # 将名称列设为索引以便快速查找
            self.coord_dict = self.data.set_index('名称').to_dict('index')
            print(f"坐标转换工具已加载！共加载 {len(self.coord_dict)} 个坐标点")
        except Exception as e:
            raise ValueError(f"初始化失败，请检查CSV文件格式: {e}")

    def run(self, name: str) -> Optional[str]:
        """根据名称查找坐标"""
        name = name.strip().strip("'").strip('"')
        if name in self.coord_dict:
            point = self.coord_dict[name]
            return f"{name}::{point['纬度']},{point['经度']}"
        return ""

# 使用示例
if __name__ == "__main__":
    # 创建实例（会自动加载数据）
    wgs84 = Wgs84()  
    
    # 测试查询
    print(wgs84.run("多家福商城"))  # 输出: 高新奇南门::22.57697992,113.9208391
    print(wgs84.run("新村后门"))   # 输出: None
    print(wgs84.run("南山天虹商场")) 