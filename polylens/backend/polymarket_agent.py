<<<<<<< HEAD
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
=======
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# ── Load .env from root folder ─────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
>>>>>>> 8eaa068 (mvp version1 complete)
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
<<<<<<< HEAD
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
        # from browser_use.browser.session import BrowserSession as Browser # Alternative if needed
=======
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-flash-latest"
GEMINI_BROWSER_MODEL = "gemini-flash-latest"

# ── Step 1: Fetch from Gamma API ─────────────────────────────────────────────
def fetch_gamma(query: str):
    """Search Gamma API for the most relevant active market."""
    import urllib.request
    from urllib.parse import quote
    
    encoded = quote(query)
    url = f"https://gamma-api.polymarket.com/events?q={encoded}&active=true&closed=false&limit=20&order=volume&ascending=false"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            events = json.loads(resp.read())
            if not events: return None, [], False
            
            # ── Helper for dollar formatting ──
            def fmt_dollars(n):
                val = float(n) if n else 0
                if val >= 1e6: return f"${val/1e6:.1f}M"
                if val >= 1e3: return f"${val/1e3:.0f}K"
                return f"${val:.0f}"

            # ── Market Data Extraction Helper ──
            def extract_data(event):
                markets = event.get("markets", [])
                if not markets: return None
                
                # Check for grouped sub-markets
                is_grouped = len(markets) > 2 and all("groupItemTitle" in m or "question" in m for m in markets[:5])
                
                if is_grouped:
                    candidates = []
                    for m in markets:
                        prices = json.loads(m.get("outcomePrices", "[0, 0]"))
                        label = m.get("groupItemTitle") or m.get("question") or "Unknown"
                        price = float(prices[0]) if prices else 0
                        candidates.append({"label": label, "price": price})
                    candidates.sort(key=lambda x: x["price"], reverse=True)
                    
                    return {
                        "id": event.get("id"),
                        "eventId": event.get("id"),
                        "title": event.get("title"),
                        "slug": event.get("slug"),
                        "probability": round(candidates[0]["price"] * 100) if candidates else 50,
                        "delta24h": "+0.0%",
                        "deltaDirection": "neutral",
                        "volume": fmt_dollars(event.get("volumeNum", 0)),
                        "liquidity": fmt_dollars(event.get("liquidityNum", 0)),
                        "outcomes": [c["label"] for c in candidates],
                        "outcomePrices": [c["price"] for c in candidates],
                        "clobTokenIds": [],
                        "isMulti": True
                    }
                
                # Standard market
                m = markets[0]
                prices = json.loads(m.get("outcomePrices", "[0.5, 0.5]"))
                outcomes = json.loads(m.get("outcomes", '["Yes", "No"]'))
                raw_delta = float(m.get("oneDayPriceChange", 0))
                
                return {
                    "id": m.get("id"),
                    "eventId": event.get("id"),
                    "title": event.get("title"),
                    "slug": event.get("slug"),
                    "probability": round(float(prices[0])*100),
                    "delta24h": (f"+{raw_delta*100:.1f}%" if raw_delta >= 0 else f"{raw_delta*100:.1f}%"),
                    "deltaDirection": "up" if raw_delta > 0.002 else "down" if raw_delta < -0.002 else "neutral",
                    "volume": fmt_dollars(event.get("volumeNum", 0)),
                    "liquidity": fmt_dollars(event.get("liquidityNum", 0)),
                    "outcomes": outcomes,
                    "outcomePrices": [float(p) for p in prices],
                    "clobTokenIds": json.loads(m.get("clobTokenIds", "[]")),
                    "isMulti": len(outcomes) > 2
                }

            # Simple scoring for relevance
            lq = query.lower()
            scored = []
            for e in events:
                title = e.get("title", "").lower()
                score = sum(2 for w in lq.split() if len(w) > 2 and w in title)
                # Volume bonus
                score += (float(e.get("volumeNum", 0)) / 1_000_000)
                scored.append((score, e))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            top_event = scored[0][1]
            
            market_data = extract_data(top_event)
            if not market_data: return None, [], False
            
            # Extract related markets (top 10 after the main one)
            related_markets = []
            num_scored = len(scored)
            if num_scored > 1:
                # Use enumerate to avoid explicit counter addition which confuses some linters
                for i, item in enumerate(scored):
                    if i == 0: continue # Skip main market
                    if i > 11: break # Max 10 related
                    e = item[1]
                    rd = extract_data(e)
                    if rd: 
                        related_markets.append(rd)
                
            return market_data, related_markets, True
    except Exception as e:
        print(f"Gamma Error: {e}")
        return None, [], False

