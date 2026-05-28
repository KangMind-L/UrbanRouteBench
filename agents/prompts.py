from langchain.prompts import PromptTemplate
import json
import math

JSON_GENERATE_2 = """You will receive a natural-language travel request. Parse it into JSON strictly following these rules:
1. "origin": departure place.
2. "destination": destination.
3. "num_via_points" and "via_points": if there are via points, write the count and connect them in order with "-"; otherwise use 0 and null.
4. "time": the mentioned time in 24-hour format "HH:MM".
5. "time_type": if the request means "arrive before a certain time", write "arrival"; otherwise write "departure".
6. "travel_mode": only these values are allowed: bus, subway, public_transit, drive, taxi, bike+public_transit, or null. If multiple modes are explicitly mentioned, join them with "|". "bike+public_transit" is one single value. "public_transit" includes subway and bus. If the user did not mention a mode, do not invent one.
7. "constraints":
  - "travel_preference": only from this closed set: lowest_cost, fewest_transfers, least_walking, shortest_time, earliest_departure, earliest_arrival, latest_departure, latest_arrival. If multiple preferences exist, connect them with "-". If not mentioned, use an empty value. Do not create any new preference.
  - "environment_constraint": only from large_luggage, rain, thunder; otherwise null.
  - "personal_constraint": only from pregnant, disabled, elderly, child; otherwise null.
  - "cost": the mentioned numeric amount.

Examples:

***** Example 1 *****
Question:
I need to drive from Shangwu Primary School, Shenzhen to Hongtian Industrial Zone and leave at 12:16 noon. I am pregnant and carrying large luggage. Please plan a safe and comfortable driving route, and keep the cost within 10 yuan.
JSON:
{{"origin": "Shangwu Primary School, Shenzhen", "num_via_points": 0, "via_points": null, "destination": "Hongtian Industrial Zone", "time": "12:16", "time_type": "departure", "travel_mode": "drive", "constraints": {{"travel_preference": null, "environment_constraint": "large_luggage", "personal_constraint": "pregnant", "cost": 10.0}}}}

***** Example 2 *****
Question:
I am traveling with a child from Mali Laoer Village to Donghua Green Second Kindergarten by public transit. We must arrive before 18:59 and prefer the option with the fewest transfers and the latest feasible departure. Keep the cost within 4 yuan.
JSON:
{{"origin": "Mali Laoer Village", "num_via_points": 0, "via_points": null, "destination": "Donghua Green Second Kindergarten", "time": "18:59", "time_type": "arrival", "travel_mode": "public_transit", "constraints": {{"travel_preference": "fewest_transfers", "environment_constraint": null, "personal_constraint": "child", "cost": 4.0}}}}

***** Example 3 *****
Question:
I want to ride a bike and then transfer to public transit from Rongcun Community to Hanjing Jiurongtai, leaving at 17:53. I want the fastest route and the earliest arrival, with total cost no more than 6 yuan.
JSON:
{{"origin": "Rongcun Community", "num_via_points": 0, "via_points": null, "destination": "Hanjing Jiurongtai", "time": "17:53", "time_type": "departure", "travel_mode": "bike+public_transit", "constraints": {{"travel_preference": "shortest_time", "environment_constraint": null, "personal_constraint": null, "cost": 6.0}}}}

***** End of Examples *****

Now parse the following question into JSON. Do not output any unexpected travel mode, environment description, or personal constraint. Expressions like "bike and public transit" must be normalized to "bike+public_transit". If no travel mode is mentioned, use null. Never infer or fill in a travel mode that is not explicitly stated in the request.
Output the JSON string only. Do not use tool calls, function calls, code fences, or any extra text.

Question: {query}
JSON:
"""
json_generate_prompt_2 = PromptTemplate(
    input_variables=["query"],
    template=JSON_GENERATE_2,
)

