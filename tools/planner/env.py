
from datetime import datetime, timedelta

bike_keywords = {
    # 英文 / 代码类
    "BICYCLE", "BIKE", "BICYCLE_RENT", "BIKE_RENT", "SHARED_BIKE",

    # 中文常见
    "单车", "骑行", "自行车", "骑车", "骑单车",
    "共享单车", "公共自行车", "扫码单车",

    # 偏口语 / 变体
    "骑自行车", "骑共享单车", "骑小蓝车", "骑摩拜", "骑哈啰",
}

# ---------- 开车 / 自驾 ----------
car_keywords = {
    # 英文 / 代码类
    "CAR", "DRIVING", "DRIVE", "SELF_DRIVE",

    # 中文常见
    "开车", "自驾", "驾车", "自家车", "私家车",

    # 偏口语 / 变体
    "自己开车", "开私家车", "开小车", "开轿车",
}

# ---------- 打车 / 网约车 ----------
taxi_keywords = {
    # 英文 / 代码类
    "CAR_PICKUP", "TAXI", "RIDE_HAILING", "RIDE_HAIL", "CAB",

    # 中文常见
    "打车", "出租车", "网约车", "的士",

    # 平台类
    "滴滴", "高德打车", "曹操出行", "首汽约车", "神州专车",

    # 偏口语 / 变体
    "叫车", "叫出租车", "叫网约车", "打的",
}

# ---------- 公交 / 地铁 / 轨道交通 ----------
transit_keywords = {
    # 英文 / 代码类
    "SUBWAY", "METRO", "BUS", "TRAM", "RAIL", "LIGHT_RAIL", "COMMUTER_RAIL",

    # 中文常见
    "公交", "地铁", "轨道交通", "有轨电车", "城轨", "轻轨", "市域铁路",

    # 具体说法
    "公交车", "巴士", "公共交通", "公共运输",

    # 偏口语 / 变体
    "坐公交", "坐地铁", "搭地铁", "乘地铁", "乘公交",
}

