import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

# ── Load .env from root folder ─────────────────────────────────────────────
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import urllib.request
from browser_use import Agent, Browser

app = FastAPI()

class GeminiModel:
    """
    A custom LLM wrapper that uses raw REST calls to bypass Pydantic/LangChain 
    dependency hell with browser-use 0.12.2.
    """
    def __init__(self, model_name, api_key):
        self.model_name = model_name
        self.model = model_name
        self.api_key = api_key
        self.provider = "google"
        
    def bind_tools(self, tools, **kwargs):
        return self

    async def ainvoke(self, input, *args, **kwargs):
        prompt = ""
        if isinstance(input, list):
             prompt = input[-1].content
        elif hasattr(input, "content"):
             prompt = input.content
        else:
             prompt = str(input)
             
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4000},
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            loop = asyncio.get_event_loop()
            def sync_call():
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            
            data = await loop.run_in_executor(None, sync_call)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            class MockResponse:
                def __init__(self, text, model_name):
                    self.content = text
                    self.completion = text
                    self.usage = self.Usage()
                    self.response_metadata = {"model_name": model_name}
                class Usage:
                    def __init__(self):
                        self.prompt_tokens = 0
                        self.completion_tokens = 0
                        self.total_tokens = 0
                    def __getattr__(self, name): return 0
                    def items(self): return [].items()

            return MockResponse(text, self.model_name)
        except Exception as e:
            class ErrorResponse:
                def __init__(self, err_text):
                    self.content = f"Error: {err_text}"
                    self.completion = self.content
                    self.usage = None
                    self.response_metadata = {}
            return ErrorResponse(str(e))

# Configure LLM
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
llm = GeminiModel("gemini-flash-latest", GOOGLE_API_KEY)

class ResearchRequest(BaseModel):
    market_query: str

async def run_search_agent(query: str):
    """
    Runs the browser-use agent to find resources for a Polymarket query.
    """
    browser = Browser(
        headless=True,
        disable_security=True,
    )
    
    task = f"""
    Research the following market prediction question from Polymarket: "{query}"
    
    Your goal is to find 3-5 high-quality, up-to-date resources (news articles, official reports, 
    or expert data) that help answer this question.
    
    For each resource, provide:
    1. The Title
    2. The URL
    3. A brief summary of why it is relevant.
    
    Finally, provide a "Likelihood Score" (0-100%) based on the evidence you found.
    Return the result in a clear, concise format.
    """
    
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )
    
    history = await agent.run(max_steps=20)
    result = history.final_result()
    
    await browser.kill()
    return result

@app.post("/research")
async def research_market(request: ResearchRequest):
    try:
        print(f"Agent starting research for: {request.market_query}")
        result = await run_search_agent(request.market_query)
        return {"status": "success", "analysis": result}
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