JSON_GENERATE_3 = """You will receive a natural-language travel request. Parse it into JSON strictly according to these rules.

Fields:
1. "origin": departure place.
2. "destination": destination.
3. "num_via_points" and "via_points": if there are via points, write the count and list them in order; otherwise use 0 and null.
4. "stay_duration": fill only if the request explicitly says to stay at a via point for at least X minutes; otherwise null.
5. "departure_time": explicit departure time in 24-hour format "HH:MM"; otherwise null.
6. "time_window": if the request explicitly says the total duration must be within X minutes, write X; otherwise null.
7. "travel_mode": only bus, subway, taxi, bike, or null. Join multiple explicit modes with "|".
   If no mode is explicitly mentioned, infer conservatively from constraints:
   - elderly / child / disabled: cannot choose drive or bike.
   - pregnant: cannot choose bike.
   - if there is an environmental constraint, cannot choose bike.
   - if both personal and environmental constraints exist and no mode is specified, write null.
8. "constraints":
   - "travel_preference": only shortest_time, lowest_cost, fewest_transfers, least_walking, joined with "|" when needed.
     Treat natural variants accordingly, for example:
     cheapest / lowest cost -> lowest_cost
     as few transfers as possible / direct if possible -> fewest_transfers
     as fast as possible -> shortest_time
     walk as little as possible -> least_walking
     A hard budget cap alone does not mean lowest_cost.
     If no preference is mentioned but personal or environmental constraints exist, you may infer least_walking|fewest_transfers. Otherwise write null.
   - "environment_constraint": only rain, heavy_rain, bad_weather, large_luggage; otherwise null.
   - "personal_constraint": only elderly, child, pregnant, disabled; otherwise null.
   - "cost": numeric upper budget if explicitly mentioned; otherwise null.

Example 1:
Question:
I need to travel from Kengzi Base to Anju Nanxinyuan. I want to leave at 12:31, keep travel time short, and reduce transfers. I do not require a specific mode, but public transit is preferred. Keep the cost within 10 yuan.
JSON:
{{"origin":"Kengzi Base","num_via_points":0,"via_points":null,"stay_duration":null,"destination":"Anju Nanxinyuan","departure_time":"12:31","time_window":0,"travel_mode":"bus|subway","constraints":{{"travel_preference":"shortest_time|fewest_transfers","environment_constraint":null,"personal_constraint":null,"cost":10}}}}

Example 2:
Question:
I plan to leave Xin'an Middle School Yanchuan Campus at 15:36, go to Miaoxi First Market first, stay there for at least 15 minutes, and then continue to Jinjia Color Printing. The whole trip should stay within 85 minutes. Because it is raining and I am pregnant, please plan the fastest feasible route. Budget: no more than 28 yuan.
JSON:
{{"origin":"Xin'an Middle School Yanchuan Campus","num_via_points":1,"via_points":"Miaoxi First Market","stay_duration":15,"destination":"Jinjia Color Printing","departure_time":"15:36","time_window":85,"travel_mode":"bus|subway|taxi","constraints":{{"travel_preference":"shortest_time","environment_constraint":"rain","personal_constraint":"pregnant","cost":28}}}}

Output requirements:
- Output the JSON string only.
- No explanation.
- No extra text.
- No code fences.
- No tool or function calls.

Question: {query}
JSON:
"""

json_generate_prompt_3 = PromptTemplate(
    input_variables=["query"],
    template=JSON_GENERATE_3,
)