# ---------- 步行 ----------
walk_keywords = {
    # 英文 / 代码类
    "WALK", "WALKING", "FOOT",

    # 中文常见
    "步行", "走路", "步走",

    # 偏口语 / 变体
    "走过去", "步行前往", "步行到达",
}
class ReactEnv:
    def __init__(self):
        print("ReAct规划初始化")
        

    
    def LogicalJudgment(self, tested_data):


        unit = tested_data
        
        returned_info = []

        if '行程' not in unit or not unit['行程']:
            returned_info.append("缺少行程信息")
            return returned_info

        trip_start = unit['行程'].get('起点')
        trip_end = unit['行程'].get('终点')

        # 收集步骤，按步骤顺序排序
        steps = sorted(
            [(k, v) for k, v in unit.items() if k != '行程'],
            key=lambda x: int(''.join(filter(str.isdigit, x[0])))  # 步骤1 -> 1
        )

        if not steps:
            returned_info.append("没有步骤信息")
            return returned_info

        # 检查首尾步骤与行程起止点是否一致
        first_step = steps[0][1]
        last_step = steps[-1][1]

        if first_step.get("起点") != trip_start:
            returned_info.append(f"步骤1起点【{first_step.get('起点')}】与行程起点【{trip_start}】不一致")

        if last_step.get("终点") != trip_end:
            returned_info.append(f"最后一步终点【{last_step.get('终点')}】与行程终点【{trip_end}】不一致")

        # 检查步骤衔接和时间顺序
        # from datetime import datetime

        prev_step = None
        travel_modes = set()
        cross_day_count = 0
        for idx, (step_name, step_data) in enumerate(steps):
            # 步骤衔接
            if prev_step:
                # 检查起终点一致性
                if prev_step.get("终点") != step_data.get("起点"):
                    returned_info.append(f"{step_name}起点【{step_data.get('起点')}】与前一步终点【{prev_step.get('终点')}】不一致")

            # 时间顺序和跨天检查
            try:
                curr_start = datetime.strptime(step_data.get("开始时间"), "%H:%M:%S")
                curr_end = datetime.strptime(step_data.get("结束时间"), "%H:%M:%S")

                # 当前步骤自己跨天
                step_cross_day = curr_start > curr_end

                # 与前一步跨天
                prev_cross_day = False
                if prev_step:
                    prev_end = datetime.strptime(prev_step.get("结束时间"), "%H:%M:%S")
                    if curr_start < prev_end:
                        prev_cross_day = True

                # 总体跨天判断
                if step_cross_day or prev_cross_day:
                    cross_day_count += 1
                    if cross_day_count > 1:
                        returned_info.append(
                            f"{step_name}发生多次跨天: 当前开始时间【{step_data.get('开始时间')}】当前结束时间【{step_data.get('结束时间')}】"
                            f"{' 或前一步结束时间【' + prev_step.get('结束时间') + '】' if prev_step else ''}"
                        )

            except Exception as e:
                returned_info.append(f"{step_name}时间格式错误: {e}")

            prev_step = step_data



            # 收集出行方式
            mode = step_data.get("出行方式")
            if mode:
                travel_modes.add(mode)

            prev_step = step_data

        # 检查出行方式共存规则
        modes_set = travel_modes

        # 规则 1：单车 + 步行 ❌
        if bike_keywords & modes_set and walk_keywords & modes_set:
            returned_info.append(
                f"出行方式冲突：单车和步行不能共存 {modes_set}"
            )

        # 规则 2：单车 + 打车/开车 ❌
        if bike_keywords & modes_set and (taxi_keywords & modes_set or car_keywords &  modes_set):
            returned_info.append(
                f"出行方式冲突：单车不能与打车或开车共存 {modes_set}"
            )

        # 规则 3：公交/地铁 + 打车/开车 ❌
        if (transit_keywords & modes_set) and (taxi_keywords & modes_set or car_keywords & modes_set):
            returned_info.append(
                f"出行方式冲突：公交或地铁不能与打车或开车共存 {modes_set}"
            )


        if len(returned_info) == 0:
            return "这一段逻辑没有问题，可以采用"
        else:
            message = "很抱歉，由于以下原因，您本次的计划逻辑不正确:"
            for idx, info in enumerate(returned_info):
                message += str(idx + 1) + ". " + info + " " + '\t'
            return message

        # return returned_info



        # # total_cost = 0
        # unit = tested_data
        # # people_number = tested_data['people_number']
        # returned_info = []

        
        # if '行程' in unit and unit['行程']:
        #     raw_start =  unit['行程']["起点"]
        #     raw_start =  unit['行程']["终点"]
        
        


        # if 'transportati on' in unit and unit['transportation'] and  unit['transportation'] != '-':
        #     value = unit['transportation']
        #     org_city, dest_city = extract_from_to(value)
        #     if org_city == None or dest_city == None:
        #         org_city, dest_city = extract_from_to(unit['current_city'])
        #     if 'flight number' in value.lower():
        #             try:
        #                 res = self.flight.data[self.flight.data['Flight Number'] == value.split('Flight Number: ')[1].split(',')[0]]
        #                 if len(res) > 0:
        #                     total_cost += res['Price'].values[0] * people_number
        #                 else:
        #                     returned_info.append('The filght information is not valid')
        #             except:
        #                 returned_info.append('The filght information is not valid')

        #     elif 'self-driving' in value.lower() or 'taxi' in value.lower():
        #         try:
        #             if 'self-driving' in value.lower():
        #                 # print(org_city,dest_city)
        #                 cost = self.googleDistanceMatrix.run_for_evaluation(org_city,dest_city,'self-driving')['cost']
        #                 if cost == None:
        #                     returned_info.append('The transporation information is not valid, please check.')
        #                 else:
        #                     total_cost += cost * math.ceil(people_number * 1.0 / 5)
        #             else:
        #                 cost = self.googleDistanceMatrix.run_for_evaluation(org_city,dest_city,'taxi')['cost']
        #                 if cost == None:
        #                     returned_info.append('The transporation information is not valid, please check.')
        #                 else:
        #                     total_cost += cost * math.ceil(people_number * 1.0 / 4)
        #         except:
        #             returned_info.append('The transporation information is not valid, please check. You have to make sure there are two cities (from A to B) in your transportation plan.')

        # if 'breakfast' in unit and unit['breakfast'] and unit['breakfast'] != '-':
        #     name, city = get_valid_name_city(unit['breakfast'])
        #     if name != '-' and city != '-':
        #         res = self.restaurants.data[(self.restaurants.data['Name'] == name) & (self.restaurants.data['City'] == city)]
        #         if len(res) > 0:
        #             total_cost += res['Average Cost'].values[0] * people_number
        #         else:
        #             returned_info.append('The breakfase information is not valid, please check.')

        # if 'lunch' in unit and  unit['lunch'] and unit['lunch'] != '-':
        #     name, city = get_valid_name_city(unit['lunch'])
        #     if name != '-' and city != '-':
        #         res = self.restaurants.data[(self.restaurants.data['Name'] == name) & (self.restaurants.data['City'] == city)]
        #         if len(res) > 0:
        #             total_cost += res['Average Cost'].values[0] * people_number
        #         else:
        #             returned_info.append('The lunch information is not valid, please check.')

        # if 'dinner' in unit and unit['dinner'] and unit['dinner'] != '-':
        #     name, city = get_valid_name_city(unit['dinner'])
        #     if name != '-' and city != '-':
        #         res = self.restaurants.data[(self.restaurants.data['Name'] == name) & (self.restaurants.data['City'] == city)]
        #         if len(res) > 0:
        #             total_cost += res['Average Cost'].values[0] * people_number
        #         else:
        #             returned_info.append('The dinner information is not valid, please check.')

        # if 'accommodation' in unit and unit['accommodation'] and unit['accommodation'] != '-':
        #     name, city = get_valid_name_city(unit['accommodation'])
        #     if name != '-' and city != '-':
        #         res = self.accommodation.data[(self.accommodation.data['NAME'] == name) & (self.accommodation.data['city'] == city)]
        #         if len(res) > 0:
        #             total_cost += res['price'].values[0] * math.ceil(people_number * 1.0 / res['maximum occupancy'].values[0])
        #         else:
        #             returned_info.append('The accommodation information is not valid, please check.')
        
        # if len(returned_info) == 0:
        #     return "The cost of your plan is " + str(total_cost) + " dollars."
        # else:
        #     message = "Sorry, the cost of your plan is not available because of the following reasons:"
        #     for idx, info in enumerate(returned_info):
        #         message += str(idx + 1) + ". " + info + " " + '\t'
        #     return message
   


    from datetime import datetime

    from datetime import datetime, timedelta

    def PlanSummary(self, step_results, tested_data):
        """
        step_results: list[dict]  多段行程的 LogicalJudgment 输入
        tested_data: dict         LLM 输出的 PlanSummary JSON
        """

        returned_info = []

        # ----------- 工具函数 -----------
        def parse_time(t):
            return datetime.strptime(t, "%H:%M:%S")

        def parse_distance(d):
            # "1234.56米"
            try:
                return float(d.replace("米", ""))
            except Exception:
                return 0.0

        def parse_duration_to_seconds(time_str):
            # 例如 "163分钟52秒"
            if not time_str:
                return 0
            minutes = 0
            seconds = 0
            if "分钟" in time_str:
                parts = time_str.split("分钟")
                minutes = int(parts[0])
                time_str = parts[1]
            if "秒" in time_str:
                seconds = int(time_str.replace("秒", ""))
            return minutes * 60 + seconds

        # ----------- 汇总变量 -----------
        all_steps = []
        travel_modes = []
        total_distance = 0.0
        total_walk = 0.0
        total_bike = 0.0
        if len(step_results) >= 2:
            first = step_results[0]
            second = step_results[1]

            # 如果第一段终点 != 第二段起点，交换顺序
            if first["行程"]["终点"] != second["行程"]["起点"]:
                step_results[0], step_results[1] = second, first

        # ----------- 展平所有步骤 -----------
        for segment in step_results:
            steps = sorted(
                [(k, v) for k, v in segment.items() if k.startswith("步骤")],
                key=lambda x: int(''.join(filter(str.isdigit, x[0])))
            )
            for _, step in steps:
                all_steps.append(step)

                dist = parse_distance(step.get("距离", "0米"))
                total_distance += dist

                mode = step.get("出行方式")
                travel_modes.append(mode)

                if mode == "步行":
                    total_walk += dist
                elif mode == "单车":
                    total_bike += dist

        if not all_steps:
            return "无法计算：没有任何步骤信息"

        # ----------- 时间计算 -----------
        real_start_time = parse_time(all_steps[0]["开始时间"])
        real_end_time = parse_time(all_steps[-1]["结束时间"])

        # 跨天处理
        if real_end_time < real_start_time:
            real_end_time += timedelta(days=1)

        real_total_seconds = int((real_end_time - real_start_time).total_seconds())
        real_total_minutes = real_total_seconds // 60
        real_total_remain_seconds = real_total_seconds % 60
        real_total_time_str = f"{real_total_minutes}分钟{real_total_remain_seconds}秒"

        # ----------- 换乘次数 -----------
        motorized_modes = [m for m in travel_modes if m in ["公交", "地铁", "打车", "开车"]]
        real_transfer_count = max(len(motorized_modes) - 1, 0)

        # ----------- 开始校验 summary -----------

        # 出发时间
        if tested_data.get("出发时间") != all_steps[0]["开始时间"]:
            returned_info.append(
                f"出发时间不一致：计算为 {all_steps[0]['开始时间']}，但给出 {tested_data.get('出发时间')}"
            )

        # 到达时间
        if tested_data.get("到达时间") != all_steps[-1]["结束时间"]:
            returned_info.append(
                f"到达时间不一致：计算为 {all_steps[-1]['结束时间']}，但给出 {tested_data.get('到达时间')}"
            )

        # 总出行时间（允许 10 分钟误差）
        tested_total_time_str = tested_data.get("总出行时间")
        tested_total_seconds = parse_duration_to_seconds(tested_total_time_str)

        if abs(tested_total_seconds - real_total_seconds) > 300:
            returned_info.append(
                f"总出行时间不一致：计算为 {real_total_time_str}，但给出 {tested_total_time_str}"
            )

        # 换乘次数
        if tested_data.get("换乘次数") != real_transfer_count:
            returned_info.append(
                f"换乘次数不一致：计算为 {real_transfer_count}，但给出 {tested_data.get('换乘次数')},如果存在两段行程,换乘次数等于每一段的换乘次数之和再+1,这一次换乘是因为已经下车了,需要过一段时间之后上车,所以多一次换乘。"
            )

        # ----------- 距离校验规则 -----------

        # 总步行距离
        tested_walk = parse_distance(tested_data.get("总步行距离", "0米"))
        if tested_walk > 0:
            if abs(tested_walk - total_walk) > 10:
                returned_info.append(
                    f"总步行距离不一致：计算为 {total_walk:.2f}米，给出 {tested_walk:.2f}米"
                )
        else:
            if total_walk > 1:
                returned_info.append(
                    f"总步行距离应为 0，但计算为 {total_walk:.2f}米"
                )

        # 骑行总距离
        tested_bike = parse_distance(tested_data.get("骑行总距离", "0米"))
        if tested_bike > 0:
            if abs(tested_bike - total_bike) > 10:
                returned_info.append(
                    f"骑行总距离不一致：计算为 {total_bike:.2f}米，给出 {tested_bike:.2f}米"
                )
        else:
            if total_bike > 1:
                returned_info.append(
                    f"骑行总距离应为 0，但计算为 {total_bike:.2f}米"
                )

        # 总距离
        tested_total_dist = parse_distance(tested_data.get("总距离", "0米"))
        if tested_total_dist > 0:
            if abs(tested_total_dist - total_distance) > 10:
                returned_info.append(
                    f"总距离不一致：计算为 {total_distance:.2f}米，给出 {tested_total_dist:.2f}米"
                )
        else:
            if total_distance > 1:
                returned_info.append(
                    f"总距离应为 0，但计算为 {total_distance:.2f}米"
                )

        # ----------- 输出结果 -----------
        if  len(returned_info) ==0 :
            return "对计划的总结与子计划完全一致"
        else:
            message = "对计划的总结与子计划不一致，原因如下："
            for idx, info in enumerate(returned_info, 1):
                message += str(idx + 1) + ". " + info + " " + '\t'
                # message += f"{i}. {info}\n"
            return message




