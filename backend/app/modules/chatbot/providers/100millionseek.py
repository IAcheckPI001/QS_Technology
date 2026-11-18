

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
   api_key=os.environ["HMS_API_KEY"],
   base_url="https://100milionseek.top/v1",
)


if __name__ == "__main__":
    stream = client.chat.completions.create(
        model="deepseek-v4.1-flash-free",
        messages=[{"role": "user", "content": "RAG là gì?"}],
        stream=True,
        )
    for chunk in stream:
        if chunk.choices:
            print(chunk.choices[0].delta.content or "", end="")