JSON_GENERATE = """You will receive a natural-language travel request. Parse it into JSON strictly following these rules:
1. "origin": departure place.
2. "destination": destination.
3. "num_via_points" and "via_points": if via points exist, write the count and connect them with "-->"; otherwise use 0 and None.
4. "time": the mentioned time in 24-hour format "HH:MM".
5. "constraints":
   - "travel_mode": only bus, subway, bus+subway, drive, taxi, or None.
   - "travel_preference": only values such as lowest_cost, fewest_transfers, shortest_distance, shortest_time; if not mentioned, write None.
   - "budget": mentioned amount; otherwise None.
   - "time_type": if the request means arriving before a given time, write "arrival"; otherwise write "departure".
   - "environment_limit": only large_luggage, heavy_rain, thunder; otherwise None.
   - "personal_limit": only pregnant, disabled, elderly, child; otherwise None.

Example 1:
Question:
At 12:50 noon I need to take a taxi from Baoping Intersection to Guanhu Songyuanxia with large luggage, and I need to stop by Kukeng Central Area on the way. My budget is about 110.
JSON:
{{"origin": "Baoping Intersection", "destination": "Guanhu Songyuanxia", "num_via_points": 1, "via_points": "Kukeng Central Area", "time": "12:50", "constraints": {{"travel_mode": "taxi", "travel_preference": None, "budget": 110.0, "time_type": "departure", "environment_limit": "large_luggage", "personal_limit": None}}}}

Example 2:
Question:
I am pregnant and it is inconvenient for me right now. At 09:48 in the morning I need to take a bus from Junfengye Building to Dayun. Can you find a route with no transfer or as few transfers as possible?
JSON:
{{"origin": "Junfengye Building", "destination": "Dayun", "num_via_points": 0, "via_points": "None", "time": "09:48", "constraints": {{"travel_mode": "bus", "travel_preference": "fewest_transfers", "budget": 0, "time_type": "departure", "environment_limit": None, "personal_limit": "pregnant"}}}}

Parse the following question into JSON. Do not output null or any travel mode, environment description, or personal constraint outside the allowed set. Normalize public-transit wording to "bus+subway". If no travel mode is mentioned, default to None.
Question: {query}
JSON:
"""

json_generate_prompt = PromptTemplate(
    input_variables=["query"],
    template=JSON_GENERATE,
)

QUERY_GENERATE = """You will receive a JSON object. Generate one natural-language travel query from it.
Meaning of fields:
- "origin": departure place
- "destination": destination
- "num_via_points": number of via points
- "via_point_order": ordered via points
- "time": 24-hour time
- "arrive_by" in constraints: true means the user must arrive before the given time; false means the time is the departure time
- If there is a via point, the request must clearly state that the user will stay there for at least 30 minutes.
Follow the example style closely. The final output should be a realistic route-planning request, without irrelevant explanation.

JSON:{json}
QUERY:
"""
query_generate_prompt = PromptTemplate(
                        input_variables=["json"],
                        template=QUERY_GENERATE,
                        )

# Generate five different phrasings for each question.
QUERY_GENERATE_1 = """You will receive a JSON object and a SCRATCHPAD. Generate one route-planning query each time, using one of 5 styles, and avoid styles already used in the SCRATCHPAD.
Rules:
1. Keep the original meaning and constraints unchanged.
2. Time, budget, and counts must remain exact.
3. If a via point exists, explicitly mention staying there for at least 30 minutes.
4. Generate exactly one query each time.

Five styles:
1. Standard: complete, polite, formal.
2. Urgent: emphasizes urgency and importance.
3. Casual: natural and conversational.
4. Detailed requirements: clearly lists the requirements.
5. Concise command: compressed, instruction-like wording.

JSON:{json}
SCRATCHPAD:{scratchpad}
QUERY:
"""
query_generate_prompt_1 = PromptTemplate(
                        input_variables=["json",'scratchpad'],
                        template=QUERY_GENERATE_1,
                        )
# Generate three different phrasings for each question.
QUERY_GENERATE_2 = """You will receive a JSON object and a SCRATCHPAD. Generate one route-planning query each time, using one of 3 styles, and avoid styles already used in the SCRATCHPAD.
Rules:
1. Keep the original meaning and constraints unchanged.
2. Time, budget, and counts must remain exact.
3. If a via point exists, mention stopping there for a concrete purpose with an approximate duration between 10 and 60 minutes, such as refueling, shopping, eating, picking someone up, or visiting.
4. Generate exactly one query each time.

Three styles:
1. Direct request.
2. Question form.
3. Concise description.

JSON:{json}
SCRATCHPAD:{scratchpad}
QUERY:
"""
query_generate_prompt_2 = PromptTemplate(
                        input_variables=["json",'scratchpad'],
                        template=QUERY_GENERATE_2,

)                        

