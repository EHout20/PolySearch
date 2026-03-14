export interface MarketData {
  title: string;
  slug: string;
  probability: number;
  probabilityLabel?: string;
  delta24h: string;
  deltaDirection: 'up' | 'down' | 'neutral';
  volume: string;
  liquidity: string;
  outcomes: string[];
  outcomePrices: number[];
  description: string;
  isMulti?: boolean;
  clobTokenIds?: string[];  // For price history charts
}

export interface ResearchResult {
  market?: MarketData;
  summary?: string;
  report?: string; // Long-form intelligence report
  factors?: Array<{ title: string; detail: string; direction: 'up' | 'down' | 'neutral' }>;
  news?: Array<{ source: string; age: string; sentiment: 'bull' | 'bear' | 'neutral'; headline: string; snippet: string; url?: string }>;
  relatedMarkets?: MarketData[];
  validationError?: string;
}

export function fmtDollars(n: any): string {
  const val = parseFloat(n) || 0;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  if (val >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
  return `$${val.toFixed(0)}`;
}

export function extractGammaData(event: any): MarketData {
  const markets = event.markets || [];
  
  // Detect grouped multi-outcome events (like "NBA Champion" with one market per team)
  const isGrouped = markets.length > 2 && markets.every((m: any) => {
    const outcomes = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : m.outcomes;
    return outcomes?.length === 2; // each sub-market is a single Yes/No bet
  });

  if (isGrouped) {
    // Build a proper candidate list from grouped sub-markets
    const candidates = markets
      .map((m: any) => {
        const prices = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : (m.outcomePrices || [0.5, 0.5]);
        const yesPrice = parseFloat(prices[0]) || 0;
        return { label: m.groupItemTitle || m.question, price: yesPrice };
      })
      .sort((a: any, b: any) => b.price - a.price); // Sort by highest probability

    const vol = parseFloat(event.volumeNum || event.volume || '0');
    const liq = parseFloat(event.liquidityNum || event.liquidity || '0');
    const topP = Math.round(candidates[0]?.price * 100) || 0;

    return {
      title: event.title || event.slug || 'Market',
      slug: event.slug || '',
      probability: topP,
      probabilityLabel: `Leading: ${candidates[0]?.label || ''}`,
      delta24h: '+0.0%',
      deltaDirection: 'neutral',
      volume: fmtDollars(vol),
      liquidity: fmtDollars(liq),
      outcomes: candidates.map((c: any) => c.label),
      outcomePrices: candidates.map((c: any) => c.price),
      description: event.description || '',
      isMulti: true
    };
  }

  // Standard single-market extraction
  const m = markets[0] || {};
  let prices: number[] = [0.5, 0.5];
  try {
    const raw = typeof m.outcomePrices === 'string' ? JSON.parse(m.outcomePrices) : m.outcomePrices;
    prices = (raw || ["0.5","0.5"]).map((p: any) => parseFloat(p) || 0);
  } catch(e) { console.warn('Price parse failed'); }
  
  // Use lastTradePrice as fallback for grouped events where parsed price is 0
  let yesPrice = prices[0];
  if (yesPrice < 0.005) {
    yesPrice = parseFloat(m.lastTradePrice || m.bestAsk || '0') || yesPrice;
  }
  
  const outcomes = typeof m.outcomes === 'string' ? JSON.parse(m.outcomes) : (m.outcomes || ['Yes','No']);
  const isMulti = outcomes.length > 2;
  
  const probability = Math.max(1, Math.round(yesPrice * 100));
  const vol = parseFloat(event.volumeNum || event.volume || '0');
  const liq = parseFloat(event.liquidityNum || event.liquidity || '0');
  
  const rawDelta = parseFloat(m.oneDayPriceChange || '0');
  const delta24h = (rawDelta >= 0 ? '+' : '') + (rawDelta * 100).toFixed(1) + '%';
  const deltaDirection = rawDelta > 0.002 ? 'up' : (rawDelta < -0.002 ? 'down' : 'neutral');
  
  return {
    title: event.title || event.slug || 'Market',
    slug: event.slug || '',
    probability,
    probabilityLabel: isMulti ? `Leading: ${outcomes[0]}` : 'Implied probability',
    delta24h,
    deltaDirection,
    volume: fmtDollars(vol),
    liquidity: fmtDollars(liq),
    outcomes,
    outcomePrices: prices,
    description: event.description || '',
    isMulti
  };
}