# ── Step 2: Fetch Comments ──────────────────────────────────────────────────
def fetch_comments(event_id: str):
    """Fetch recent community comments for a given event ID."""
    import urllib.request
    url = f"https://gamma-api.polymarket.com/comments?eventId={event_id}&limit=20"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return [c.get("comment", "") for c in data if c.get("comment")]
    except:
        return []

# ── Step 3: browser-use web research (Consolidated Call) ─────────────────────
async def browser_research(query: str, market: dict, related: list[dict], as_json: bool = False) -> str:
    """
    Use browser-use + Gemini to find recent web content and generate the ANALYST BRIEF in one go.
    """
    try:
        from browser_use import Agent, Browser
>>>>>>> 8eaa068 (mvp version1 complete)
    except ImportError as e:
        return json.dumps({"error": f"browser-use not available: {e}"})

    if not GOOGLE_API_KEY:
        return json.dumps({"error": "GOOGLE_API_KEY missing"})

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
<<<<<<< HEAD
        
        # Transparent Proxy to bypass Pydantic monkeypatching issues
=======
>>>>>>> 8eaa068 (mvp version1 complete)
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
<<<<<<< HEAD
                return await self._llm.ainvoke(*args, **kwargs)
            def invoke(self, *args, **kwargs):
                return self._llm.invoke(*args, **kwargs)
            
=======
                res = await self._llm.ainvoke(*args, **kwargs)
                # Ensure usage data exists for browser-use (OpenAI-style keys for Pydantic validation)
                u = {
                    'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                    'prompt_cached_tokens': 0, 'prompt_cache_creation_tokens': 0, 'prompt_image_tokens': 0
                }
                if not hasattr(res, 'usage_metadata'): setattr(res, 'usage_metadata', u)
                if not hasattr(res, 'usage'): setattr(res, 'usage', u)
                return res
            def invoke(self, *args, **kwargs):
                res = self._llm.invoke(*args, **kwargs)
                u = {
                    'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                    'prompt_cached_tokens': 0, 'prompt_cache_creation_tokens': 0, 'prompt_image_tokens': 0
                }
                if not hasattr(res, 'usage_metadata'): setattr(res, 'usage_metadata', u)
                if not hasattr(res, 'usage'): setattr(res, 'usage', u)
                return res
>>>>>>> 8eaa068 (mvp version1 complete)
        llm = TransparentProxy(model=GEMINI_BROWSER_MODEL, api_key=GOOGLE_API_KEY)
    except ImportError:
        return json.dumps({"error": "langchain-google-genai not installed"})

<<<<<<< HEAD
    # Configure browser to be truly headless (no tabs popping up)
    # Configure browser - in 0.12.2 Browser defaults to headless or can be configured via Agent