QUERY_GENERATE_3 = """You will receive a simplified travel query. Rewrite it into a more natural and fluent expression.
Requirements:
1. Preserve all original information: origin, destination, via points, time, mode, budget, and constraints.
2. Use more natural everyday wording.
3. You may add reasonable connectives or tone words.
4. Make time, budget, and constraints clear.

Input: {query}
Output:
"""

query_generate_prompt_3 = PromptTemplate(
                        input_variables=["query"],
                        template=QUERY_GENERATE_3,
                        )
QUERY_GENERATE_4 = """You will receive a JSON object. Generate one natural-language travel query from it.
Field meanings:
- "origin": departure place
- "destination": destination
- "num_via_points": number of via points
- "via_points": place(s) that must be visited on the way
- "time": 24-hour time
- "time_type": if it means arriving before a given time, use an arrival-style request; otherwise treat it as departure time
- If there is a via point, explicitly say the user needs to stay there for at least 30 minutes.
Follow the example style and output only the final travel query.

JSON:{json}
QUERY:"""
query_generate_prompt_4 = PromptTemplate(
                        input_variables=["json"],
                        template=QUERY_GENERATE_4,
                        )

QUERY_GENERATE_5 = """You will receive a JSON object. Generate one natural, realistic travel-planning request in Chinese based on it.
Do not mechanically copy field names. Understand the meaning and express the request naturally.
Rules:
1. If "travel_mode" is empty, you may omit it.
2. If there is one mode, mention it directly.
3. If there are multiple modes, describe them naturally instead of just listing them.
4. Express "travel_preference" in natural language while preserving meaning.
5. If a via point exists, you must say the user will go there first, stay for the specified time, and then continue to the destination.
6. Do not explain the JSON or output extra commentary.

JSON:{json}
QUERY:
"""

query_generate_prompt_5 = PromptTemplate(
                        input_variables=["json"],
                        template=QUERY_GENERATE_5,
                        )

QUERY_GENERATE_6 = """You will receive a JSON object. Generate exactly one Chinese travel query in a constraint-first style.
Style requirements:
- Do not start with the origin and destination.
- Start with preferences, restrictions, or unacceptable conditions.
- Use wording such as "provided that", "prioritizing", "avoid if possible", or "must satisfy".
- The tone should sound like the user is telling the system what kind of route is acceptable.
- Origin, destination, and time may appear later in the sentence.
- Do not write it like a narrative or a navigation command.
Other rules:
- If preferences exist, express them clearly.
- If via points exist, say the user goes there first, stays for the required time, and then continues.
- If multiple modes exist, express them naturally.
- Time must be explicit and not vague.

JSON:{json}
Please output one line only.
"""


query_generate_prompt_6 = PromptTemplate(
                        input_variables=["json"],
                        template=QUERY_GENERATE_6,
                        )
QUERY_GENERATE_7 = """You will receive a JSON object. Generate exactly one Chinese travel query in a narrative, daily-life style.
Style requirements:
- Start from a life situation or personal condition, such as time, weather, health, or a temporary arrangement.
- Sound conversational and natural, like a real user explaining their plan.
- Do not write it like a navigation command or a dry condition list.
- You may reorder the information, but do not omit anything important.
- Time must be explicit, not vague.
Other rules:
- If environmental or personal constraints exist, blend them naturally into the narration.
- If via points exist, clearly say where to go first, how long to stay, and then continue to the destination.
- Mention travel mode naturally.
- Do not explain the JSON or mention field names.

JSON:{json}
Please output one line only.
"""
                      
query_generate_prompt_7 = PromptTemplate(
                        input_variables=["json"],
                        template=QUERY_GENERATE_7,
                        )

