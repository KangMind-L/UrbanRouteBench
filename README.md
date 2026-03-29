# <h1 align="center">TripPlannerGPT<br> A Benchmark for Real-World Planning<br> with Language Agents </h1>

![TripPlannerGPT](https://img.shields.io/badge/Task-Planning-blue)
![TripPlannerGPT](https://img.shields.io/badge/Task-Tool_Use-blue)
![TripPlannerGPT](https://img.shields.io/badge/Task-Language_Agents-blue)
![GPT-4](https://img.shields.io/badge/Model-GPT--4-green)
![LLMs](https://img.shields.io/badge/Model-LLMs-green)

<p align="center">
    <img src="images/icon.png" width="10%"> <br>
</p>

TripPlannerGPT is a benchmark repository for evaluating language agents on real-world travel planning tasks with tool use and multi-constraint reasoning.

![Demo Video GIF](images/TravelPlanner.gif)

<p align="center">
[<a href="https://osu-nlp-group.github.io/TravelPlanner/">Website</a>] •
[<a href="http://arxiv.org/abs/2402.01622">Paper</a>] •
[<a href="https://huggingface.co/datasets/osunlp/TravelPlanner">Dataset</a>] •
[<a href="https://huggingface.co/spaces/osunlp/TravelPlannerLeaderboard">Leaderboard</a>] •
[<a href="https://huggingface.co/spaces/osunlp/TravelPlannerEnvironment">Environment</a>]
</p>

## Overview

TripPlannerGPT evaluates how well language agents can generate complete travel itineraries under realistic constraints.

For each query, agents are expected to output a day-by-day plan including:
- transportation
- meals
- attractions
- accommodation

Constraint types include:
- Environment Constraints
- Commonsense Constraints
- Hard Constraints

## Setup Environment

1. Create a conda environment and install dependencies:

```bash
conda create -n tripplannergpt python=3.9
conda activate tripplannergpt
pip install -r requirements.txt
```

2. Download the database and unzip it to the project root (for example: `your/path/TripPlannerGPT`).

## Running

### Two-stage Mode

In two-stage mode, agents first call tools to gather travel information, then generate a plan that satisfies user requirements and commonsense constraints.

```bash
export OUTPUT_DIR=path/to/your/output/file
# MODEL_NAME example: gpt-3.5-turbo-X, gpt-4-1106-preview, gemini, mistral-7B-32K, mixtral
export MODEL_NAME=MODEL_NAME
export OPENAI_API_KEY=YOUR_OPENAI_KEY
# If you do not want to test Google models, set this to "1"
export GOOGLE_API_KEY=YOUR_GOOGLE_KEY
# SET_TYPE in ['validation', 'test']
export SET_TYPE=validation

cd agents
python tool_agents.py --set_type $SET_TYPE --output_dir $OUTPUT_DIR --model_name $MODEL_NAME
```

Outputs are stored in `OUTPUT_DIR/SET_TYPE`.

### Sole-Planning Mode

Sole-planning mode focuses only on planning quality with key information provided, reducing tool-calling overhead.

```bash
export OUTPUT_DIR=path/to/your/output/file
export MODEL_NAME=MODEL_NAME
export OPENAI_API_KEY=YOUR_OPENAI_KEY
export GOOGLE_API_KEY=YOUR_GOOGLE_KEY
export SET_TYPE=validation
# STRATEGY in ['direct','cot','react','reflexion']
export STRATEGY=direct

cd tools/planner
python sole_planning.py --set_type $SET_TYPE --output_dir $OUTPUT_DIR --model_name $MODEL_NAME --strategy $STRATEGY
```

## Postprocess

To parse natural-language plans, this repo converts outputs into JSON format and then combines them for evaluation.

```bash
export OUTPUT_DIR=path/to/your/output/file
export MODEL_NAME=MODEL_NAME
export OPENAI_API_KEY=YOUR_OPENAI_KEY
export SET_TYPE=validation
export STRATEGY=direct
# MODE in ['two-stage','sole-planning']
export MODE=two-stage
export TMP_DIR=path/to/tmp/parsed/plan/file
export SUBMISSION_DIR=path/to/your/evaluation/file

cd postprocess
python parsing.py --set_type $SET_TYPE --output_dir $OUTPUT_DIR --model_name $MODEL_NAME --strategy $STRATEGY --mode $MODE --tmp_dir $TMP_DIR
python element_extraction.py --set_type $SET_TYPE --output_dir $OUTPUT_DIR --model_name $MODEL_NAME --strategy $STRATEGY --mode $MODE --tmp_dir $TMP_DIR
python combination.py --set_type $SET_TYPE --output_dir $OUTPUT_DIR --model_name $MODEL_NAME --strategy $STRATEGY --mode $MODE --submission_file_dir $SUBMISSION_DIR
```

## Evaluation

Use local validation-set evaluation with:

```bash
export SET_TYPE=validation
export EVALUATION_FILE_PATH=your/evaluation/file/path

cd evaluation
python eval.py --set_type $SET_TYPE --evaluation_file_path $EVALUATION_FILE_PATH
```

For test-set evaluation, use the official leaderboard.

## Warnings

This benchmark is intended for fair and reproducible evaluation.

Strictly prohibited:
1. Reverse engineering dataset examples or construction rules for test/validation optimization.
2. Hard-coding benchmark-specific hints into prompts.
3. Any manual interference strategy tailored only to this benchmark with poor generalization.

## Load Datasets

```python
from datasets import load_dataset
# "test" can be replaced by "train" or "validation".
data = load_dataset("osunlp/TravelPlanner", "test")["test"]
```

## Citation

If this project helps your research, please cite:

```bibtex
@inproceedings{xie2024travelplanner,
  title={TravelPlanner: A Benchmark for Real-World Planning with Language Agents},
  author={Xie, Jian and Zhang, Kai and Chen, Jiangjie and Zhu, Tinghui and Lou, Renze and Tian, Yuandong and Xiao, Yanghua and Su, Yu},
  booktitle={Forty-first International Conference on Machine Learning},
  year={2024}
}
```
