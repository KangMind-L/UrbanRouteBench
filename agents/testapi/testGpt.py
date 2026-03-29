import requests
import json

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
url = "https://api.shredder.money/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-1bzBQsxqUJuTBChw71Ib1ZTPBlGEzkniXZKC3r373BbXtoK9"
    }
data = {
    "model": "deepseek-V3.2",
    "messages": [              
            {"role": "user", "content": "你好"}
            ]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
