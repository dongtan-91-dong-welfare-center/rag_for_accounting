import os
from dotenv import load_dotenv
from openai import OpenAI

from src.utils.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS

load_dotenv()

client: OpenAI = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=LLM_MAX_RETRIES,
)

