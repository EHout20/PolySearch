#!/usr/bin/env python3
"""
polymarket_agent.py — Polymarket research agent using Gamma API + browser-use + Gemini

Usage:
    cd "/Users/erichout/ai child companion"
    python polymarket_agent.py "will bitcoin hit 100k"
    python polymarket_agent.py "Fed rate cut May 2025"
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote_plus
import urllib.request
from urllib.error import URLError

# ── Load .env from root folder ─────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GAMMA_BASE     = "https://gamma-api.polymarket.com"
GEMINI_MODEL   = "gemini-flash-latest"
GEMINI_BROWSER_MODEL = "gemini-flash-latest" 


# ── Helpers ───────────────────────────────────────────────────────────────────

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    print("Please install langchain-google-genai via pip")
    sys.exit(1)

def fmt_dollars(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "$0"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.0f}K"
    return f"${n:.0f}"


def gamma_get(path: str) -> list | dict:
    url = f"{GAMMA_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def extract_market(event: dict) -> dict:
    market = (event.get("markets") or [{}])[0]
    prices_raw = market.get("outcomePrices", '["0.5","0.5"]')
    try:
        prices = json.loads(prices_raw)
    except Exception:
        prices = ["0.5", "0.5"]
    yes_price  = float(prices[0]) if prices else 0.5
    probability = round(yes_price * 100)
    
    # Handle multi-outcome label
    outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
    is_multi = len(outcomes) > 2
    prob_label = "Implied probability" if not is_multi else f"Leading: {outcomes[0]}"

    raw_delta  = float(market.get("oneDayPriceChange") or 0)
    sign       = "+" if raw_delta >= 0 else ""
    delta_str  = f"{sign}{raw_delta*100:.1f}%"
    direction  = "up" if raw_delta > 0.002 else ("down" if raw_delta < -0.002 else "neutral")
    
    return {
        "title": event.get("title") or event.get("slug") or "Market",
        "slug": event.get("slug", ""),
        "probability": probability,
        "probabilityLabel": prob_label,
        "delta24h": delta_str,
        "deltaDirection": direction,
        "volume": fmt_dollars(event.get("volumeNum") or event.get("volume") or 0),
        "liquidity": fmt_dollars(event.get("liquidityNum") or event.get("liquidity") or 0),
        "outcomes": outcomes,
        "outcomePrices": prices,
        "description": event.get("description", ""),
        "isMulti": is_multi
    }


# ── Step 1: Gamma lookup & Validation ─────────────────────────────────────────
def fetch_gamma(query: str) -> tuple[dict, list[dict], bool]:
    """Returns (best_event_dict, related_events_list, is_valid)"""
    params = urlencode({
        "q":         query,
        "active":    "true",
        "closed":    "false",
        "limit":     "20",  # Increase limit to see more results for keyword matching
    })
    
    default_market = {"title": query, "probability": 50, "delta24h": "0%", "volume": "$0", "liquidity": "$0", "slug": ""}

    try:
        events = gamma_get(f"/events?{params}")
        if not events or len(events) == 0:
            return default_market, [], False
        
        # REFINEMENT: Mirror Next.js scoring logic (score by word match, sort by score then volume)
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        scored_events = []
        
        for e in events:
            title = (e.get("title") or "").lower()
            score = sum(1 for w in query_words if w in title)
            vol = float(e.get("volumeNum") or e.get("volume") or 0)
            scored_events.append((score, vol, e))
            
        # Sort by score desc, then volume desc
        scored_events.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_event = scored_events[0][2]

        # Gather related markets (others from the same search that ARENT the best)
        best    = extract_market(best_event)
        related = []
        for e in events:
            if e.get("id") != best_event.get("id"):
                related.append(extract_market(e))
            if len(related) >= 10: break
            
        return best, related, True
    except Exception as e:
        sys.stderr.write(f"[Gamma API error] {e}\n")
        return default_market, [], False


# ── Step 2: browser-use web research (Consolidated Call) ─────────────────────
async def browser_research(query: str, market: dict, related: list[dict]) -> str:
    """
    Use browser-use + Gemini to find recent web content and generate the ANALYST BRIEF in one go.
    This saves 50% on LLM calls to avoid 429 limits.
    """
    try:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        return json.dumps({"error": f"browser-use not available: {e}"})

    if not GOOGLE_API_KEY:
        return json.dumps({"error": "GOOGLE_API_KEY missing"})

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        # Transparent Proxy to bypass Pydantic monkeypatching issues
        class TransparentProxy:
            def __init__(self, **kwargs):
                self._llm = ChatGoogleGenerativeAI(**kwargs)
                self.provider = "google"
                self.model = GEMINI_BROWSER_MODEL
                self.model_name = GEMINI_BROWSER_MODEL
            def items(self):
                return {"provider": self.provider, "model": self.model}.items()
            def __getattr__(self, name):
                return getattr(self._llm, name)
            def bind_tools(self, *args, **kwargs):
                return self._llm.bind_tools(*args, **kwargs)
            async def ainvoke(self, *args, **kwargs):
                return await self._llm.ainvoke(*args, **kwargs)
            def invoke(self, *args, **kwargs):
                return self._llm.invoke(*args, **kwargs)
            
        llm = TransparentProxy(model=GEMINI_BROWSER_MODEL, api_key=GOOGLE_API_KEY)
    except ImportError:
        return json.dumps({"error": "langchain-google-genai not installed"})

    # Configure browser to be truly headless (no tabs popping up)
    browser = Browser(config=BrowserConfig(headless=True))

    edu_prompt = f"""You are an Educational Research Agent.
