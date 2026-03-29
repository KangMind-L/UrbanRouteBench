import json
import os
import shutil

# =========================
# 1 读取 jsonl，找到需要删除的行号
# =========================
jsonl_path = "/home/kangpeng/TripPlannerGPT/output_Result_combination_jsonl_V4/test/args_gpt-5.2_reflect_submission.jsonl"

remove_lines = set()

with open(jsonl_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, start=1):
        data = json.loads(line)

        if "出行计划" in data and data["出行计划"] == []:
            remove_lines.add(i)

print("需要删除的数量:", len(remove_lines))


# =========================
# 2 文件目录
# =========================
input_dir = "/home/kangpeng/TripPlannerGPT/output_Result_V4/test/args/reflect/gpt-5.2"
output_dir = "/home/kangpeng/TripPlannerGPT/output_Result_V5/test/args/reflect/gpt-5.4"

os.makedirs(output_dir, exist_ok=True)


# =========================
# 3 遍历复制
# =========================
copy_count = 0
skip_count = 0

for i in range(1, 1001):  # 根据你的最大编号调整
    file_name = f"generated_plan_{i}.json"
    src_path = os.path.join(input_dir, file_name)

    if not os.path.exists(src_path):
        break

    if i in remove_lines:
        skip_count += 1
        continue

    dst_path = os.path.join(output_dir, file_name)
    shutil.copy(src_path, dst_path)
    copy_count += 1

print("复制数量:", copy_count)
print("跳过数量:", skip_count)