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

# Suppress browser_use logs from polluting standard output used for JSON
os.environ["BROWSER_USE_LOGGING_LEVEL"] = "error"
os.environ["ANONYMIZED_TELEMETRY"] = "false"


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
        "isMulti": is_multi,
        "eventId": event.get("id")
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


# ── Step 2: Fetch Comments ────────────────────────────────────────────────────
def fetch_comments(event_id: str | int) -> list[str]:
    """Fetch recent comments for the event."""
    if not event_id: return []
    params = urlencode({
        "parent_entity_id": str(event_id),
        "parent_entity_type": "Event",
        "limit": "20",
        "order": "createdAt",
        "ascending": "false"
    })
    try:
        data = gamma_get(f"/comments?{params}")
        if isinstance(data, list):
            return [c.get("content", "") for c in data if c.get("content")]
        return []
    except Exception as e:
        sys.stderr.write(f"[Comments API error] {e}\n")
        return []


# ── Step 3: browser-use web research (Consolidated Call) ─────────────────────
async def browser_research(query: str, market: dict, related: list[dict]) -> str:
    """
    Use browser-use + Gemini to find recent web content and generate the ANALYST BRIEF in one go.
    This saves 50% on LLM calls to avoid 429 limits.
    """
    try:
        from browser_use import Agent, Browser
        from browser_use.browser.browser import BrowserConfig
        # from browser_use.browser.session import BrowserSession as Browser # Alternative if needed
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

    # Configure browser to be truly headless (no tabs popping up) and disable images for speed
    browser = Browser(config=BrowserConfig(
        headless=True,
        extra_chromium_args=['--blink-settings=imagesEnabled=false']
    ))

    unified_prompt = f"""You are a research agent. Your ONLY goal is to find 5 real news articles about "{query}".

STEPS (do them fast):
1. Go to https://news.google.com/search?q={query.replace(' ', '+')}&hl=en-US
2. For each of the top 5 article links on the page: click the link, wait for it to load, then copy the full browser URL (not a google.com URL).
3. Also note: the article title, publication source name, and a 1-sentence summary.

OUTPUT: Return ONLY this raw JSON with no markdown:
{{
  "briefing": "2-paragraph summary of the current state of {query} based on what you found.",
  "intel": "Key facts: key players, standings, injuries, or relevant stats.",
  "news": [
    {{"source": "ESPN", "age": "2h ago", "headline": "Exact Article Title", "snippet": "One-sentence summary.", "sentiment": "neutral", "url": "https://espn.com/article-actual-url"}},
    {{"source": "Reuters", "age": "5h ago", "headline": "Exact Article Title", "snippet": "One-sentence summary.", "sentiment": "neutral", "url": "https://reuters.com/article-actual-url"}},
    {{"source": "BBC", "age": "1d ago", "headline": "Exact Article Title", "snippet": "One-sentence summary.", "sentiment": "neutral", "url": "https://bbc.com/article-actual-url"}},
    {{"source": "AP News", "age": "2d ago", "headline": "Exact Article Title", "snippet": "One-sentence summary.", "sentiment": "neutral", "url": "https://apnews.com/article-actual-url"}},
    {{"source": "Source", "age": "3d ago", "headline": "Exact Article Title", "snippet": "One-sentence summary.", "sentiment": "neutral", "url": "https://full-article-url-here.com"}}
  ]
}}

CRITICAL: The url field MUST be the direct article URL (starting with https://), NOT a google.com URL."""

    sys.stderr.write(f"\n🌐  Launching SILENT Multi-Agent Deep Research for: {query}\n")
    
    # NEW: Fetch comments from Gamma
    event_id = market.get("eventId")
    comments_list: list[str] = fetch_comments(event_id) if event_id else []
    comments_block = "\n".join([f"- {c}" for c in comments_list[:10]]) if comments_list else "No recent community comments found."

    agent = Agent(task=unified_prompt, llm=llm, browser=browser, use_vision=False)
    
    try:
        history = await agent.run(max_steps=8)
        raw_result = history.final_result() or "{}"
        
        # Clean potential markdown
        cleaned_json = raw_result.replace("```json", "").replace("```", "").strip()
        data = {}
        try:
            data = json.loads(cleaned_json)
        except:
            data = {"briefing": cleaned_json, "intel": "Data extraction failed", "news": []}

        from typing import cast, Any
        _data: dict[str, Any] = data if isinstance(data, dict) else {}
        edu_text: str = str(_data.get("briefing", "No briefing found."))
        news_list: list[dict] = list(_data.get("news", []))
        scraped_intel: str = str(_data.get("intel", ""))

        # Determine probability for context
        prob = 50
        if isinstance(market, dict):
            prob = market.get('probability', 50)

        # ── OPTIMIZED SYNTHESIS ───────────────────────────────────────────────
        # The browser already gave us real, fast news citations — pass them
        # straight through. The LLM only needs to write the analysis (summary,
        # report, factors) using those articles as its source, which is far
        # faster than asking it to re-invent news it already has.
        news_for_prompt = json.dumps(list(news_list)[:5])  # feed scraped articles in
        synthesize_prompt = f"""You are a Professional Market Analyst & Intelligence Officer.
YOUR GOAL: Write a concise but high-quality intelligence briefing for "{query}" using the research below.

SOURCE BRIEFING:
{edu_text}

SCRAPED INTEL:
{scraped_intel}

VERIFIED NEWS ARTICLES (already sourced — do NOT fabricate new ones):
{news_for_prompt}

POLYMARKET COMMUNITY DISCUSSION:
{comments_block}

CURRENT MARKET ODDS: {prob}%

YOUR TASK — return ONLY this raw JSON (no markdown fences):
{{
  "summary": "2-3 paragraph betting thesis synthesising all the above.",
  "report": "Structured intelligence dossier with Markdown headers:\\n# CURRENT STATUS\\n...\\n# COMMUNITY PULSE\\n...\\n# MARKET VERDICT\\n...",
  "factors": [
    {{"direction": "up|down|neutral", "title": "...", "detail": "..."}}
  ],
  "sentiment": {{"bull": 50, "bear": 30, "neutral": 20}},
  "probabilityLabel": "Short market verdict label",
  "signals": [{{"label": "...", "type": "warning|info|success"}}]
}}

CRITICAL: The "report" field must be thorough (300+ words). Use bolding and bullet lists."""

        final_response = await llm.ainvoke(synthesize_prompt)
        raw_analysis = getattr(final_response, 'content', str(final_response))

        # ── Merge: inject the real scraped news into the LLM's analysis ──────
        analysis: dict[str, Any]
        try:
            parsed = json.loads(
                raw_analysis.replace("```json", "").replace("```", "").strip()
            )
            analysis = parsed if isinstance(parsed, dict) else {}
        except Exception:
            analysis = {
                "summary": raw_analysis,
                "report": "Report parsing failed — see summary.",
                "factors": [],
                "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
                "probabilityLabel": "Analysis Available",
                "signals": []
            }

        # Always use the browser's real citations — never the LLM's guesses
        analysis["news"] = news_list
        return json.dumps(analysis)
            
    except Exception as e:
        # Generate a high-quality fallback
        print(f"❌ Error in deep research: {str(e)}", file=sys.stderr)
        fallback = {
            "summary": f"Polymarket data for {query} is available, but deep research encountered an issue. Implied probability: {market.get('probability', 50)}%.",
            "report": "Intelligence report unavailable due to a technical error. Please try again later.",
            "factors": [], 
            "news": [],
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
  "probabilityLabel": "Market Verdict",
  "summary": "Quick high-level snippet.",
  "report": "Brief data-driven report mentioning current context and trends.",
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
            print("---JSON_START---")
            print(json.dumps({
                "validationError": f"The query '{query}' does not match any current Polymarket event. Please try a more specific topic.",
                "market": market,
                "relatedMarkets": []
            }))
            print("---JSON_END---")
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
            print("---JSON_START---")
            print(json.dumps(out))
            print("---JSON_END---")
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
            print("---JSON_START---")
            print(json.dumps(fallback))
            print("---JSON_END---")
    else:
        print(f"\n{'─'*60}\nANALYST BRIEF\n{'─'*60}\n{summary}\n{'─'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