=======
>>>>>>> 8eaa068 (mvp version1 complete)
    browser = Browser()

    unified_prompt = f"""You are a Master Betting Intelligence Agent.
YOUR GOAL: Provide a deeply informative and contextual briefing for "{query}".

<<<<<<< HEAD
1. WEB RESEARCH: Go to google.com and search for "{query} latest injuries standings news statistics".
2. EXTRACTION: Find and extract:
   - COMPREHENSIVE CONTEXT: Explain the league, event, or topic status. If sports, get records, seeds, and season storylines.
   - PERSONNEL INTEL: List key figures (players/coaches/leaders) and their current status (injuries, form, scandals).
   - RECENT NEWS: Find 5 high-quality news articles with titles, snippets, source names, and URLs.
3. OUTPUT: Return ONLY a RAW JSON object. Be extremely detailed in the briefing and intel fields.
{{
  "briefing": "A long, detailed educational context about the terminology and entities (3-4 paragraphs).",
  "intel": "A comprehensive list of facts found: Detailed injury reports, team stats, recent game results, or political poll data.",
  "news": [
    {{"source": "Actual Site Name", "age": "e.g. 2 hours ago", "headline": "Real headline", "snippet": "Detailed snippet of the article content.", "sentiment": "bull|bear|neutral", "url": "https://url.com"}},
    ...
  ]
}}"""

    print(f"\n🌐  Launching SILENT Multi-Agent Deep Research for: {query}\n")
    
    # NEW: Fetch comments from Gamma
    event_id = market.get("eventId")
    comments_list = fetch_comments(event_id) if event_id else []
    comments_block = "\n".join([f"- {c}" for c in comments_list[:10]]) if comments_list else "No recent community comments found."
=======
1. WEB RESEARCH: 
   - Search for "{query} latest news status standings facts".
   - Search for "{query} recent results and performance data".
   - Search for "{query} betting markets and experts opinion".
   - CRITICAL: For each result, CLICK on the article link to navigate to the actual page, then capture the full URL from the browser address bar.
