import argparse
import os
from datasets import load_dataset
from tqdm import tqdm
import json
import pandas as pd

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_type", type=str, default="query")
    parser.add_argument("--model_name", type=str, default="gpt-5")
    parser.add_argument("--mode", type=str, default="ReAct")
    parser.add_argument("--strategy", type=str, default="direct")
    parser.add_argument("--output_dir", type=str, default="../")
    parser.add_argument("--tmp_dir", type=str, default="../")

    args = parser.parse_args()

    if args.mode == 'two-stage':
        suffix = ''
    elif args.mode == 'sole-planning':
        suffix = f'_{args.strategy}'

    save_dir = f"{args.output_dir}{args.set_type}/"
    os.makedirs(save_dir, exist_ok=True)
    results = open(f'{args.tmp_dir}{args.set_type}_{args.model_name}_{args.mode}.txt','r').read().strip().split('\n')
    
    # if args.set_type == 'train':
    #     query_data_list  = load_dataset('osunlp/TravelPlanner','train')['train']
    # elif args.set_type == 'validation':
    # query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
    query_data_list = pd.read_csv('../8-22/test_llm.csv')
    # elif args.set_type == 'test':
    #     query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']

    idx_number_list = [i for i in range(1,len(query_data_list)+1)]
    for idx in tqdm(idx_number_list[:]):
    # for idx in tqdm([1,2,3,4,5]):
        generated_plan = json.load(open(f'{args.output_dir}/agents/{args.set_type}/{args.model_name}/generated_plan_{idx}.json'))
        if generated_plan[-1][f'{args.model_name}_{args.mode}_results'] not in ["","Max Token Length Exceeded."] :
            try:
                result = results[idx-1].split('```json')[1].split('```')[0]
            except:
                print(f"{idx}:\n{results[idx-1]}\n此计划无法解析。计划必须遵循格式```json [生成的 json 格式计划]```（常见的 gpt-4-preview-1106 json 格式）。出现这种情况时，请手动修改。")
                break
            try:
                # if args.mode == 'ReAct':
                #     generated_plan[-1][f'{args.model_name}{suffix}_{args.mode}_parsed_results'] = eval(result)
                generated_plan[-1][f'{args.model_name}_{args.mode}_parsed_results'] = eval(result)

                # else:
                #     generated_plan[-1][f'{args.model_name}{suffix}_{args.mode}_parsed_results'] = eval(result)
            except:
                print(f"{idx}:\n{result}\n 这是一个非法的json格式。出现这种情况时，请手动修改。")
                break
        else:
            # if args.mode == 'two-stage':
            #     generated_plan[-1][f'{args.model_name}{suffix}_{args.mode}_parsed_results'] = None
            generated_plan[-1][f'{args.model_name}_{args.mode}_parsed_results'] = None

            # else:
            #     generated_plan[-1][f'{args.model_name}{suffix}_{args.mode}_parsed_results'] = None
        
        with open(f'{args.output_dir}{args.set_type}/generated_plan_{idx}.json', 'w', encoding='utf-8') as f:
            json.dump(generated_plan, f, ensure_ascii=False)
