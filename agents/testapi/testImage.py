# from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    temperature=0,
    model="kimi-k2-thinking",
    openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
    base_url="https://api.shredder.money/v1",
)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "这张图片里有什么？"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://pic.nximg.cn/file/20230418/33458386_091455553121_2.jpg"
                }
            },
        ],
    }
]

response = llm.invoke(messages)
print(response.content)
