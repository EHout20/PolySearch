import { NextResponse } from 'next/server';

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtDollars(n: any): string {
  const val = parseFloat(n) || 0;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val.toFixed(0)}`;
}

function extractGammaMarket(event: any) {
  const markets = event.markets || [];
  
  // Detect grouped multi-outcome events
  const isGrouped = markets.length > 2 && markets.every((m: any) => {
    const o = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : m.outcomes;
    return o?.length === 2;
  });

  if (isGrouped) {
    const candidates = markets
      .map((m: any) => {
        const prices = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : (m.outcomePrices || [0, 0]);
        const p = Array.isArray(prices) ? prices : [0, 0];
        return { label: m.groupItemTitle || m.question, price: parseFloat(p[0]) || 0 };
      })
      .sort((a: any, b: any) => b.price - a.price);
    const topP = Math.round((candidates[0]?.price || 0) * 100);
    return {
      id: event.id,
      eventId: event.id,
      title: event.title || event.slug,
      slug: event.slug || '',
      probability: topP,
      probabilityLabel: candidates[0] ? `Leading: ${candidates[0].label}` : 'Market Odds',
      delta24h: '+0.0%', 
      deltaDirection: 'neutral' as const,
      volume: fmtDollars(event.volumeNum || event.volume),
      liquidity: fmtDollars(event.liquidityNum || event.liquidity),
      outcomes: candidates.map((c: any) => c.label),
      outcomePrices: candidates.map((c: any) => c.price),
      description: event.description || '',
      isMulti: true,
      clobTokenIds: []
    };
  }

  const m = markets[0] || {};
  let prices: number[] = [0.5, 0.5];
  try {
    const raw = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : m.outcomePrices;
    prices = Array.isArray(raw) ? raw.map((p: any) => parseFloat(p) || 0) : [0.5, 0.5];
  } catch (_) {}

  let yesPrice = prices[0];
  if (yesPrice < 0.005) yesPrice = parseFloat(m.lastTradePrice || m.bestAsk || '0') || yesPrice;

  const outcomes = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : (m.outcomes || ['Yes', 'No']);
  const rawDelta = parseFloat(m.oneDayPriceChange || '0');

  let clobTokenIds: string[] = [];
  try {
    const raw = typeof m.clobTokenIds === 'string' ? JSON.parse(m.clobTokenIds) : m.clobTokenIds;
    clobTokenIds = Array.isArray(raw) ? raw : [];
  } catch (_) {}

  return {
    id: m.id,
    eventId: event.id,
    title: event.title || event.slug,
    slug: event.slug || '',
    probability: Math.max(1, Math.round(yesPrice * 100)),
    probabilityLabel: outcomes.length > 2 ? `Leading: ${outcomes[0]}` : 'Implied probability',
    delta24h: (rawDelta >= 0 ? '+' : '') + (rawDelta * 100).toFixed(1) + '%',
    deltaDirection: (rawDelta > 0.002 ? 'up' : rawDelta < -0.002 ? 'down' : 'neutral') as 'up' | 'down' | 'neutral',
    volume: fmtDollars(event.volumeNum || event.volume),
    liquidity: fmtDollars(event.liquidityNum || event.liquidity),
    outcomes,
    outcomePrices: prices,
    description: event.description || '',
    isMulti: outcomes.length > 2,
    clobTokenIds
  };
}

// ── Gemini Deep Synthesis (uses pre-fetched news as source) ─────────────────
async function getGeminiDeepSummary(
  market: any,
  query: string,
  news: any[]
): Promise<{ summary: string; report: string; factors: any[]; signals: any[]; sentiment: any }> {
  let apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
  }

  if (!apiKey) return {
    summary: 'AI summary unavailable (no API key configured).',
    report: '',
    factors: [],
    signals: [],
    sentiment: { bull: 50, bear: 30, neutral: 20 }
  };

  const prob = market?.probability ?? 50;
  const newsJson = JSON.stringify(news.slice(0, 8));

  const prompt = `You are a clear, direct financial journalist. Your job is to explain what's happening with "${query}" in plain English that anyone can understand — no jargon, no buzzwords, no corporate speak.

MARKET DATA:
- Market: ${market?.title || query}
- Current odds: ${prob}% chance of YES
- Volume traded: ${market?.volume || 'N/A'} | Liquidity: ${market?.liquidity || 'N/A'}

NEWS ARTICLES (use only these as your source — do not invent facts):
${newsJson}

TONE RULES:
- Write like a smart friend texting you what's happening, not a formal report
- Use short sentences. Get to the point fast.
- No phrases like "intelligence briefing", "dossier", "aforementioned", "it is worth noting"
- Use numbers and specifics where possible (e.g. "odds dropped from 60% to 45%", not "odds decreased significantly")

