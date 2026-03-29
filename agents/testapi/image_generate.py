# from langchain_openai import OpenAIImages

# client = OpenAIImages(
#     mode_name = "gpt-5",
#     openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
#     base_url="https://api.shredder.money/v1",   # Shredder 的接口
# )

# resp = client.generate(
#     prompt="一只戴着墨镜的猫在喝奶茶，卡通风格，高清",
#     size="1024x1024",
#     n=1,
# )

# # 获取图片URL
# img_url = resp.data[0].url
# print("生成图片地址：", img_url)


# from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(
#     model="gpt-5",                         # 如果是图像模型也在这里写，例如 gpt-image-1（看你 API 是否支持）
#     temperature=0,
#     openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
#     base_url="https://api.shredder.money/v1",
# )

# prompt = """
# 请生成一张图片，内容是一只坐在月亮上的猫，动漫风格。
# """

# response = llm.invoke(prompt)
# print(response)


# from langchain_community.image import OpenAIImageGeneration
# import base64

# # 初始化图像生成器
# image_gen = OpenAIImageGeneration(
#     model="gpt-5",   # 图像生成模型，gpt-image-1 或 gpt-5 取决于你的服务端支持
#     openai_api_key="sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi",
#     base_url="https://api.shredder.money/v1",  # 你使用的服务器
# )

# # 生成图像
# result = image_gen.run(
#     prompt="一只坐在沙滩上喝椰汁的猫，可爱风格，高清",
#     n=1,         # 生成图片数量
#     size="1024x1024"  # 图片分辨率，可选 256x256, 512x512, 1024x1024
# )

# # 输出结果（通常是 base64 编码）
# image_base64 = result[0]['b64_json'] if isinstance(result, list) else result['b64_json']

# # 保存图片
# with open("cat_beach.png", "wb") as f:
#     f.write(base64.b64decode(image_base64))

# print("图片已生成并保存为 cat_beach.png")


import requests
import base64

url = "https://api.shredder.money/v1/images/generations"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-7Rg66SYcYI7foEJVYb55G8hNRBqJVjWNuCRRANIVw41zDsdi"
}

payload = {
    "model": "dall-e-3",  # 这里换成官方支持的图片生成模型
    "prompt": "一只穿宇航服的杰尼龟站在月球上，超真实风格",
    "size": "1024x1024",
    "n": 1
}

response = requests.post(url, headers=headers, json=payload)

# 打印返回信息，方便调试
print(response.status_code)
print(response.text)

data = response.json()

if "data" in data and len(data["data"]) > 0:
    img_base64 = data["data"][0]["b64_json"]
    with open("output.png", "wb") as f:
        f.write(base64.b64decode(img_base64))
    print("图片已保存为 output.png")
else:
    print("生成图片失败，返回内容:", data)

