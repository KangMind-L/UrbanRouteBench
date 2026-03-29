好的，下面给你一份**完整、可直接替换 README 的中文版（统一风格 + 已润色 + 适合开源项目/论文仓库）**：

---

# <h1 align="center">TripPlannerGPT<br>面向真实世界规划的语言代理评测基准</h1>

![TripPlannerGPT](https://img.shields.io/badge/任务-规划-blue)
![TripPlannerGPT](https://img.shields.io/badge/任务-工具调用-blue)
![TripPlannerGPT](https://img.shields.io/badge/任务-语言代理-blue)
![GPT-4](https://img.shields.io/badge/模型-GPT--4-green)
![LLMs](https://img.shields.io/badge/模型-大语言模型-green)

<p align="center">
    <img src="images/icon.png" width="10%"> <br>
</p>

TripPlannerGPT 是一个用于评估语言代理（Language Agents）在真实世界旅行规划任务中表现的基准框架，重点关注模型在**工具调用（Tool Use）**与**多约束推理（Multi-Constraint Reasoning）**场景下的综合能力。

![Demo Video GIF](images/TravelPlanner.gif)

<p align="center">
[<a href="https://osu-nlp-group.github.io/TravelPlanner/">项目主页</a>] •
[<a href="http://arxiv.org/abs/2402.01622">论文</a>] •
[<a href="https://huggingface.co/datasets/osunlp/TravelPlanner">数据集</a>] •
[<a href="https://huggingface.co/spaces/osunlp/TravelPlannerLeaderboard">排行榜</a>] •
[<a href="https://huggingface.co/spaces/osunlp/TravelPlannerEnvironment">环境模拟器</a>]
</p>

---

## 📌 项目概述

TripPlannerGPT 旨在系统性评估语言代理在真实约束条件下生成完整旅行计划的能力。

对于每一个输入查询，模型需要生成**按天组织的旅行行程（day-by-day itinerary）**，包括以下关键要素：

* 🚗 交通安排（Transportation）
* 🍽️ 餐饮安排（Meals）
* 🏛️ 景点安排（Attractions）
* 🏨 住宿安排（Accommodation）

同时，生成的规划必须满足多种现实约束：

* **环境约束（Environment Constraints）**：如天气、时间、地理条件等
* **常识约束（Commonsense Constraints）**：如合理作息、行程连贯性等
* **硬约束（Hard Constraints）**：如预算、时间限制、指定偏好等

---

## ⚙️ 环境配置

### 1. 创建 Conda 环境并安装依赖

```bash
conda create -n tripplannergpt python=3.9
conda activate tripplannergpt
pip install -r requirements.txt
```

### 2. 下载数据库

请下载项目所需数据库，并解压至项目根目录，例如：

```
your/path/TripPlannerGPT
```

---

## 🚀 运行方式

### 🧠 两阶段模式（Two-stage Mode）

在两阶段模式中，语言代理首先调用工具获取旅行相关信息，然后基于这些信息生成满足用户需求与约束条件的完整规划。

```bash
export OUTPUT_DIR=path/to/your/output/file

# 示例：gpt-3.5-turbo-X, gpt-4-1106-preview, gemini, mistral-7B-32K, mixtral
export MODEL_NAME=MODEL_NAME

export OPENAI_API_KEY=YOUR_OPENAI_KEY

# 若不测试 Google 模型，可设置为 "1"
export GOOGLE_API_KEY=YOUR_GOOGLE_KEY

# 可选：validation 或 test
export SET_TYPE=validation

cd agents
python tool_agents.py \
  --set_type $SET_TYPE \
  --output_dir $OUTPUT_DIR \
  --model_name $MODEL_NAME
```

输出结果保存在：

```
OUTPUT_DIR/SET_TYPE
```

---

### 🧾 单阶段规划模式（Sole-Planning Mode）

该模式不涉及工具调用，直接基于提供的关键信息生成规划，用于评估模型的纯规划能力。

```bash
export OUTPUT_DIR=path/to/your/output/file
export MODEL_NAME=MODEL_NAME
export OPENAI_API_KEY=YOUR_OPENAI_KEY
export GOOGLE_API_KEY=YOUR_GOOGLE_KEY
export SET_TYPE=validation

# 可选策略：direct / cot / react / reflexion
export STRATEGY=direct

cd tools/planner
python sole_planning.py \
  --set_type $SET_TYPE \
  --output_dir $OUTPUT_DIR \
  --model_name $MODEL_NAME \
  --strategy $STRATEGY
```

---

## 🔄 后处理（Postprocess）

该步骤用于将自然语言生成的旅行规划解析为结构化 JSON，并整合为最终评估文件。

```bash
export OUTPUT_DIR=path/to/your/output/file
export MODEL_NAME=MODEL_NAME
export OPENAI_API_KEY=YOUR_OPENAI_KEY
export SET_TYPE=validation
export STRATEGY=direct

# 模式：two-stage 或 sole-planning
export MODE=two-stage

export TMP_DIR=path/to/tmp/parsed/plan/file
export SUBMISSION_DIR=path/to/your/evaluation/file

cd postprocess

python parsing.py \
  --set_type $SET_TYPE \
  --output_dir $OUTPUT_DIR \
  --model_name $MODEL_NAME \
  --strategy $STRATEGY \
  --mode $MODE \
  --tmp_dir $TMP_DIR

python element_extraction.py \
  --set_type $SET_TYPE \
  --output_dir $OUTPUT_DIR \
  --model_name $MODEL_NAME \
  --strategy $STRATEGY \
  --mode $MODE \
  --tmp_dir $TMP_DIR

python combination.py \
  --set_type $SET_TYPE \
  --output_dir $OUTPUT_DIR \
  --model_name $MODEL_NAME \
  --strategy $STRATEGY \
  --mode $MODE \
  --submission_file_dir $SUBMISSION_DIR
```

---

## 📊 评估（Evaluation）

使用本地验证集进行评估：

```bash
export SET_TYPE=validation
export EVALUATION_FILE_PATH=your/evaluation/file/path

cd evaluation
python eval.py \
  --set_type $SET_TYPE \
  --evaluation_file_path $EVALUATION_FILE_PATH
```

测试集评估请使用官方排行榜。

---

## ⚠️ 注意事项

本基准旨在提供公平、可复现的评测环境，请严格遵守以下规范：

1. 不得通过反向推断数据集构造规则来优化模型表现
2. 不得在 Prompt 中硬编码与 Benchmark 强相关的信息
3. 不得采用仅针对本基准、缺乏泛化能力的人工策略

---

## 📦 数据集加载

```python
from datasets import load_dataset

# "test" 可替换为 "train" 或 "validation"
data = load_dataset("osunlp/TravelPlanner", "test")["test"]
```

---

## 📖 引用

如果本项目对你的研究有所帮助，请引用：

```bibtex
@inproceedings{xie2024travelplanner,
  title={TravelPlanner: A Benchmark for Real-World Planning with Language Agents},
  author={Xie, Jian and Zhang, Kai and Chen, Jiangjie and Zhu, Tinghui and Lou, Renze and Tian, Yuandong and Xiao, Yanghua and Su, Yu},
  booktitle={Forty-first International Conference on Machine Learning},
  year={2024}
}
```

---

如果你接下来要**投稿论文 / 做 benchmark 对比 / 写实验部分**，我也可以帮你把这份 README 再压缩成一段**论文中的“Dataset & Benchmark”标准描述**（那种 reviewer 很喜欢的写法）。
