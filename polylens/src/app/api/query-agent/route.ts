import { NextResponse } from 'next/server';

const GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent';

// ── Step 1: Use Gemini to parse user query into structured search terms ────────
async function parseQueryWithAgent(userQuery: string): Promise<{
  searchTerms: string[];
  entities: { people: string[]; orgs: string[]; topics: string[]; thresholds: string[] };
  category: string;
  bestKeywords: string[];
}> {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) throw new Error('GOOGLE_API_KEY not set');

  const prompt = `You are a Polymarket query parsing agent. A user has typed a prediction or question. 
Your job is to extract the best search terms to find this market on Polymarket's database.

Polymarket uses SHORT, CONCISE market titles like:
- "Will Bitcoin hit $100k in 2025?"
- "NBA Champion 2026"  
- "US confirms alien life by 2027?"
- "Trump impeached in 2026?"

Given the user's input, return ONLY valid JSON (no markdown, no explanation) with:
{
  "searchTerms": ["term1", "term2", "term3"],  // 3-5 search queries to try against Polymarket API, ordered best-first
  "entities": {
    "people": [],     // named people/politicians/athletes
    "orgs": [],       // companies, governments, agencies  
    "topics": [],     // core concepts (aliens, bitcoin, election, etc.)
    "thresholds": []  // numbers/dates/milestones mentioned
  },
  "category": "Politics|Crypto|Sports|Science|Entertainment|Finance|World|Other",
  "bestKeywords": ["keyword1", "keyword2"]  // 1-3 most important single words
}

User input: "${userQuery}"`;

  const res = await fetch(`${GEMINI_URL}?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.1, maxOutputTokens: 400 }
    })
  });

  if (!res.ok) throw new Error(`Gemini agent error: ${res.status}`);
  const data = await res.json();
  const raw = data?.candidates?.[0]?.content?.parts?.[0]?.text || '{}';

  // Strip markdown fences if present
  const clean = raw.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(clean);
}

// ── Step 2: Search Polymarket Gamma with all generated terms in parallel ───────
async function searchGamma(terms: string[]): Promise<Map<string, any>> {
  const eventMap = new Map<string, any>();

  const responses = await Promise.allSettled(
    terms.slice(0, 6).map((term: string) =>
      fetch(
        `https://gamma-api.polymarket.com/events?q=${encodeURIComponent(term)}&active=true&closed=false&limit=20`,
        { headers: { 'User-Agent': 'PolyLens/Agent', Accept: 'application/json' }, cache: 'no-store' }
      ).then(r => r.ok ? r.json() : [])
    )
  );

  responses.forEach(res => {
    if (res.status === 'fulfilled' && Array.isArray(res.value)) {
      res.value.forEach((e: any) => { if (e.id) eventMap.set(e.id, e); });
    }
  });

  return eventMap;
}

// ── Step 3: Score and rank events by relevance to parsed query ─────────────────
function rankEvents(
  events: any[],
  userQuery: string,
  entities: { people: string[]; orgs: string[]; topics: string[]; thresholds: string[] },
  bestKeywords: string[]
): any[] {
  const lq = userQuery.toLowerCase().trim();

  return events
    .map((e: any) => {
      const title = (e.title || '').toLowerCase().trim();
      let score = 0;

      // Full query match
      if (title === lq) score += 5000;
      if (title.includes(lq)) score += 2000;

      // Entity matches (people, orgs, topics are high-value)
      [...entities.people, ...entities.orgs, ...entities.topics].forEach((entity: string) => {
        if (entity && title.includes(entity.toLowerCase())) score += 400;
      });

      // Threshold matches (numbers, years)
      entities.thresholds.forEach((t: string) => {
        if (t && title.includes(t.toLowerCase())) score += 300;
      });

      // Best keyword matches
      bestKeywords.forEach((kw: string) => {
        if (kw && title.includes(kw.toLowerCase())) score += 600;
      });

      // Liquidity as tiny tie-breaker (active markets float up)
      const liq = parseFloat(e.liquidity || e.liquidityClob || '0');
      score += Math.min(20, Math.log10(liq + 1) * 4);

      return { event: e, score, title: e.title };
    })
    .sort((a: any, b: any) => b.score - a.score);
}

// ── Route handler ─────────────────────────────────────────────────────────────
export async function POST(req: Request) {
  try {
    const { query } = await req.json();
    if (!query || typeof query !== 'string') {
      return NextResponse.json({ error: 'query is required' }, { status: 400 });
    }

    console.log(`[QueryAgent] Parsing: "${query}"`);

    // Step 1: Agent parses the user's intent
    const parsed = await parseQueryWithAgent(query);
    console.log('[QueryAgent] Parsed:', JSON.stringify(parsed, null, 2));

    // Step 2: Build comprehensive search terms
    const allTerms = [
      ...parsed.searchTerms,
      ...parsed.bestKeywords,
      ...parsed.entities.topics,
      ...parsed.entities.people,
      ...parsed.entities.orgs,
    ].filter((t: string) => t && t.length > 1);

    // Step 3: Search Gamma in parallel
    const eventMap = await searchGamma(allTerms);
    const events = Array.from(eventMap.values());
    console.log(`[QueryAgent] Found ${events.length} unique events`);

    if (events.length === 0) {
      return NextResponse.json({
        found: false,
        message: `No Polymarket markets found for "${query}". This market may not exist yet.`,
        parsed
      });
    }

    // Step 4: Rank and return top result + alternatives
    const ranked = rankEvents(events, query, parsed.entities, parsed.bestKeywords);
    console.log('[QueryAgent] Top 5:', ranked.slice(0, 5).map(r => ({ title: r.title, score: r.score })));

    return NextResponse.json({
      found: true,
      topEvent: ranked[0].event,
      alternatives: ranked.slice(1, 8).map(r => r.event),
      parsed,
      totalFound: events.length
    });

  } catch (err: any) {
    console.error('[QueryAgent] Error:', err.message);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