ZEROSHOT_REACT_INSTRUCTION = """
You are using the ReAct framework. You must strictly follow the single-step output rule.

Single-step output rule:
- Each reply may contain only one module: Thought, Action, or Observation.
- Thought must not contain any Action.
- Action must contain exactly one tool call and no extra text. Only one of CoordSearch, RouteSearch, RouteRank, NotebookWrite, or Planner may be called.
- Do not put Thought and Action in the same message.
- After one step, wait for the next turn before producing the next step.

1. CoordSearch[place_name]
Description: a geographic coordinate lookup tool.
Parameter:
- place_name: the place whose coordinates should be searched.
Example: CoordSearch[Shenzhen University]

2. RouteSearch[{"fromPlace": ..., "toPlace": ..., "viaPlace": ..., "time": ..., "mode": ..., "stayMinutes": ..., "window": ...}]
Description: a route-planning tool for urban travel. Search a one-segment or two-segment route only once; do not split it into separate searches.
You must strictly use coordinates already stored in the scratchpad. Never invent coordinates.
Parameter rules:
- fromPlace / toPlace are required and must be in the form "place_name::latitude,longitude".
- time is required and must be the parsed 24-hour time "HH:MM".
- viaPlace is optional and should be passed only when a via point explicitly exists.
- stayMinutes is optional and should be passed only when the user explicitly mentions a stay duration.
- window is optional and should be passed only when the user explicitly mentions a time window.
- mode is optional and only allows these mappings:
  subway -> SUBWAY
  bus -> BUS
  bus+subway -> TRANSIT
  taxi -> CAR_PICKUP
  drive -> CAR
  bike+bus/subway -> TRANSIT,BICYCLE
Usage rules:
- If the user explicitly specifies a travel mode, use the parsed result directly.
- Multiple modes must be joined with "|".
- If no travel mode is specified, pass an empty string.
Implicit constraints, only when mode is empty:
- large_luggage: forbid TRANSIT,BICYCLE
- elderly: forbid CAR, TRANSIT,BICYCLE
- pregnant: forbid TRANSIT,BICYCLE
- child: forbid CAR
- disabled: forbid CAR, TRANSIT,BICYCLE
Important constraints:
- Only the modes above are allowed. Do not add or infer undefined modes.
- Constraints may only remove modes, never introduce new ones.

Example:
RouteSearch[{{"fromPlace": "origin::22.6537223,114.0242094", "toPlace": "destination::22.543096,114.057865", "viaPlace": "via::22.5934193,113.993249", "time": "19:00", "mode": "BUS|SUBWAY", "stayMinutes": 20, "window": "180"}}]
RouteSearch[{{"fromPlace": "origin::22.6537223,114.0242094", "toPlace": "destination::22.543096,114.057865", "time": "19:00", "mode": "BUS|SUBWAY", "window": "180"}}]

3. RouteRank[time=, time_window=, preference=, stay_time=]
Description: rank candidate routes returned by RouteSearch and choose the optimal result.
Required parameters:
- time=HH:MM: reference time in 24-hour format.
- time_window=minutes: if no time window exists, write time_window=None.
- preference="...": allowed atomic preferences are shortest_time, lowest_cost, least_walking, fewest_transfers. If no preference exists, write preference=None. One or two atomic preferences may be joined with "|".
- stay_time=minutes: if there is no relevant stay, write stay_time=None.
Important constraints:
- Exactly four parameters must be passed.
- Ranking is based only on RouteSearch results and Notebook contents.
- If preference exists, it must strictly follow the allowed enumeration and combination rules.
Examples:
RouteRank[time="17:45",time_window=180,preference="shortest_time|fewest_transfers",stay_time=20]
RouteRank[time="17:45",time_window=None,preference=None,stay_time=None]

4. NotebookWrite[label]
Description: write a short labeled entry into Notebook. This must be called immediately after every CoordSearch, RouteSearch, and RouteRank call so Planner can see the stored data.
Parameter:
- label: a short description or tag for the stored data.

5. Planner[query]
Description: an intelligent planning tool that produces a detailed plan from the user request and Notebook contents.
Parameter:
- query: the user request and parsed parameters.

Important correction:
- Thought contains only reasoning and analysis, never tool calls or action intent.
- Action contains exactly one tool call in the form ToolName[arguments].
- Each operation may call exactly one tool function once.
- Strictly obey the single-step output rule.

Query: {query} scratchpad: {scratchpad}"""
zeroshot_react_agent_prompt = PromptTemplate(
                        input_variables=["query", "scratchpad"],
                        template=ZEROSHOT_REACT_INSTRUCTION,
                        )

