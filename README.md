
---
# <h1 align="center">RoutePlanner<br>面向真实城市路径规划的语言代理评测基准</h1>

<p align="center">
    <img src="image/xitongEng.png" width="90%"> <br>
</p>

RoutePlanner 是一个用于评估语言代理（Language Agents）在真实城市路径规划任务中表现的基准框架，重点关注模型在**工具调用（Tool Use）**与**多约束推理（Multi-Constraint Reasoning）**场景下的综合能力。


---

## 📌 项目概述

RoutePlanner 旨在系统性评估语言代理在真实约束条件下生成完整路径规划的能力。

对于每一个输入查询，模型需要生成**按路径点生成合理路径**，包括以下关键要素：

* 🚗 出行方式
* 🍽️ 途经点
* 🏛️ 换乘时间

同时，生成的规划必须满足多种现实约束：

* **常识约束**：如合理时间、行程连贯性等
* **硬约束**：如起点、终点、预算、时间限制、指定偏好等
* **隐式约束**：如老人等换乘个体需步行少的路径

---

## ⚙️ 环境配置


### 1. 构建OTP（OpenTripPlanner）路径规划平台
构建完整OTP所需要文件有以下组成：
```bash
otp-2.5.0-shaded.jar  OTP jar包
overpass_sz.osm.pbf   深圳市交通路网
subway_gtfs.zip  new_Gtfs.zip 此处交通数据必须为gtfs.zip结尾
```
我们通过处理深圳市的真实交通数据，按照GTFS标准进行构建，并通过GTFS官网进行验证

官网下载[OTP项目](https://github.com/opentripplanner/OpenTripPlanner),选择2.5.0版本

下载[深圳市交通路径路网](此处放路网链接) 

下载[深圳市真实交通数据](此处放路网链接) 

构建路网
```bash
构建路网数据graph.obj
java -Xmx4G -jar otp-2.5.0-shaded.jar --build --save ./你的路网路径
加载路网数据
java -Xmx4G -jar otp-2.5.0-shaded.jar --load ./你的路网路径
```
此时OTP成功加载，输入localhost:8080 即可查询路径


### 2. 创建 Conda 环境并安装依赖

```bash
conda create -n RoutePlanner python=3.9
conda activate RoutePlanner
pip install -r requirements.txt
```


## 🚀 运行方式

### 🧠 两阶段运行方式

在两阶段模式中，语言代理首先进行需求理解，然后基于这些信息调用工具满足用户需求与约束条件的完整规划。

```bash
export OUTPUT_DIR=path/to/your/output/file

# 示例：gpt-3.5-turbo-X, gpt-4-1106-preview, gemini, mistral-7B-32K, mixtral
export MODEL_NAME=MODEL_NAME

export OPENAI_API_KEY=YOUR_OPENAI_KEY


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



---

## ⚠️ 注意事项

本基准旨在提供公平、可复现的评测环境，请严格遵守以下规范：

1. 不得通过反向推断数据集构造规则来优化模型表现
2. 不得在 Prompt 中硬编码与 Benchmark 强相关的信息
3. 不得采用仅针对本基准、缺乏泛化能力的人工策略

---
