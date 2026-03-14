import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtDollars(n: any): string {
  const val = parseFloat(n) || 0;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val.toFixed(0)}`;
}

function extractGammaMarket(event: any) {
  const markets = event.markets || [];
  const isGrouped = markets.length > 2 && markets.every((m: any) => {
    const o = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : m.outcomes;
    return o?.length === 2;
  });

  if (isGrouped) {
    const candidates = markets
      .map((m: any) => {
        const prices = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : (m.outcomePrices || [0, 0]);
        return { label: m.groupItemTitle || m.question, price: parseFloat(prices[0]) || 0 };
      })
      .sort((a: any, b: any) => b.price - a.price);
    const topP = Math.round((candidates[0]?.price || 0) * 100);
    return {
      title: event.title || event.slug,
      slug: event.slug || '',
      probability: topP,
      probabilityLabel: `Leading: ${candidates[0]?.label}`,
      delta24h: '+0.0%', deltaDirection: 'neutral' as const,
      volume: fmtDollars(event.volumeNum || event.volume),
      liquidity: fmtDollars(event.liquidityNum || event.liquidity),
      outcomes: candidates.map((c: any) => c.label),
      outcomePrices: candidates.map((c: any) => c.price),
      description: event.description || '',
      isMulti: true
    };
  }

  const m = markets[0] || {};
  let prices: number[] = [0.5, 0.5];
  try {
    const raw = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : m.outcomePrices;
    prices = (raw || []).map((p: any) => parseFloat(p) || 0);
  } catch (_) {}

  let yesPrice = prices[0];
  if (yesPrice < 0.005) yesPrice = parseFloat(m.lastTradePrice || m.bestAsk || '0') || yesPrice;

  const outcomes = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : (m.outcomes || ['Yes', 'No']);
  const rawDelta = parseFloat(m.oneDayPriceChange || '0');

  // Extract token IDs for price history chart
  let clobTokenIds: string[] = [];
  try {
    const raw = typeof m.clobTokenIds === 'string' ? JSON.parse(m.clobTokenIds) : m.clobTokenIds;
    clobTokenIds = Array.isArray(raw) ? raw : [];
  } catch (_) {}

  return {
    title: event.title || event.slug,
    slug: event.slug || '',
    probability: Math.max(1, Math.round(yesPrice * 100)),
    probabilityLabel: 'Implied probability',
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

// ── Gemini Summary ────────────────────────────────────────────────────────────
async function getGeminiSummary(market: any, query: string): Promise<{ summary: string; report: string; factors: any[] }> {
  let apiKey = process.env.GOOGLE_API_KEY;
  
  if (!apiKey) {
    try {
      const fs = require('fs');
      const p = require('path');
      const envPath = p.join(process.cwd(), '.env');
      if (fs.existsSync(envPath)) {
        const envFile = fs.readFileSync(envPath, 'utf8');
        const match = envFile.match(/^GOOGLE_API_KEY\s*=\s*(.+)$/m);
        if (match) apiKey = match[1].trim();
      }
    } catch (_) {}
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

// ── Main Handler ─────────────────────────────────────────────────────────────
export async function POST(req: Request) {
  try {
    const { query, deep, ai = true } = await req.json();
    if (!query?.trim()) return NextResponse.json({ error: 'Missing query' }, { status: 400 });

    if (deep) {
      // Deep: run the Python agent
      const scriptPath = path.join(process.cwd(), 'backend', 'polymarket_agent.py');
      let stdout = '', stderr = '';
      const agentProcess = spawn('python3', [scriptPath, query, '--json', '--deep']);
      agentProcess.stdout.on('data', (d) => { stdout += d.toString(); });
      agentProcess.stderr.on('data', (d) => { stderr += d.toString(); });
      const result: any = await new Promise((resolve, reject) => {
        agentProcess.on('close', (code) => {
          if (code !== 0 && !stdout.includes('{')) reject(new Error(stderr || 'Agent failed'));
          else {
            try { 
              // Robust extraction: find the first { and last }
              const start = stdout.indexOf('{');
              const end = stdout.lastIndexOf('}');
              if (start === -1 || end === -1) throw new Error('No JSON found in output');
              resolve(JSON.parse(stdout.substring(start, end + 1))); 
            }
            catch (_) { reject(new Error('Failed to parse agent output: ' + stdout)); }
          }
        });
      });
      return NextResponse.json(result);
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

    return NextResponse.json({ 
      market, 
      summary, 
      factors, 
      news: [], // Blank until deep research provides real ones
      relatedMarkets 
    });
  } catch (error: any) {
    console.error('Research API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