PLANNER_INSTRUCTION = """You are a Shenzhen travel-planning assistant. Based on the provided information, generate a complete, detailed, and realistic travel plan.

The trip may be:
- a single segment: origin -> destination
- two segments: origin -> via point -> stay -> destination

Follow the output format strictly. Do not omit fields and do not add new fields.
Use "-" when a field does not need to be filled.
Distance must be in meters. Time duration must use minutes and seconds.
Allowed plan preferences are: shortest_walking, shortest_time, lowest_cost, fewest_transfers, shortest_distance. If the user does not specify one, treat it as no preference.

Example output skeleton:
Travel Plan:
Route Summary: a brief summary of the route
Detailed Steps:
First leg: from **Origin** to **Via Point**
  Step 1: from **Origin** walk to **Stop A**
    Mode: walk
    Distance: 100.0 meters
    Estimated Time: 2 minutes 0 seconds
    Start Time: 08:00:00
    End Time: 08:02:00
Second leg: stay at **Via Point** for 25 minutes, then continue to **Destination**
...
Plan Preference: fewest_transfers
Departure Time: 08:00:00
Arrival Time: 09:00:00
Transfers: 2
Total Travel Time: 60 minutes 0 seconds
Estimated Cost: 8.0 yuan
Total Walking Distance: 500.0 meters
Total Cycling Distance: 0.0 meters
Total Distance: 12000.0 meters

Important constraints:
1. Every step's start and end time must exactly match the collected information.
2. Place names must exactly match the database records.
3. Do not use tools, JSON, or function calls.
4. Output only the final travel-plan text.

Collected information:
{text}

User request:
{query}

Travel plan:
"""
COT_PLANNER_INSTRUCTION = """You are a Shenzhen travel-planning assistant. Based on the provided information, generate a complete, detailed, and realistic travel plan.

The trip may be:
- a single segment: origin -> destination
- two segments: origin -> via point -> stay -> destination

Follow the output format strictly. Do not omit fields and do not add new fields.
Use "-" when a field does not need to be filled.
Distance must be in meters. Time duration must use minutes and seconds.
Allowed plan preferences are: shortest_walking, shortest_time, lowest_cost, fewest_transfers, shortest_distance. If the user does not specify one, treat it as no preference.

Example output skeleton:
Travel Plan:
Route Summary: a brief summary of the route
Detailed Steps:
First leg: from **Origin** to **Via Point**
  Step 1: from **Origin** walk to **Stop A**
    Mode: walk
    Distance: 100.0 meters
    Estimated Time: 2 minutes 0 seconds
    Start Time: 08:00:00
    End Time: 08:02:00
Second leg: stay at **Via Point** for 25 minutes, then continue to **Destination**
...
Plan Preference: fewest_transfers
Departure Time: 08:00:00
Arrival Time: 09:00:00
Transfers: 2
Total Travel Time: 60 minutes 0 seconds
Estimated Cost: 8.0 yuan
Total Walking Distance: 500.0 meters
Total Cycling Distance: 0.0 meters
Total Distance: 12000.0 meters

Important constraints:
1. Every step's start and end time must exactly match the collected information.
2. Place names must exactly match the database records.
3. Do not use tools, JSON, or function calls.
4. Output only the final travel-plan text.

Collected information:
{text}

User request:
{query}

Travel plan:
Let us think step by step. First, """

