'use client';
import React, { useState, useEffect } from 'react';
import { MarketData, ResearchResult, extractGammaData } from '@/components/Common';
import MarketExplorer from '@/components/MarketExplorer';
import ResearchResults from '@/components/ResearchResults';

export default function Home() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingDeep, setLoadingDeep] = useState(false);
  const [deepLog, setDeepLog] = useState<string[]>([]);
  const [researchData, setResearchData] = useState<ResearchResult | null>(null);
  const [trendingMarkets, setTrendingMarkets] = useState<MarketData[]>([]);
  const [relatedMarkets, setRelatedMarkets] = useState<MarketData[]>([]);

  // Load trending on mount
  useEffect(() => {
    fetchTrending();
  }, []);

  async function fetchTrending() {
    try {
      const res = await fetch('/api/gamma/events?order=volume&ascending=false&active=true&closed=false&limit=30');
      const events = await res.json();
      setTrendingMarkets(events.map(extractGammaData));
    } catch (e) {
      console.warn('Trending fetch failed');
    }
  }

  async function handleSearch(q: string, deep = false) {
    if (!q.trim()) return;
    setQuery(q);
    setIsSearching(true);
    setIsLoading(true);
    setResearchData(null);
    setDeepLog([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
      const res = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, ai: false, deep: false })
      });
      const data = await res.json();
      setResearchData(data);
      if (data.relatedMarkets) {
        setRelatedMarkets(data.relatedMarkets);
      }
    } catch (e: any) {
      console.error('Search failed:', e);
    } finally {
      setIsLoading(false);
    }
  }

  async function runDeepResearch() {
    if (!query.trim()) return;
    setLoadingDeep(true);
    setDeepLog(['🔍 Analysing news sources...', `📡 Querying Polymarket odds for "${query}"...`]);

    try {
      // Simulate progress log while waiting
      const logTimer = setInterval(() => {
        setDeepLog(prev => {
          if (prev.length < 8) {
            const steps = [
              '📰 Reading news articles...',
              '🔎 Analysing market sentiment...',
              '📊 Cross-referencing with market data...',
              '✓ Sources verified, compiling...',
              '✦ Generating AI report...',
            ];
            const next = steps[prev.length - 2];
            return next ? [...prev, next] : prev;
          }
          return prev;
        });
      }, 2500);

      const res = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          deep: true,
          // Send the news and market already on screen — Gemini writes from these
          market: researchData?.market,
          news: researchData?.news ?? [],
        })
      });
      clearInterval(logTimer);
      const data = await res.json();
      setDeepLog(prev => [...prev, '✓ Deep research complete!']);
      // Merge: always keep the original news — never let it be replaced
      const existingNews = researchData?.news ?? [];
      setResearchData(prev => ({
        ...prev,
        ...data,
        market: data.market || prev?.market,
        // Prefer existing news (fast RSS) — only use returned news if we had none
        news: existingNews.length > 0 ? existingNews : (data.news ?? []),
      }));
      if (data.relatedMarkets) setRelatedMarkets(data.relatedMarkets);
    } catch (e) {
      setDeepLog(prev => [...prev, '⚠ Research encountered an error. Please try again.']);
    } finally {
      setLoadingDeep(false);
    }
  }


  return (
    <main className="app-container">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 40 }}>
        <div className="wordmark">Poly<em>lens</em></div>
        <div className="header-tag">Market Intelligence</div>
      </header>

      <div className={`hero ${isSearching ? 'compact' : ''}`}>
        {!isSearching && (
          <>
            <div className="card-label" style={{ color: 'var(--muted)', marginBottom: 12 }}>Prediction Market Research</div>
            <h1 className="hero-title">What's the market<br/><em>saying?</em></h1>
            <p className="hero-sub">Enter any prediction market topic or question — get instant AI-powered research.</p>
          </>
        )}

        <div className="search-wrap">
          <input
            type="text"
            placeholder="e.g. Oscars Best Picture 2026, NBA Champion..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
            disabled={isLoading}
          />
          <button className="search-btn" onClick={() => handleSearch(query)} disabled={isLoading}>
            {isLoading ? 'Researching...' : 'Research →'}
          </button>
        </div>

        {!isSearching && (
          <div style={{ marginTop: 24, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>Try:</span>
            {['Oscars Best Picture', 'NBA Champion 2026', 'Bitcoin $150k', 'Fed rate cut'].map(q => (
              <span key={q} className="odds-delta"
                style={{ cursor: 'pointer', background: 'var(--surface2)', padding: '4px 10px', borderRadius: 8 }}
                onClick={() => handleSearch(q)}>
                {q}
              </span>
            ))}
          </div>
        )}
      </div>

      {isLoading && (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div className="shimmer" style={{ height: 40, width: '60%', margin: '0 auto 20px' }} />
          <div className="shimmer" style={{ height: 100, width: '100%', marginBottom: 20 }} />
          <div className="shimmer" style={{ height: 100, width: '100%' }} />
        </div>
      )}

      {/* RESULT ORDERING: Summary ALWAYS above Explorer */}
      {researchData && !isLoading && (
        <ResearchResults
          data={researchData}
          query={query}
          onDeepResearch={runDeepResearch}
          loadingDeep={loadingDeep}
          deepLog={deepLog}
        />
      )}

      <MarketExplorer
        title={isSearching ? 'Related Markets' : 'Trending Markets'}
        data={isSearching ? relatedMarkets : trendingMarkets}
        onSelect={(q) => handleSearch(q)}
      />

      <footer style={{ marginTop: 80, padding: '24px 0 40px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)' }}>
        <div>&copy; 2026 PolyLens Market Research</div>
        <div style={{ fontFamily: 'Geist Mono, monospace', textTransform: 'uppercase', letterSpacing: 1 }}>Powered by Gamma API & Gemini</div>
      </footer>
    </main>
  );
}