2. EXTRACTION: Find and extract:
   - COMPREHENSIVE CONTEXT: Detailed stats, current rankings, recent win/loss streaks, and historical context.
   - PERSONNEL & PHYSICALS: Specific injury reports, player availability, coaching changes, or team news.
   - REAL NEWS ARTICLES: Find at least 5-8 HIGH-QUALITY news articles. For EACH article:
     * CLICK the link to open the page
     * Copy the EXACT URL from the address bar (must start with https://)
     * Capture: Source name, Timestamp, Headline, 3-4 sentence snippet
3. OUTPUT: Return ONLY a RAW JSON object. DO NOT include markdown formatting like ```json.
{{
  "briefing": "Extremely detailed educational context. Explain the entities involved, the history, and the current stakes (at least 350 words).",
  "intel": "A massive bulleted list of raw facts: Injury lists with specifics, recent scorelines, head-to-head records, and statistical advantages.",
  "news": [
    {{"source": "ESPN", "age": "2 hours ago", "headline": "Exact Headline Here", "snippet": "Detailed snippet...", "sentiment": "bull|bear|neutral", "url": "https://espn.com/exact/article/url"}},
    ...
  ]
}}
IMPORTANT: The url field MUST be the direct article URL, not a search result URL or google.com link."""

    if not as_json:
        print(f"\n🌐  Launching HEAVY-DUTY Deep Research for: {query}\n")
    
    # Silence browser-use logs if json output requested
    import logging
    if as_json:
        logging.getLogger('browser_use').setLevel(logging.WARNING)
    
    event_id = market.get("eventId")
    comments_list = fetch_comments(event_id) if event_id else []
    num_comments = len(comments_list)
    top_comments = []
    for i in range(min(num_comments, 15)):
        top_comments.append(f"- {comments_list[i]}")
    comments_block = "\n".join(top_comments) if top_comments else "No recent community comments found."
>>>>>>> 8eaa068 (mvp version1 complete)

    agent = Agent(task=unified_prompt, llm=llm, browser=browser, use_vision=False)
    
    try:
<<<<<<< HEAD
        history = await agent.run(max_steps=15)
        raw_result = history.final_result() or "{}"
        
        # Clean potential markdown
=======
        history = await agent.run(max_steps=20)
        raw_result = history.final_result() or "{}"
        
>>>>>>> 8eaa068 (mvp version1 complete)
        cleaned_json = raw_result.replace("```json", "").replace("```", "").strip()
        data = {}
        try:
            data = json.loads(cleaned_json)
        except:
<<<<<<< HEAD
            data = {"briefing": cleaned_json, "intel": "Data extraction failed", "news": []}
=======
            import re
            match = re.search(r'(\{.*\})', cleaned_json, re.DOTALL)
            if match:
                try: data = json.loads(match.group(1))
                except: data = {}
            else:
                data = {"briefing": cleaned_json, "intel": "Data extraction failed", "news": []}
>>>>>>> 8eaa068 (mvp version1 complete)

        edu_text = data.get("briefing", "No briefing found.")
        news_list = data.get("news", [])
        scraped_intel = data.get("intel", "")
<<<<<<< HEAD

        # Determine probability for context
        prob = 50
        if isinstance(market, dict):
            prob = market.get('probability', 50)

        # Final Synthesis
        synthesize_prompt = f"""You are a Professional Market Analyst & Intelligence Officer.
YOUR GOAL: Produce a high-stakes, comprehensive intelligence briefing for "{query}".

CONTEXTUAL INTEL:
{edu_text}

WEBSITE SCRAPED INTEL:
{scraped_intel}

RECENT NEWS ARTICLES:
{json.dumps(news_list)}

POLYMARKET COMMUNITY DISCUSSION:
{comments_block}

CURRENT MARKET ODDS (Probability): {prob}%

YOUR TASK:
1. Write a "summary": 2-3 compelling paragraphs that synthesize the research into a coherent betting thesis.
2. Write a "report": A professional-grade, structured intelligence dossier using Markdown headers.
   - Use # for main sections and ## for sub-sections.
   - SECTIONS REQUIRED:
     # CURRENT STATUS
     (Detail the standings, rankings, and major league/event storylines)
     # PERSONNEL & INJURIES
     (Provide a deep dive into key figures and their physical/mental status)
     # COMMUNITY PULSE
     (Analyze the community comments provided above. What is the sentiment? Are there contrarian views?)
     # MARKET VERDICT
     (Detailed analysis of why the odds are what they are and what shifts they may take)
3. List 4 high-impact "factors" (bullet points).
4. Return a "news" array with 5 real news items.

CRITICAL: The "report" must be extremely detailed (at least 500 words). Use bolding and lists for readability.

RETURN ONLY A RAW JSON OBJECT:
{{
  "summary": "Full summary text...",
  "report": "Full dossier text...",
  "factors": [ ... ],
  "news": [ ... ],
  "sentiment": {{"bull": x, "bear": y, "neutral": z}},
  "probabilityLabel": "Market Label",
=======
        prob = market.get('probability', 50)

        synthesize_prompt = f"""You are a Lead Quant & Betting Strategist.
YOUR GOAL: Produce a professional-grade, high-conviction intelligence dossier for "{query}".

RAW INTEL GATHERED:
{edu_text}

FACTUAL EVIDENCE:
{scraped_intel}

REAL-TIME NEWS SOURCES:
{json.dumps(news_list)}

COMMUNITY SENTIMENT (Direct from Polymarket):
{comments_block}

MARKET ODDS: {prob}%

YOUR MISSION:
Whip up a comprehensive, well-formatted analyst report.

1. "summary": 2 paragraphs of sharp, high-level analysis.
2. "report": A MASSIVE, structured intelligence BRIEFING (Markdown).
   - Use # for headers and ## for subheaders.
   - Use specific details from the "FACTUAL EVIDENCE" and "NEWS SOURCES" above. Mention players, scores, and dates.
   - REQUIRED SECTIONS:
     # EXECUTIVE SUMMARY
     # PERSONNEL & TEAM HEALTH (Deep dive into injuries)
     # STANDINGS & STATISTICAL TRENDS
     # COMMUNITY ATTITUDE (Analyze the comments provided)
     # ANALYST VERDICT (Final recommendation)
3. "factors": 4 keys to the game with directions and detail.
4. "news": The news articles provided above.

RETURN ONLY A RAW JSON OBJECT:
{{
  "summary": "...",
  "report": "...",
  "factors": [ ... ],
  "news": [ ... ],
  "sentiment": {{"bull": x, "bear": y, "neutral": z}},
  "probabilityLabel": "Strategic Verdict",
>>>>>>> 8eaa068 (mvp version1 complete)
  "signals": [{{ "label": "Label", "type": "warning|info|success" }}]
}}"""
        
        final_response = await llm.ainvoke(synthesize_prompt)
<<<<<<< HEAD
        # Ensure the response is returned as a string (it's already a JSON string from the LLM usually)
        return getattr(final_response, 'content', str(final_response))
            
    except Exception as e:
        # Generate a high-quality fallback
        print(f"❌ Error in deep research: {str(e)}")
        fallback = {
            "summary": f"Polymarket data for {query} is available, but deep research encountered an issue. Implied probability: {market.get('probability', 50)}%.",
            "report": "Intelligence report unavailable due to a technical error. Please try again later.",
            "factors": [], 
            "news": [],
=======
        raw_content = getattr(final_response, 'content', '')
        # LangChain+Gemini may return a list of content parts
        if isinstance(raw_content, list):
            parts = []
            for part in raw_content:
                if isinstance(part, dict) and 'text' in part:
                    parts.append(part['text'])
                elif isinstance(part, str):
                    parts.append(part)
            final_response_text = '\n'.join(parts)
        else:
            final_response_text = str(raw_content)
        
        # Robust JSON extraction
        cleaned = final_response_text.replace('```json', '').replace('```', '').strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        json_str = cleaned[start:end+1] if start != -1 and end != -1 else '{}'
        
        try:
            final_data = json.loads(json_str)
            if not final_data.get("news"):
                final_data["news"] = news_list
            return json.dumps(final_data)
        except Exception as parse_err:
            print(f"⚠️ JSON parse failed ({parse_err}), returning text fallback")
            # Return the text directly in a valid JSON container
            fallback = {
                "summary": final_response_text[:500] if final_response_text else "Analysis unavailable.",
                "report": final_response_text,
                "factors": [], "news": news_list,
                "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
                "probabilityLabel": "Deep Research"
            }
            return json.dumps(fallback)
            
    except Exception as e:
        print(f"❌ Error in deep research: {str(e)}")
        fallback = {
            "summary": f"Deep research encountered an issue for {query}. Implied probability: {market.get('probability', 50)}%.",
            "report": "Intelligence report unavailable due to a technical error. Please try again later.",
            "factors": [], "news": [],
>>>>>>> 8eaa068 (mvp version1 complete)
            "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
            "probabilityLabel": "Market Data Only"
        }
        return json.dumps(fallback)

<<<<<<< HEAD
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


=======
>>>>>>> 8eaa068 (mvp version1 complete)
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

<<<<<<< HEAD
    if not as_json:
        print(f"\n{'='*60}")
        print(f"  Polymarket Research Agent")
        print(f"  Query: {query}")
        print(f"{'='*60}\n")

    # 1. Gamma API & Validation
    if not as_json: print("📡  Validating against Polymarket API…")
=======
>>>>>>> 8eaa068 (mvp version1 complete)
    market, related, is_valid = fetch_gamma(query)
    
    if not is_valid:
        if as_json:
<<<<<<< HEAD
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
=======
            print(json.dumps({"validationError": f"The query '{query}' not found.", "market": market, "relatedMarkets": []}))
            return
        else:
            print(f"❌ '{query}' not found.")
            sys.exit(0)

    if not isinstance(market, dict): market = {"title": query, "probability": 50}
    if not isinstance(related, list): related = []

    summary = ""
    if args.deep:
        summary = await browser_research(query, market, related, as_json)
    else:
        # Fallback to simple summary if not deep
        summary = json.dumps({
            "summary": "Deep Research required for full analysis.",
            "report": "Intelligence report available via Deep Research.",
            "factors": [], "news": [],
            "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
            "probabilityLabel": "Fast Scan"
        })
>>>>>>> 8eaa068 (mvp version1 complete)
    
    if as_json:
        try:
            out = json.loads(summary)
<<<<<<< HEAD
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

=======
            out["market"] = market
            out["relatedMarkets"] = related
            print(f"---JSON_START---{json.dumps(out)}---JSON_END---")
        except:
            print(f"---JSON_START---{summary}---JSON_END---")
    else:
        print(summary)
>>>>>>> 8eaa068 (mvp version1 complete)

if __name__ == "__main__":
    asyncio.run(main())
