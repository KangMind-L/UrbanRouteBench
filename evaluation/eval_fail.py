import os
import json
import pandas as pd


def calculate_failure_reason_for_model(model_dir, model_name, strategy):

    over_limit = 0
    repeat_three = 0
    invalid_action = 0
    param_error = 0
    total_failed = 0

    for file_name in os.listdir(model_dir):

        if not file_name.startswith("generated_plan_"):
            continue
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(model_dir, file_name)

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                continue

        for item in data:

            result_key = f"{model_name}_{strategy}_results"
            logs_key = f"{model_name}_{strategy}_action_logs"

            if result_key not in item:
                continue

            results_text = item[result_key]
            action_logs = item.get(logs_key, [])

            # 只统计没有出行计划的
            if "出行计划" in results_text:
                continue

            total_failed += 1

            # 1 超过最大步数
            max_step = max([log.get("step", 0) for log in action_logs], default=0)
            if max_step >= 30:
                over_limit += 1
                continue

            # 2 相同动作重复三次
            # if any("同样的动作重复3次" in log.get("state", "") for log in action_logs):
            #     if():
            #         repeat_three += 1
            #     else:
            #         param_error +=1
            #         continue   

                        # 3 非法动作
            if any("invalidAction" in log.get("state", "") for log in action_logs):
                invalid_action += 1
                continue
            # 2️⃣ 相同动作重复三次（严格判断前两个步骤都成功）
            found_repeat = False
            for i in range(len(action_logs)):
                state = action_logs[i].get("state", "")
                if "同样的动作重复3次" in state:
                    if i >= 2:
                        prev_state_1 = action_logs[i-1].get("state", "")
                        prev_state_2 = action_logs[i-2].get("state", "")
                        if prev_state_1 == "Successful" and prev_state_2 == "Successful":
                            repeat_three += 1
                        else:
                            param_error += 1
                    else:
                        param_error += 1
                    found_repeat = True
                    break  # 找到一次就停止循环

            if found_repeat:
                continue  # 跳到下一个 plan




            # 4 参数错误
            # if any(
            #     "early stop due to 3 max retries." in log.get("state", "")
            #     and "invalidAction" not in log.get("state", "")
            #     for log in action_logs
            # ):
            param_error += 1
            continue

    if total_failed == 0:
        return None

    return {
        "模型": model_name,
        "失败样本数": total_failed,
        "超过最大限制(%)": round(over_limit / total_failed * 100, 2),
        "重复三次(%)": round(repeat_three / total_failed * 100, 2),
        "非法动作(%)": round(invalid_action / total_failed * 100, 2),
        "参数错误(%)": round(param_error / total_failed * 100, 2),
    }


def main():

    query_type_list = ["args"]

    model_list = [
        "llama3.1:8b",
        "qwen3-32b",
        "qwen3-max",
        "deepseek-v3.2",
        "gemini-3-flash-preview",
        "gpt-5.2",
    ]

    strategy_list = ["direct"]
    set_type_list = ["test"]

    jsonl_dir = "output_Result_V4"

    all_rows = []

    for set_type in set_type_list:
        for query_type in query_type_list:
            for strategy in strategy_list:
                for model_name in model_list:

                    model_dir = os.path.join(
                        jsonl_dir,
                        set_type,
                        query_type,
                        strategy,
                        model_name,
                    )

                    if not os.path.exists(model_dir):
                        continue

                    stats = calculate_failure_reason_for_model(
                        model_dir, model_name, strategy
                    )

                    if stats:
                        all_rows.append(stats)

    # 转为 DataFrame
    df = pd.DataFrame(all_rows)

    # 保存为 Excel
    save_path = "test-V4/Failure_Reason_Statistics.xlsx"
    df.to_excel(save_path, index=False)

    print("统计完成，已保存到：", save_path)
    print(df)


if __name__ == "__main__":
    main()