REACT_PLANNER_INSTRUCTION = """You are a Shenzhen travel-planning assistant. Based on the provided information, generate a complete, detailed, and realistic travel plan.

The trip may be:
- a single segment: origin -> destination
- two segments: origin -> via point -> stay -> destination

Follow the output format strictly. Do not omit fields and do not add new fields.
Use "-" when a field does not need to be filled.
Distance must be in meters. Time duration must use minutes and seconds.
Allowed plan preferences are: shortest_walking, shortest_time, lowest_cost, fewest_transfers, shortest_distance. If the user does not specify one, treat it as no preference.

You are using the ReAct framework:
- Thought: reasoning only.
- Action: exactly one tool call.
- Observation: tool result.

Available actions:
1. LogicalJudgment[subplan_json]
Validate the logic of one complete segment of the trip.
2. PlanSummary[summary_json]
Summarize the final complete plan. If there are two trip segments, total transfers equal the sum of transfers in each segment plus one when the via-point stay creates the segment break.
3. Finish[final_plan]
Return the final complete plan.

You must use Finish to indicate completion. Each action may call only one function once.

Collected information:
{text}

User request:
{query}{scratchpad}
"""

REFLECTION_HEADER = 'You previously tried to provide a sub-plan or a plan summary but failed. The reflections below offer guidance to avoid the same failure. Use them to improve your strategy for producing a correct plan.'
REFLECT_INSTRUCTION = """You are an advanced reasoning agent that can improve through self-reflection. You will be given a previous reasoning attempt in which you were asked to validate sub-plan logic, summarize the overall plan logic, and answer a route-planning query using the available information. A step is considered valid only if the timing, travel mode, and place-name logic are correct, and the summary is also correct. You failed to create the plan because you ran out of the allowed reasoning steps. Diagnose the likely causes of failure in a few sentences, then produce a new concise high-level plan that avoids the same failure. Use complete sentences.
Collected information: {text}

Previous attempt:
Question: {query}{scratchpad}

Reflection:"""

REACT_REFLECT_PLANNER_INSTRUCTION = """You are a Shenzhen travel-planning assistant. Based on the provided information, generate a complete, detailed, and realistic travel plan.

The trip may be:
- a single segment: origin -> destination
- two segments: origin -> via point -> stay -> destination

Follow the output format strictly. Do not omit fields and do not add new fields.
Use "-" when a field does not need to be filled.
Distance must be in meters. Time duration must use minutes and seconds.
Allowed plan preferences are: shortest_walking, shortest_time, lowest_cost, fewest_transfers, shortest_distance. If the user does not specify one, treat it as no preference.

You are using the ReAct framework:
- Thought: reasoning only.
- Action: exactly one tool call.
- Observation: tool result.

Available actions:
1. LogicalJudgment[subplan_json]
Validate the logic of one complete segment of the trip.
2. PlanSummary[summary_json]
Summarize the final complete plan. If there are two trip segments, total transfers equal the sum of transfers in each segment plus one when the via-point stay creates the segment break.
3. Finish[final_plan]
Return the final complete plan.

Use the following reflections to improve your reasoning:
{reflections}

You must use Finish to indicate completion. Each action may call only one function once.

Collected information:
{text}

User request:
{query}{scratchpad}
"""

planner_agent_prompt = PromptTemplate(
                        input_variables=["text","query"],
                        template = PLANNER_INSTRUCTION,
                        )


cot_planner_agent_prompt = PromptTemplate(
                        input_variables=["text","query"],
                        template = COT_PLANNER_INSTRUCTION,
                        )

react_planner_agent_prompt = PromptTemplate(
                        input_variables=["text","query", "scratchpad"],
                        template = REACT_PLANNER_INSTRUCTION,
                        )

reflect_prompt = PromptTemplate(
                        input_variables=["text", "query", "scratchpad"],
                        template = REFLECT_INSTRUCTION,
                        )

react_reflect_planner_agent_prompt = PromptTemplate(
                        input_variables=["text", "query", "reflections", "scratchpad"],
                        template = REACT_REFLECT_PLANNER_INSTRUCTION,
                        )
