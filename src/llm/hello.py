import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

base_url = os.environ["LLM_BASE_URL"]
api_key = os.environ["LLM_API_KEY"]
model = os.environ["LLM_MODEL"]
timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

client = OpenAI(
    base_url=base_url,
    api_key=api_key,
    timeout=timeout,
    max_retries=0,
)

response = client.chat.completions.create(
    model=model,
    temperature=0,
    messages=[
        {
            "role": "system",
            "content": (
                "This is a connectivity test. "
                "Your entire response MUST be exactly the lowercase word ready. "
                "Do not explain. Do not add punctuation."
            ),
        },
        {
            "role": "user",
            "content": "Return exactly: ready",
        },
    ],
    max_tokens=5,
)

answer = response.choices[0].message.content or ""
answer = answer.strip()

print("provider =", base_url)
print("model    =", model)
print("answer   =", answer)

if "ready" not in answer.lower():
    raise RuntimeError(f"Provider responded, but did not contain 'ready': {answer!r}")

print("STAGE 0 PROVIDER CHECK: PASS")
