import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client: OpenAI = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