Return ONLY this raw JSON (no markdown fences, no code blocks):
{
  "summary": "3 short punchy sentences: what's happening right now, what's driving it, and what to watch. Written like a text message from a smart friend.",
  "report": "# What's going on\\n[2-3 sentences explaining the current situation in plain English]\\n\\n# Why the odds are here\\n[Explain what's pushing the probability up or down, using specific details from the news]\\n\\n# What could change this\\n[2-3 concrete things that could shift the market. Be specific.]\\n\\n# Bottom line\\n[One blunt sentence — is this likely to happen or not, and why?]",
  "factors": [
    {"direction": "up|down|neutral", "title": "Short factor name", "detail": "One plain-English sentence explaining why this matters."}
  ],
  "sentiment": {"bull": 50, "bear": 30, "neutral": 20},
  "signals": [{"label": "Short signal label", "type": "warning|info|success"}]
}

CRITICAL: Every sentence in summary and report must be something a non-expert would immediately understand.`;

  try {
    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.6, maxOutputTokens: 2048 }
        })
      }
    );
    const data = await resp.json();
    if (data.error) throw new Error(data.error.message || 'Gemini API Error');

    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
    const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    const start = cleaned.indexOf('{');
    const end = cleaned.lastIndexOf('}');
    const jsonStr = start !== -1 && end !== -1 ? cleaned.substring(start, end + 1) : '{}';

    let parsed: any = {};
    try { if (jsonStr !== '{}') parsed = JSON.parse(jsonStr); } catch (_) {}

    return {
      summary: parsed.summary || text,
      report: parsed.report || '',
      factors: parsed.factors || [],
      signals: parsed.signals || [],
      sentiment: parsed.sentiment || { bull: 50, bear: 30, neutral: 20 }
    };
  } catch (e) {
    console.error('Gemini deep error:', e);
    return {
      summary: 'AI analysis temporarily unavailable.',
      report: '',
      factors: [],
      signals: [],
      sentiment: { bull: 50, bear: 30, neutral: 20 }
    };
  }
}

// ── Gemini Summary ────────────────────────────────────────────────────────────
async function getGeminiSummary(market: any, query: string): Promise<{ summary: string; report: string; factors: any[] }> {
  let apiKey = process.env.GOOGLE_API_KEY;
  
  if (!apiKey) {
  }

  if (!apiKey) return { 
    summary: 'AI summary unavailable (no API key configured).', 
    report: '',
    factors: [] 
  };

  const outcomeInfo = market.isMulti
    ? `\nTop candidates: ${market.outcomes.slice(0, 5).map((o: string, i: number) => `${o} (${Math.round(market.outcomePrices[i] * 100)}%)`).join(', ')}`
    : `\nYes: ${market.probability}%, No: ${100 - market.probability}%`;

  const prompt = `You are a prediction market analyst. Analyze this Polymarket prediction market and provide a concise intelligence briefing.

Market: "${market.title}"
Query: "${query}"
Volume: ${market.volume} | Liquidity: ${market.liquidity}${outcomeInfo}

