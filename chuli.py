import os
import shutil

SRC_ROOT = "output_Result_V5"
DST_ROOT = "output_Result_V5"

model_names = [
    # "deepseek-v3.2",
    # 'qwen3-max',
    # "qwen3-coder-480b-a35b-instruct"
    # "llama3:7b"
    # "llama3.1:8b",
    "gpt-5.4",
    # "glm-4.6",
    # "llama3:70b",
    # "qwen3-32b",
    # "gemini-2.5-flash",
    # "gemini-3-flash-preview"

    ]
query_type_list=[
    "query",
    # "query1",
    # "query2",
    "args"
    ]
strategy_list = [
    # "direct",
    # "cot",
    # "react",
    "reflect",
    # "not-tool-direct"


    ]
set_type_list =  [
    # "train",
    # "validation",
    "test",
]

def process_directory(src_dir, dst_dir):
    """
    处理一个 strategy 目录：
    - 仅当存在 generated_plan_*.json 时才创建目标目录
    - 替换文件内容中的“途径” -> “途经”
    """
    json_files = [
        f for f in os.listdir(src_dir)
        if f.startswith("generated_plan_") and f.endswith(".json")
    ]

    if not json_files:
        return  # 没有目标文件，不创建目录

    os.makedirs(dst_dir, exist_ok=True)

    for filename in json_files:
        src_path = os.path.join(src_dir, filename)
        dst_path = os.path.join(dst_dir, filename)

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace( "gpt-5.2","gpt-5.4")

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    for set_type in set_type_list:                          
        for query_type in query_type_list:
            for strategy in strategy_list:

                for model in model_names:

                    src_dir = os.path.join(
                        SRC_ROOT, set_type,query_type, strategy, model
                    )
                    dst_dir = os.path.join(
                        DST_ROOT ,set_type,query_type, strategy, model
                    )

                    if not os.path.isdir(src_dir):
                        continue

                    process_directory(src_dir, dst_dir)
import os

# SRC_DIR = "output_V3"     # 原 txt 目录
# DST_DIR = "output_V4"    # 新目录（自动创建）

# os.makedirs(DST_DIR, exist_ok=True)

# def main1():
#     for filename in os.listdir(SRC_DIR):
#         if not filename.endswith(".txt"):
#             continue

#         src_path = os.path.join(SRC_DIR, filename)
#         dst_path = os.path.join(DST_DIR, filename)

#         with open(src_path, "r", encoding="utf-8") as f:
#             content = f.read()

#         # 替换
#         content = content.replace("途径", "途经")

#         with open(dst_path, "w", encoding="utf-8") as f:
#             f.write(content)

#         print(f"[OK] {filename}")
# import os

# SRC_DIR = "test-V3"     # 原 CSV 目录
# DST_DIR = "test-V4"    # 新目录

# os.makedirs(DST_DIR, exist_ok=True)

# def main2():
#     for filename in os.listdir(SRC_DIR):
#         if not filename.endswith(".csv"):
#             continue

#         src_path = os.path.join(SRC_DIR, filename)
#         dst_path = os.path.join(DST_DIR, filename)

#         with open(src_path, "r", encoding="utf-8") as f:
#             content = f.read()

#         # 替换
#         new_content = content.replace("途径", "途经")

#         with open(dst_path, "w", encoding="utf-8") as f:
#             f.write(new_content)

#         print(f"[OK] {filename}")
# SRC_PY_FILE = "agents/prompts.py"     # 原 .py 文件
# DST_PY_FILE = "agents/prompts1.py"    # 新 .py 文件

# def main3():
#     with open(SRC_PY_FILE, "r", encoding="utf-8") as f:
#         content = f.read()

#     new_content = content.replace("途径", "途经")

#     with open(DST_PY_FILE, "w", encoding="utf-8") as f:
#         f.write(new_content)

#     print(f"[OK] 已生成: {DST_PY_FILE}")

# PY_FILE = "agents/prompts1.py"

# def main4():
#     with open(PY_FILE, "r", encoding="utf-8") as f:
#         content = f.read()

#     new_content = content.replace("途经", "途径")

#     if new_content != content:
#         with open(PY_FILE, "w", encoding="utf-8") as f:
#             f.write(new_content)
#         print("[OK] 已在源文件中完成替换：途径 → 途经")
#     else:
#         print("[INFO] 文件中未发现“途径”，无需修改")


# import os

# ROOT_DIR = "/home/kangpeng/TripPlannerGPT"
# SELF_FILE = os.path.abspath(__file__)

# def replace_in_py_files(root_dir: str):
#     modified_files = 0

#     for root, _, files in os.walk(root_dir):
#         for file in files:
#             if not file.endswith(".py"):
#                 continue

#             file_path = os.path.abspath(os.path.join(root, file))

#             # ⭐ 跳过当前执行的脚本
#             if file_path == SELF_FILE:
#                 continue

#             with open(file_path, "r", encoding="utf-8") as f:
#                 content = f.read()

#             if "途径" not in content:
#                 continue

#             new_content = content.replace("途径", "途经")

#             with open(file_path, "w", encoding="utf-8") as f:
#                 f.write(new_content)

#             modified_files += 1
#             print(f"[MODIFIED] {file_path}")

#     print(f"\n完成：共修改 {modified_files} 个 .py 文件")

if __name__ == "__main__":
    # replace_in_py_files(ROOT_DIR)

    main()


