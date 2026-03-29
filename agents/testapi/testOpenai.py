from langchain.chat_models import ChatOpenAI

models = [
    # "gpt-5",
    # "deepseek-v3.2",
    # "deepseek-v3.2-exp",
    # "deepseek-v3",
    # "gemini-2.5-pro",
    # "qwen3-coder-480b-a35b-instruct",
    # "deepseek-r1",
    # "glm-4.7",
    # "qwen3-max",
    # "gpt-5.2",
    # "gpt-5.1",
    # "qwen3-32b",
    # "gemini-3-pro",
    # "gemini-3-flash-preview",
    # "gemini-3-pro-preview",
    # "gemini-2.5-flash",
    # "gemini-3-flash" ,
    # "gemini-3" ,
    # "glm-4.7",
    # "kimi-k2.5",
    
]
# chat-completions
#sk-35FfaisxpT0NLMny3EyRX8FI3qvcTsTHPRc04MrCptehzE2S
# 默认分组
# sk-mXIoQJ7Y7ojULM9pb6uy8yFbZTwlUjHVLNvJQB1cBsk77KFX
# nvidia
# sk-1bzBQsxqUJuTBChw71Ib1ZTPBlGEzkniXZKC3r373BbXtoK9
# iflow  qwen3-coder-480b-a35b-instruct  deepseek-v3.2 
# sk-2MmXP8X9pmtqWR7HPXH2ZxWAsr72PnQ2FUoBt4FB0lAY5xs2
# mota
# sk-jEnWQN0y0EgIi21lwONLKR5tD5f9Fbsyk6vY8SmwCiHMXztE
for m in models:
    try:
        llm = ChatOpenAI(
            model=m,
            temperature=0.7,
            max_tokens=2048,
            openai_api_key="sk-35FfaisxpT0NLMny3EyRX8FI3qvcTsTHPRc04MrCptehzE2S",
            base_url="https://api.shredder.money/v1"  # 或你实际后端 URL
        )
        resp = llm.invoke("你好")
         
#         resp = llm.invoke("""你将收到一个自然语言的出行问题，请严格按照以下规则解析为JSON：
# 1. "起点"：出发地。
# 2. "终点"：目的地。
# 3. "途经点数量" 和 "途经点"：如果有途经点，则写数量并用 "-" 连接顺序；没有则数量为0，。
# 4. "时间"：提到的时间（24小时制，格式"HH:MM"）。
# 5. "时间性质"：如果表述是"在某时间之前到达目的地"，写 "到达"；否则是 "出发"。
# 6. "出行方式"：提到的交通方式（只包含公交车、地铁、公共交通、开车、打车、单车+公共交通和空值null这7种情况），存在多种交通方式可以用"|"连接，"单车+公共交通"是一个整体，不需要拆分。公共交通是包含地铁和公交车的，需求中没有提到出行方式的时候，一定不能自己填充出行方式。
# 7. 约束条件：
#   - "出行偏好"：如 "费用最低"、"换乘最少"、"步行最少"、"时间最少"，"最早出发"."最早到达"."最晚出发"."最晚到达","步行最少|时间最少"，存在多种约束情况，用"-"分隔，没提则写 ""空值，一定不能超出这八种偏好范围，禁止构造新的偏好。
#   - "环境约束"：如果有环境类描述（只存在：携带大件行李、下雨、打雷三种情况），写入，否则写入空值""null
#   - "个体约束"：如果有个体约束（只包含孕妇、残疾人、老人、小孩四种情况），写入，否则写入空值""null
#   - "预算"：提到的数字金额

# 以下是几个示例：

# ***** 示例1 *****
# 问题：
# 我需要从深圳市上屋小学开车前往洪田工业区，中午12点16分出发。我是一名孕妇，还携带大件行李，请帮我规划一条安全舒适的驾车路线，费用最好控制在10元以内。
# JSON:
# {"起点": "深圳市上屋小学",  "途经点数量": 0, "途经点": null,"终点": "洪田工业区", "时间": "12:16", "时间性质": "出发", "出行方式": "开车",  "约束条件": {"出行偏好": null,"环境约束": "携带大件行李", "个体约束": "孕妇", "费用": 10.0}}

# ***** 示例2 *****
# 问题：
# 我带着小孩从马坜老二村乘坐公共交通前往东华格林第二幼儿园。需要在晚上6点59分之前到达，希望选择换乘最少、最晚出发的方案，费用控制在4元以内。
# JSON:
# {"起点": "马坜老二村", "途经点数量": 0, "途经点": null,  "终点": "东华格林第二幼儿园","时间": "18:59","时间性质": "到达","出行方式": "公共交通", "约束条件": {"出行偏好": "换乘最少", "环境约束": null, "个体约束": "小孩","费用": 4.0}}

# ***** 示例3 *****
# 问题：
# 我要从荣村小区骑单车转乘公共交通前往汉京·九榕台，下午5点53分出发。希望规划时间最少、最早到达的路线方案，总费用不超过6元。
# JSON:
# {"起点": "荣村小区", "途经点数量": 0, "途经点": null,  "终点": "汉京·九榕台","时间": "17:53", "时间性质": "出发", "出行方式": "公共交通", "约束条件": {"出行偏好": "时间最短", "环境约束": null, "个体约束": null, "费用": 6.0}}

# *
# ***** 示例结束 *****

# 请把下面的问题解析为JSON：不会出现null和上述描述中没出现过的出行方式、环境描述、个体描述。单车和公共交通这种要描述成为（单车+公共交通）,没有提到出行方式的话就默认为null
# 一定不能自己写提到的出行方式，不能自己推断出，要依据需求中提到的出行方式，不能自己填充出行方式。不管其他因素
# 请直接输出 JSON 字符串本身，不要使用工具调用或结构化输出。
# query:我需要从富士君荟骑单车转乘公共交通前往融悦大厦，要求在下午4点58分之前到达，总费用不超过8元。
# """)
        print("Model", m, "✅ 可用，输出:", resp)
        print("Response length:", len(resp.content))

    except Exception as e:
        print("Model", m, "❌ 不可用，错误:", e)
