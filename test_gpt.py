import os

from dotenv import load_dotenv
from openai import OpenAI

# Load .env if available
load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
resp = client.chat.completions.create(
    model="gpt-5-mini", messages=[{"role": "user", "content": "Mikä päivä tänään?"}]
)
print(resp.choices[0].message.content)
print(resp)