class ReactReflectEnv(ReactEnv):
    def __init__(self):
        super().__init__()
        self.is_terminated = False
        self.max_retry_step = 3
        self.retry_step = 0

    def reset(self):
        self.is_terminated = False
        self.retry_step = 0

    def LogicalJudgment(self, tested_data):


        unit = tested_data
        
        returned_info = []

        if '行程' not in unit or not unit['行程']:
            returned_info.append("缺少行程信息")
            return returned_info

        trip_start = unit['行程'].get('起点')
        trip_end = unit['行程'].get('终点')

        # 收集步骤，按步骤顺序排序
        steps = sorted(
            [(k, v) for k, v in unit.items() if k != '行程'],
            key=lambda x: int(''.join(filter(str.isdigit, x[0])))  # 步骤1 -> 1
        )

        if not steps:
            returned_info.append("没有步骤信息")
            return returned_info

        # 检查首尾步骤与行程起止点是否一致
        first_step = steps[0][1]
        last_step = steps[-1][1]

        if first_step.get("起点") != trip_start:
            returned_info.append(f"步骤1起点【{first_step.get('起点')}】与行程起点【{trip_start}】不一致")

        if last_step.get("终点") != trip_end:
            returned_info.append(f"最后一步终点【{last_step.get('终点')}】与行程终点【{trip_end}】不一致")

        # 检查步骤衔接和时间顺序
        # from datetime import datetime

        prev_step = None
        travel_modes = set()
        cross_day_count = 0
        for idx, (step_name, step_data) in enumerate(steps):
            # 步骤衔接
            if prev_step:
                # 检查起终点一致性
                if prev_step.get("终点") != step_data.get("起点"):
                    returned_info.append(f"{step_name}起点【{step_data.get('起点')}】与前一步终点【{prev_step.get('终点')}】不一致")

            # 时间顺序和跨天检查
            try:
                curr_start = datetime.strptime(step_data.get("开始时间"), "%H:%M:%S")
                curr_end = datetime.strptime(step_data.get("结束时间"), "%H:%M:%S")

                # 当前步骤自己跨天
                step_cross_day = curr_start > curr_end

                # 与前一步跨天
                prev_cross_day = False
                if prev_step:
                    prev_end = datetime.strptime(prev_step.get("结束时间"), "%H:%M:%S")
                    if curr_start < prev_end:
                        prev_cross_day = True

                # 总体跨天判断
                if step_cross_day or prev_cross_day:
                    cross_day_count += 1
                    if cross_day_count > 1:
                        returned_info.append(
                            f"{step_name}发生多次跨天: 当前开始时间【{step_data.get('开始时间')}】当前结束时间【{step_data.get('结束时间')}】"
                            f"{' 或前一步结束时间【' + prev_step.get('结束时间') + '】' if prev_step else ''}"
                        )

            except Exception as e:
                returned_info.append(f"{step_name}时间格式错误: {e}")

            prev_step = step_data



            # 收集出行方式
            mode = step_data.get("出行方式")
            if mode:
                travel_modes.add(mode)

            prev_step = step_data

        # 检查出行方式共存规则
        modes_set = travel_modes

        # 规则 1：单车 + 步行 ❌
        if "单车" in modes_set and "步行" in modes_set:
            returned_info.append(
                f"出行方式冲突：单车和步行不能共存 {modes_set}"
            )

        # 规则 2：单车 + 打车/开车 ❌
        if "单车" in modes_set and ("打车" in modes_set or "开车" in modes_set):
            returned_info.append(
                f"出行方式冲突：单车不能与打车或开车共存 {modes_set}"
            )

        # 规则 3：公交/地铁 + 打车/开车 ❌
        if ("公交" in modes_set or "地铁" in modes_set) and ("打车" in modes_set or "开车" in modes_set):
            returned_info.append(
                f"出行方式冲突：公交或地铁不能与打车或开车共存 {modes_set}"
            )


        if len(returned_info) == 0:
            self.retry_step = 0
            self.is_terminated = False
            return "这一段逻辑没有问题，可以采用"
        else:
            message = "很抱歉，由于以下原因，您本次的计划逻辑不正确:"
            for idx, info in enumerate(returned_info):
                message += str(idx + 1) + ". " + info + " " + '\t'
            self.retry_step += 1
            if self.retry_step >= self.max_retry_step:
                self.is_terminated = True
            return message

    from datetime import datetime

    from datetime import datetime, timedelta

    def PlanSummary(self, step_results, tested_data):
        """
        step_results: list[dict]  多段行程的 LogicalJudgment 输入
        tested_data: dict         LLM 输出的 PlanSummary JSON
        """

        returned_info = []

        # ----------- 工具函数 -----------
        def parse_time(t):
            return datetime.strptime(t, "%H:%M:%S")

        def parse_distance(d):
            # "1234.56米"
            try:
                return float(d.replace("米", ""))
            except Exception:
                return 0.0

        def parse_duration_to_seconds(time_str):
            # 例如 "163分钟52秒"
            if not time_str:
                return 0
            minutes = 0
            seconds = 0
            if "分钟" in time_str:
                parts = time_str.split("分钟")
                minutes = int(parts[0])
                time_str = parts[1]
            if "秒" in time_str:
                seconds = int(time_str.replace("秒", ""))
            return minutes * 60 + seconds

        # ----------- 汇总变量 -----------
        all_steps = []
        travel_modes = []
        total_distance = 0.0
        total_walk = 0.0
        total_bike = 0.0
        if len(step_results) >= 2:
            first = step_results[0]
            second = step_results[1]

            # 如果第一段终点 != 第二段起点，交换顺序
            if first["行程"]["终点"] != second["行程"]["起点"]:
                step_results[0], step_results[1] = second, first

        # ----------- 展平所有步骤 -----------
        for segment in step_results:
            steps = sorted(
                [(k, v) for k, v in segment.items() if k.startswith("步骤")],
                key=lambda x: int(''.join(filter(str.isdigit, x[0])))
            )
            for _, step in steps:
                all_steps.append(step)

                dist = parse_distance(step.get("距离", "0米"))
                total_distance += dist

                mode = step.get("出行方式")
                travel_modes.append(mode)

                if mode in "步行":
                    total_walk += dist
                elif mode == "单车":
                    total_bike += dist

        if not all_steps:
            return "无法计算：没有任何步骤信息"

        # ----------- 时间计算 -----------
        real_start_time = parse_time(all_steps[0]["开始时间"])
        real_end_time = parse_time(all_steps[-1]["结束时间"])

        # 跨天处理
        if real_end_time < real_start_time:
            real_end_time += timedelta(days=1)

        real_total_seconds = int((real_end_time - real_start_time).total_seconds())
        real_total_minutes = real_total_seconds // 60
        real_total_remain_seconds = real_total_seconds % 60
        real_total_time_str = f"{real_total_minutes}分钟{real_total_remain_seconds}秒"

        # ----------- 换乘次数 -----------
        motorized_modes = [m for m in travel_modes if m in ["公交", "地铁", "打车", "开车"]]
        real_transfer_count = max(len(motorized_modes) - 1, 0)

        # ----------- 开始校验 summary -----------

        # 出发时间
        if tested_data.get("出发时间") != all_steps[0]["开始时间"]:
            returned_info.append(
                f"出发时间不一致：计算为 {all_steps[0]['开始时间']}，但给出 {tested_data.get('出发时间')}"
            )

        # 到达时间
        if tested_data.get("到达时间") != all_steps[-1]["结束时间"]:
            returned_info.append(
                f"到达时间不一致：计算为 {all_steps[-1]['结束时间']}，但给出 {tested_data.get('到达时间')}"
            )

        # 总出行时间（允许 10 分钟误差）
        tested_total_time_str = tested_data.get("总出行时间")
        tested_total_seconds = parse_duration_to_seconds(tested_total_time_str)

        if abs(tested_total_seconds - real_total_seconds) > 600:
            returned_info.append(
                f"总出行时间不一致：计算为 {real_total_time_str}，但给出 {tested_total_time_str}"
            )

        # 换乘次数
        if tested_data.get("换乘次数") != real_transfer_count:
            returned_info.append(
                f"换乘次数不一致：计算为 {real_transfer_count}，但给出 {tested_data.get('换乘次数')},如果存在两段行程,换乘次数等于每一段的换乘次数之和再+1,这一次换乘是因为已经下车了,需要过一段时间之后上车,所以多一次换乘。"
            )

        # ----------- 距离校验规则 -----------

        # 总步行距离
        tested_walk = parse_distance(tested_data.get("总步行距离", "0米"))
        if tested_walk > 0:
            if abs(tested_walk - total_walk) > 10:
                returned_info.append(
                    f"总步行距离不一致：计算为 {total_walk:.2f}米，给出 {tested_walk:.2f}米"
                )
        else:
            if total_walk > 1:
                returned_info.append(
                    f"总步行距离应为 0，但计算为 {total_walk:.2f}米"
                )

        # 骑行总距离
        tested_bike = parse_distance(tested_data.get("骑行总距离", "0米"))
        if tested_bike > 0:
            if abs(tested_bike - total_bike) > 10:
                returned_info.append(
                    f"骑行总距离不一致：计算为 {total_bike:.2f}米，给出 {tested_bike:.2f}米"
                )
        else:
            if total_bike > 1:
                returned_info.append(
                    f"骑行总距离应为 0，但计算为 {total_bike:.2f}米"
                )

        # 总距离
        tested_total_dist = parse_distance(tested_data.get("总距离", "0米"))
        if tested_total_dist > 0:
            if abs(tested_total_dist - total_distance) > 10:
                returned_info.append(
                    f"总距离不一致：计算为 {total_distance:.2f}米，给出 {tested_total_dist:.2f}米"
                )
        else:
            if total_distance > 1:
                returned_info.append(
                    f"总距离应为 0，但计算为 {total_distance:.2f}米"
                )

        # ----------- 输出结果 -----------
        if len(returned_info) == 0:
            self.retry_step = 0
            self.is_terminated = False
            return "对计划的总结与子计划完全一致"
        else:
            message = "对计划的总结与子计划不一致，原因如下："
            for idx, info in enumerate(returned_info, 1):
                message += str(idx + 1) + ". " + info + " " + '\t'
                # message += f"{i}. {info}\n"
            self.retry_step += 1
            if self.retry_step >= self.max_retry_step:
                self.is_terminated = True
            return message