Respond with a JSON object (no markdown, pure JSON):
{
  "summary": "2-3 paragraph analysis of the key forces driving this market, what the odds reflect, and what traders should watch for",
  "factors": [
    {"title": "Factor name", "detail": "Brief explanation", "direction": "up|down|neutral"},
    {"title": "Factor name", "detail": "Brief explanation", "direction": "up|down|neutral"},
    {"title": "Factor name", "detail": "Brief explanation", "direction": "up|down|neutral"}
  ]
}`;

  try {
    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 1024 }
        })
      }
    );
    const data = await resp.json();
    if (data.error) throw new Error(data.error.message || 'Gemini API Error');
    
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
    // Robust parsing
    const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    const start = cleaned.indexOf('{');
    const end = cleaned.lastIndexOf('}');
    const jsonStr = start !== -1 && end !== -1 ? cleaned.substring(start, end + 1) : '{}';
    
    let parsed: any = {};
    try {
      if (jsonStr !== '{}') parsed = JSON.parse(jsonStr);
    } catch (err) {
      console.warn('Gemini JSON parse failed, falling back to raw text');
    }
    
    return { 
      summary: parsed.summary || text, 
      report: parsed.report || '',
      factors: parsed.factors || [] 
    };
  } catch (e) {
    console.error('Gemini error:', e);
    return { 
      summary: 'AI analysis temporarily unavailable.', 
      report: '',
      factors: [] 
    };
  }
}

// ── Google News RSS Fetcher (no API key required) ────────────────────────────
async function fetchGoogleNewsRss(query: string): Promise<any[]> {
  try {
    const rssUrl = `https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=en-US&gl=US&ceid=US:en`;
    const res = await fetch(rssUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(6000)
    });
    const xml = await res.text();
    // Parse items out of RSS XML without a library
    const itemMatches = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)];
    const news: any[] = [];
    for (const match of itemMatches.slice(0, 8)) {
      const block = match[1];
      const title = (block.match(/<title><!\[CDATA\[(.+?)\]\]><\/title>/) || block.match(/<title>(.+?)<\/title>/))?.[1]?.trim();
      const rawLink = (block.match(/<link>([^<]+)<\/link>/) || block.match(/<link\s*\/>\s*<([^>]+)>/))?.[1]?.trim();
      const pubDate = (block.match(/<pubDate>(.+?)<\/pubDate>/))?.[1]?.trim();
      const descRaw = (block.match(/<description><!\[CDATA\[([\s\S]*?)\]\]><\/description>/) || block.match(/<description>([\s\S]*?)<\/description>/))?.[1] || '';
      // Strip HTML tags from description
      const snippet = descRaw.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim().slice(0, 200);
      // Extract the real source from title (Google News format: "Headline - Source")
      const sourceSplit = title?.lastIndexOf(' - ');
      const headline = sourceSplit && sourceSplit > 0 ? title?.slice(0, sourceSplit) : title;
      const source = sourceSplit && sourceSplit > 0 ? title?.slice(sourceSplit + 3) : 'News';
      // Google News links are redirects — use them directly, they forward to the article
      const url = rawLink || '';
      // Parse age from pubDate
      let age = 'Recent';
      if (pubDate) {
        const diff = Date.now() - new Date(pubDate).getTime();
        const h = Math.floor(diff / 3.6e6);
        const d = Math.floor(diff / 8.64e7);
        age = h < 24 ? `${h}h ago` : `${d}d ago`;
      }
      if (headline && url) news.push({ source, age, headline, snippet, url, sentiment: 'neutral' });
    }
    return news;
  } catch (e) {
    console.warn('News RSS fetch failed:', e);
    return [];
  }
}

// ── Main Handler ─────────────────────────────────────────────────────────────
export async function POST(req: Request) {
  try {
    const { query, deep, ai = true, market: incomingMarket, news: incomingNews } = await req.json();
    if (!query?.trim()) return NextResponse.json({ error: 'Missing query' }, { status: 400 });

    if (deep) {
      // ── Deep Research: NO browser-use. Use the news already shown to the user.
      // The frontend sends the existing market + news so Gemini can write the report
      // from verified sources only. News is never re-fetched or overwritten.
      const market = incomingMarket || { title: query, probability: 50 };
      const news: any[] = Array.isArray(incomingNews) && incomingNews.length > 0
        ? incomingNews
        : [];

      const analysis = await getGeminiDeepSummary(market, query, news);

      return NextResponse.json({
        market,
        ...analysis,
        // Always echo back the SAME news the user was already seeing
        news,
      });
    }

    // Standard: fetch from Gamma API + Gemini
    const encoded = encodeURIComponent(query);
    const gammaRes = await fetch(
      `https://gamma-api.polymarket.com/events?q=${encoded}&active=true&closed=false&limit=20&order=volume&ascending=false`,
      { headers: { 'User-Agent': 'PolyLens/Next', Accept: 'application/json' }, next: { revalidate: 60 } }
    );

    if (!gammaRes.ok) throw new Error(`Gamma API error: ${gammaRes.status}`);
    const events: any[] = await gammaRes.json();

    if (!events || events.length === 0) {
      return NextResponse.json({ validationError: `No prediction markets found for "${query}". Try a different search term.` });
    }

    // Find the most relevant event
    const lq = query.toLowerCase();
    const scored = events.map((e: any) => {
      const title = (e.title || '').toLowerCase();
      let score = 0;
      lq.split(' ').forEach((w: string) => { if (w.length > 2 && title.includes(w)) score++; });
      return { event: e, score };
    });
    scored.sort((a, b) => b.score - a.score || b.event.volumeNum - a.event.volumeNum);
    const topEvent = scored[0].event;

    const market = extractGammaMarket(topEvent);
    
    let summaryData: { summary: string; factors: any[] } = { 
      summary: 'Click "Deep Research" to generate an AI analysis of this market.', 
      factors: [] 
    };
    if (ai) {
      summaryData = await getGeminiSummary(market, query);
    }

    const { summary, factors } = summaryData;

    // Build related markets
    const relatedMarkets = events.slice(1, 11).map(extractGammaMarket);

    // Fetch real news from Google News RSS for fast scan
    const news = await fetchGoogleNewsRss(market.title || query);

    return NextResponse.json({ 
      market, 
      summary, 
      factors, 
      news,
      relatedMarkets 
    });
  } catch (error: any) {
    console.error('Research API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