YOUR GOAL: Explain "{query}" to a complete beginner.
Research the terminology, the entities involved (e.g., specific sports leagues, agencies, political bodies), and the current context.
For example, if the query includes "La Liga", explain what La Liga is and who the teams are. 
Return a clear, concise 2-3 paragraph summary focusing on the basics. Do not use JSON."""

    scrape_prompt = f"""You are a News Scraping Agent.
YOUR GOAL: Find 5 RECENT and DIVERSE news articles about "{query}".
1. Go to google.com/news.
2. Search for "{query} latest news predictions".
3. Open at least 5 DIFFERENT organic results from VARIOUS publishers (e.g., ESPN, BBC, Reuters, specialized blogs).
4. Do NOT use "Polymarket" or "Google Search" as your sources. Find actual news sites.
5. From each result, extract the page title, the REAL source name, and the EXACT URL.
6. Close all tabs when finished.

CRITICAL: Return ONLY a RAW JSON object. Do NOT use placeholders like "Site Name".
{{
  "news": [
    {{"source": "Actual Site Name", "age": "e.g. 2 hours ago", "headline": "The real headline", "snippet": "A meaningful summary snippet.", "sentiment": "bull|bear|neutral", "url": "https://full-unique-url.com"}},
    ...
  ]
}}"""

    print(f"\n🌐  Launching SILENT Multi-Agent Deep Research for: {query}\n")
    agent_edu = Agent(task=edu_prompt, llm=llm, browser=browser, use_vision=False)
    agent_scrape = Agent(task=scrape_prompt, llm=llm, browser=browser, use_vision=False)
    
    try:
        results = await asyncio.gather(
            agent_edu.run(max_steps=15),
            agent_scrape.run(max_steps=20),
            return_exceptions=True
        )
        
        # Consolidate results
        edu_text = ""
        scrape_json = "{}"
        
        if results and len(results) >= 2:
            edu_raw = results[0]
            scrape_raw = results[1]
            
            # educator returns raw text
            if not isinstance(edu_raw, Exception):
                edu_text = getattr(edu_raw, 'final_result', lambda: str(edu_raw))()
            
            # scraper returns JSON string
            if not isinstance(scrape_raw, Exception):
                scrape_json = getattr(scrape_raw, 'final_result', lambda: "{}")()
            
            # Determine probability for context
            prob = 50
            if isinstance(market, dict):
                prob = market.get('probability', 50)

            # Final Synthesis
            synthesize_prompt = f"""You are a Betting Analysis Expert.
