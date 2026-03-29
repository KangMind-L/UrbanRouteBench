

import pandas as pd
query_data_list = pd.read_csv('D:\\project\\Python\\TripPlannerGPT\\validation.csv')
numbers = [i for i in range(1,len(query_data_list)+1)]
for number in numbers:
    query = query_data_list.iloc[number-1]['query']