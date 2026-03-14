import os
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

api_key = os.environ.get("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=api_key)
try:
    response = llm.invoke("Hello, how are you?")
    print(f"Success! Response: {response.content}")
except Exception as e:
    print(f"Failed! Error: {e}")