Combine the following research into a final analysis for "{query}".

EDUCATIONAL CONTEXT (for beginners):
{edu_text}

NEWS AND ARTICLES (JSON):
{scrape_json}

CURRENT MARKET ODDS (Probability): {prob}%

YOUR TASK:
1. Synthesize a "summary" that explains the event simply (using the Educator's context) and analyzes current trends.
2. List prominent "factors" (bullet points) affecting the outcome.
3. Clean and return the list of 5 news articles.

RETURN ONLY A RAW JSON OBJECT:
{{
  "summary": "Full analysis here...",
  "factors": [
    {{"direction": "up|down|neutral", "title": "Factor title", "detail": "Detailed explanation"}},
    {{"direction": "up|down|neutral", "title": "Factor title", "detail": "Detailed explanation"}},
    {{"direction": "up|down|neutral", "title": "Factor title", "detail": "Detailed explanation"}}
  ],
  "news": [ ...at least 5 real news items... ],
  "sentiment": {{"bull": 50, "bear": 30, "neutral": 20}},
  "probabilityLabel": "Analysis Outcome",
  "signals": [{{ "label": "Social Trend", "type": "info" }}]
}}"""
            
            final_response = await llm.ainvoke(synthesize_prompt)
            return getattr(final_response, 'content', str(final_response))
        else:
            return json.dumps({"error": "Failed to gather multi-agent results"})
            
    except Exception as e:
        # If both agents failed, return a basic market summary instead of just erroring
        print(f"❌ Error in multi-agent research: {str(e)}")
        fallback = {
            "summary": f"Polymarket data for {query} is available, but deep web research encountered a technical issue. Implied probability: {market.get('probability', 50)}%.",
            "factors": [], "news": [],
            "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
            "probabilityLabel": "Market Data Only"
        }
        return json.dumps(fallback)

# ── Step 3: Gemini summarization ──────────────────────────────────────────────
def gemini_summarize(query: str, market: dict, related: list[dict], web_snippets: str, as_json: bool = False) -> str:
    """Call Gemini REST API and return a structured analyst summary."""
    if not GOOGLE_API_KEY:
        return json.dumps({"error": "GOOGLE_API_KEY not set"}) if as_json else "[GOOGLE_API_KEY not set]"

    import urllib.request

    prob = 50
    if isinstance(market, dict):
        prob = market.get('probability', 50)

    if as_json:
        prompt = f"""You are a sharp Polymarket prediction market analyst.
REAL GAMMA API DATA: {json.dumps(market)}
RELATED MARKETS: {json.dumps(related)}
WEB RESEARCH SNIPPETS: {web_snippets[:3000]}
USER QUERY: "{query}"

Return ONLY a valid JSON object (no markdown) with these exact fields:
{{
  "probabilityLabel": "e.g. Moderate-high probability",
  "summary": "2-3 sentence sharp analyst commentary grounded in real context.",
  "signals": [{{ "label": "...", "type": "bull|bear|neutral|watch|info" }}, ...],
  "factors": [{{ "direction": "up|down|neutral", "title": "...", "detail": "..." }}, ...],
  "news": [{{ "source": "...", "age": "...", "headline": "...", "snippet": "...", "sentiment": "positive|neutral|negative" }}, ...],
  "sentiment": {{ "bull": 50, "bear": 30, "neutral": 20 }},
  "chartData": [13 numbers showing realistic 30-day trend ending at {prob}]
}}"""
    else:
        prompt = f"""You are a sharp Polymarket prediction market analyst.
REAL GAMMA API DATA: {json.dumps(market, indent=2)}
RELATED MARKETS: {json.dumps(related, indent=2)}
WEB RESEARCH SNIPPETS: {web_snippets[:3000]}
USER QUERY: "{query}"

Write a structured analyst brief (plain text, no JSON) that includes:
1. Market snapshot: current probability, 24h delta, volume, liquidity
2. Thesis: 2-3 sentences on what is driving the market
3. Bull case: key factors pushing probability higher
4. Bear case: key factors pushing probability lower
5. Related markets worth watching
6. Bottom line: one sentence verdict"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4000},
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    
    def do_call():
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            if "429" in str(e): return "429"
            raise e

    try:
        text = do_call()
        if text == "429":
            import time
            time.sleep(6)
            text = do_call()

        if text == "429":
            return json.dumps({"error": "Gemini rate limit hit"}) if as_json else "[Gemini rate limit hit]"

        if as_json:
            # Robust JSON extraction: Find first { and last }
            clean = text.replace("```json", "").replace("```", "").strip()
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1:
                return clean[start:end+1]
            return clean
        return text
    except Exception as e:
        return json.dumps({"error": str(e)}) if as_json else f"[Gemini error: {e}]"


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("--json", action="store_true", help="Output as JSON for UI")
    parser.add_argument("--deep", action="store_true", help="Run browser-use research")
    args = parser.parse_args()

    if not args.query:
        print("Usage: python polymarket_agent.py \"<query>\" [--json] [--deep]")
        sys.exit(1)

    query = " ".join(args.query)
    as_json = args.json

    if not as_json:
        print(f"\n{'='*60}")
        print(f"  Polymarket Research Agent")
        print(f"  Query: {query}")
        print(f"{'='*60}\n")

    # 1. Gamma API & Validation
    if not as_json: print("📡  Validating against Polymarket API…")
    market, related, is_valid = fetch_gamma(query)
    
    if not is_valid:
        if as_json:
            print(json.dumps({
                "validationError": f"The query '{query}' does not match any current Polymarket event. Please try a more specific topic.",
                "market": market,
                "relatedMarkets": []
            }))
            return
        else:
            print(f"❌  Validation Error: '{query}' not found in active markets.")
            sys.exit(0)

    # Ensure they are valid dict/list even if None (redundant but safe)
    if not isinstance(market, dict): market = {"title": query, "probability": 50}
    if not isinstance(related, list): related = []

    if not as_json:
        if market.get("title"):
            print(f"\n✅  BEST MATCH: {market['title']}")
            print(f"   Probability : {market['probability']}%")
            print(f"   24h Change  : {market['delta24h']} ({market['direction']})")
        else:
            print("⚠️  No Gamma match found — proceeding with web research only.")

    # 2. Research Phase
    summary = ""
    if args.deep:
        # CONSOLIDATED DEEP CALL: browsing + summarization in one go
        summary = await browser_research(query, market, related)
    else:
        # STANDARD FAST CALL: Use existing Gemini summarizer (one call only)
        if not as_json: print("✦  Synthesising with Gemini (fast scan)…")
        summary = gemini_summarize(query, market, related, "", as_json=as_json)
    
    if as_json:
        try:
            out = json.loads(summary)
            if "error" in out:
                # Fallback if AI reached rate limit
                out["market"] = market if market else {"title": query, "probability": 50}
                out["relatedMarkets"] = related
                out["summary"] = f"Polymarket data found for {query}, but AI research/synthesis was limited. Probability: {out['market'].get('probability', 50)}%."
            else:
                out["market"] = market
                out["relatedMarkets"] = related
                # If the agent returned nested JSON, out["summary"] might already be a string,
                # but we need to ensure it didn't just dump the JSON string into the summary field.
                if "summary" not in out:
                    out["summary"] = "AI Analysis completed."
            print(json.dumps(out))
        except Exception as e:
            fallback = {
                "market": market if market else {"title": query, "probability": 50},
                "relatedMarkets": related,
                "summary": f"Research for {query}. AI enrichment currently unavailable (Error: {str(e)}).",
                "probabilityLabel": "Data Sourced from Gamma",
                "signals": [], "factors": [], "news": [],
                "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
                "chartData": [50]*13
            }
            print(json.dumps(fallback))
    else:
        print(f"\n{'─'*60}\nANALYST BRIEF\n{'─'*60}\n{summary}\n{'─'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
