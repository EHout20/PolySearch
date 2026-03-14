'use client';
import React, { useState, useRef } from 'react';
import { ResearchResult } from './Common';
import PriceChart from './PriceChart';

interface Props {
  data: ResearchResult;
  query: string;
  onDeepResearch: () => void;
  loadingDeep?: boolean;
  deepLog?: string[];
}

const SENT_COLOR  = { bull: '#1a6b4a', bear: '#b03a2e', neutral: '#92600a' };
const SENT_BG     = { bull: 'rgba(26,107,74,0.08)', bear: 'rgba(176,58,46,0.08)', neutral: 'rgba(146,96,10,0.08)' };
const SENT_LABEL  = { bull: '▲ Bullish', bear: '▼ Bearish', neutral: '◎ Neutral' };

export default function ResearchResults({ data, query, onDeepResearch, loadingDeep, deepLog = [] }: Props) {
  const [newsExpanded, setNewsExpanded] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const m = data.market;

  // ─── Validation Error ────────────────────────────────────────
  if (data.validationError) {
    return (
      <div className="results-container">
        <div className="card" style={{ border: '1px dashed #ef4444', background: 'rgba(239,68,68,0.05)' }}>
          <div className="card-body">
            <p style={{ color: '#ef4444', fontWeight: 600, marginBottom: 8 }}>⚠️ Topic Not Found</p>
            <p style={{ color: '#666' }}>{data.validationError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!m) return null;

  const isMulti = m.isMulti || m.outcomes.length > 2;
  const topP     = Math.max(1, m.outcomePrices[0] ? Math.round(m.outcomePrices[0] * 100) : m.probability);
  const topColor = topP >= 60 ? '#1a6b4a' : topP >= 35 ? '#92600a' : '#b03a2e';
  const news     = data.news || [];
  const visibleNews = newsExpanded ? news : news.slice(0, 5);
  const chartTokenId = m.clobTokenIds?.[0] || '';

  return (
    <div className="results-container">

      {/* ─── HEADER ─────────────────────────────────────────── */}
      <div style={{ marginBottom: 28 }}>
        <div className="card-label" style={{ color: 'var(--muted)', marginBottom: 8 }}>RESEARCH RESULTS</div>
        <h2 style={{ fontFamily: "'Instrument Serif', serif", fontSize: 30, lineHeight: 1.2, marginBottom: 8 }}>
          {m.title || query}
        </h2>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12, color: 'var(--muted)' }}>
            Vol {m.volume} · Liq {m.liquidity}
          </span>
          <span style={{
            fontSize: 11, fontFamily: 'Geist Mono, monospace', fontWeight: 600, padding: '2px 8px',
            borderRadius: 6, background: 'var(--surface2)',
            color: m.deltaDirection === 'up' ? '#1a6b4a' : m.deltaDirection === 'down' ? '#b03a2e' : 'var(--muted)'
          }}>
            {m.delta24h} 24h
          </span>
          {m.slug && (
            <a
              href={`https://polymarket.com/event/${m.slug}`}
              target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 11, color: '#2563eb', fontFamily: 'Geist Mono, monospace', textDecoration: 'none' }}
            >
              View on Polymarket ↗
            </a>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>
        {/* ─── LEFT COLUMN ──────────────────────────────────── */}
        <div>

          {/* PRICE CHART */}
          {chartTokenId && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-label">📈 Price History</div>
                <div className="card-label" style={{ color: 'var(--muted)', fontSize: 10 }}>Last 90 days · Daily</div>
              </div>
              <div style={{ padding: '16px 20px' }}>
                <PriceChart tokenId={chartTokenId} height={140} />
              </div>
            </div>
          )}

          {/* CANDIDATES / ODDS LEADERBOARD */}
          {isMulti ? (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-label">🏆 Candidates & Odds</div>
                <div className="card-label" style={{ color: 'var(--muted)' }}>{m.outcomes.length} entries (scrollable)</div>
              </div>
              <div style={{ padding: '8px 0', maxHeight: 420, overflowY: 'auto' }}>
                {m.outcomes.map((label, idx) => {
                  const prob    = Math.max(1, Math.round((m.outcomePrices[idx] || 0) * 100));
                  const isTop   = idx === 0;
                  const barClr  = isTop ? '#1a6b4a' : idx === 1 ? '#2563eb' : 'var(--border2)';
                  const maxP    = Math.max(1, Math.round((m.outcomePrices[0] || 0.01) * 100));
                  const barPct  = Math.min(100, Math.round((prob / maxP) * 100));
                  return (
                    <div key={label + idx} style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px',
                      background: isTop ? 'rgba(26,107,74,0.03)' : 'transparent',
                      borderBottom: idx < m.outcomes.length - 1 ? '1px solid var(--border)' : 'none'
                    }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                        background: isTop ? '#1a6b4a' : 'var(--surface2)',
                        color: isTop ? 'white' : 'var(--muted)',
                        fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: 'Geist Mono, monospace'
                      }}>{idx + 1}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: isTop ? 600 : 400, marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {label}
                          {isTop && <span style={{ marginLeft: 6, fontSize: 10, color: '#1a6b4a', fontFamily: 'Geist Mono, monospace', textTransform: 'uppercase' }}>Leading</span>}
                        </div>
                        <div style={{ height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${barPct}%`, background: barClr, borderRadius: 3, transition: 'width 0.6s ease' }} />
                        </div>
                      </div>
                      <div style={{
                        fontFamily: 'Geist Mono, monospace', fontSize: 15, fontWeight: 700, flexShrink: 0, minWidth: 44, textAlign: 'right',
                        color: barClr === 'var(--border2)' ? 'var(--muted)' : barClr
                      }}>{prob}%</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* BINARY MARKET GAUGE */
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-label">📊 Market Probability</div>
                <div className="card-label" style={{ color: topColor }}>
                  {topP >= 70 ? '● Strong signal' : topP >= 50 ? '● Moderate signal' : '● Uncertain'}
                </div>
              </div>
              <div className="card-body">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 48, fontWeight: 700, color: topColor, lineHeight: 1 }}>{topP}%</div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>Implied probability · YES</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 24, color: 'var(--muted)', lineHeight: 1 }}>{100 - topP}%</div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>NO</div>
                  </div>
                </div>
                <div style={{ height: 10, background: '#fde8e8', borderRadius: 5, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${topP}%`, background: `linear-gradient(90deg, ${topColor}, ${topColor}cc)`, borderRadius: 5, transition: 'width 0.8s ease' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontFamily: 'Geist Mono, monospace', fontSize: 10, color: 'var(--muted)' }}>
                  <span>YES {topP}%</span><span>NO {100 - topP}%</span>
                </div>
                {/* Plain-English odds explanation */}
                <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--surface2)', borderRadius: 8, fontSize: 12, color: 'var(--muted)', lineHeight: 1.5 }}>
                  💡 Polymarket traders collectively believe there&apos;s a <strong style={{ color: topColor }}>{topP}% chance</strong> this happens — and a <strong>{100 - topP}% chance</strong> it doesn&apos;t. This is based on real money wagered by thousands of traders.
                </div>
              </div>
            </div>
          )}

          {/* AI SUMMARY */}
          {(() => {
            const summary = data.summary || '';
            const isPrompt = summary.includes('Deep Research');
            const LIMIT = 400;
            const displayText = !summaryExpanded && summary.length > LIMIT
              ? summary.slice(0, LIMIT).trimEnd() + '\u2026'
              : summary;
            return (
              <div className="card" style={{ marginBottom: 24 }}>
                <div className="card-header">
                  <div className="card-label">✦ AI Analysis</div>
                  <div className="card-label" style={{ color: 'var(--muted)', fontSize: 10 }}>Powered by Gemini</div>
                </div>
                <div className="card-body">
                  {isPrompt ? (
                    <div className="ai-summary-text" style={{ fontStyle: 'italic', color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <p>{summary}</p>
                      <button className="search-btn" style={{ alignSelf: 'flex-start', fontSize: 12, padding: '8px 16px' }} onClick={onDeepResearch}>
                        Generate Analysis →
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div className="ai-summary-text" style={{ fontSize: 13, lineHeight: 1.65 }}>{displayText}</div>
                      {summary.length > LIMIT && (
                        <button onClick={() => setSummaryExpanded(!summaryExpanded)}
                          style={{ marginTop: 8, fontSize: 12, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'inherit' }}>
                          {summaryExpanded ? 'Show less ↑' : 'Read more ↓'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* MAIN INTEL GRID: Report vs News */}
          <div style={{ display: 'grid', gridTemplateColumns: data.report && news.length > 0 ? '1.2fr 0.8fr' : '1fr', gap: 24, marginBottom: 24 }}>
            {/* INTELLIGENCE REPORT */}
            {data.report && (
              <div className="card" style={{ borderLeft: '4px solid #2563eb' }}>
                <div className="card-header">
                  <div className="card-label">📋 Intelligence Report</div>
                  <div className="card-label" style={{ color: '#2563eb', fontSize: 10 }}>Comprehensive Briefing</div>
                </div>
                <div className="card-body" style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)' }}>
                  <div className="report-content" style={{ whiteSpace: 'pre-wrap' }}>
                    {data.report.split('\n').map((line, i) => {
                      if (line.startsWith('# ')) {
                        return <h3 key={i} style={{ fontSize: 16, fontWeight: 700, marginTop: 16, marginBottom: 8, color: '#111827' }}>{line.replace('# ', '')}</h3>;
                      }
                      if (line.startsWith('## ')) {
                        return <h4 key={i} style={{ fontSize: 14, fontWeight: 700, marginTop: 12, marginBottom: 6, color: '#374151' }}>{line.replace('## ', '')}</h4>;
                      }
                      return <p key={i} style={{ marginBottom: 12 }}>{line}</p>;
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* NEWS ARTICLES (Side-by-side with Report if exists) */}
            {news.length > 0 ? (
              <div className="card">
                <div className="card-header">
                  <div className="card-label">📰 News & Sources</div>
                  <div className="card-label" style={{ color: 'var(--muted)' }}>{news.length} articles</div>
                </div>
                <div style={{ padding: '8px 0', maxHeight: 800, overflowY: 'auto' }}>
                  {visibleNews.map((n, i) => {
                    if (!n) return null;
                    const s = (n.sentiment || 'neutral') as 'bull' | 'bear' | 'neutral';
                    // Use direct URL if available, otherwise fall back to Google News search
                    const hasRealUrl = n.url && n.url.startsWith('http') && !n.url.includes('google.com/search');
                    const articleUrl = hasRealUrl ? n.url : `https://news.google.com/search?q=${encodeURIComponent(n.headline || query)}&hl=en`;
                    return (
                      <a key={i} href={articleUrl} target="_blank" rel="noopener noreferrer"
                        style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}>
                        <div
                          style={{ padding: '14px 20px', borderBottom: i < visibleNews.length - 1 ? '1px solid var(--border)' : 'none', transition: 'background 0.15s' }}
                          onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface2)')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10, textTransform: 'uppercase', color: 'var(--muted)' }}>{n.source || 'News'}</span>
                              <span style={{ fontSize: 10, color: 'var(--muted)' }}>· {n.age || 'Recent'}</span>
                              {hasRealUrl && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(37,99,235,0.1)', color: '#2563eb', fontFamily: 'Geist Mono, monospace' }}>DIRECT LINK</span>}
                            </div>
                            <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4, color: SENT_COLOR[s] || 'var(--muted)', background: SENT_BG[s] || 'transparent', fontFamily: 'Geist Mono, monospace' }}>
                              {SENT_LABEL[s] || '◎ Neutral'}
                            </span>
                          </div>
                          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, lineHeight: 1.3 }}>
                            {n.headline || 'Untitled Article'}
                            <span style={{ marginLeft: 6, fontSize: 11, color: '#2563eb' }}>↗</span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>{n.snippet || 'No snippet available.'}</div>
                          {!hasRealUrl && n.headline && (
                            <div style={{ marginTop: 5, fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>→ Searching Google News for this article</div>
                          )}
                        </div>
                      </a>
                    );
                  })}
                </div>
                {news.length > 5 && (
                  <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)' }}>
                    <button className="show-more-btn" style={{ marginTop: 0 }} onClick={() => setNewsExpanded(!newsExpanded)}>
                      {newsExpanded ? 'Show Less ↑' : `Show ${news.length - 5} More Articles ↓`}
                    </button>
                  </div>
                )}
              </div>
            ) : data.report ? (
              <div className="card">
                <div className="card-header">
                  <div className="card-label">📰 News & Sources</div>
                </div>
                <div className="card-body" style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
                  <div style={{ fontSize: 24, marginBottom: 12 }}>🗞️</div>
                  <div style={{ fontSize: 13 }}>No direct news sources found for this topic.</div>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* ─── RIGHT COLUMN ─────────────────────────────────── */}
        <div>
          {/* KEY FACTORS */}
          {(data.factors || []).length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header"><div className="card-label">Key Factors</div></div>
              <div style={{ padding: '12px 0' }}>
                {(data.factors || []).map((f, i) => (
                  <div key={i} style={{ padding: '10px 20px', display: 'flex', gap: 12, borderBottom: i < (data.factors || []).length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0, background: f.direction === 'up' ? '#1a6b4a' : f.direction === 'down' ? '#b03a2e' : 'var(--muted)' }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{f.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.4 }}>{f.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* RELATED MARKETS ("Odds Listed Out") */}
          {(data.relatedMarkets || []).length > 0 && (
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-label">🔗 Related Markets & Odds</div>
                <div className="card-label" style={{ color: 'var(--muted)', fontSize: 10 }}>Polymarket odds</div>
              </div>
              {/* Odds explanation */}
              <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', fontSize: 11, color: 'var(--muted)', background: 'var(--surface2)', lineHeight: 1.5 }}>
                💡 These % figures represent the probability Polymarket traders assign based on real money wagered — e.g. 15% = traders think there&apos;s a 1-in-7 chance.
              </div>
              <div style={{ padding: '8px 0', maxHeight: 400, overflowY: 'auto' }}>
                {(data.relatedMarkets || []).map((rm, i) => {
                  const rmColor = rm.probability >= 60 ? '#1a6b4a' : rm.probability >= 40 ? '#92600a' : '#b03a2e';
                  const rmLabel = rm.probability >= 70 ? 'Likely' : rm.probability >= 45 ? 'Toss-up' : rm.probability >= 20 ? 'Unlikely' : 'Very unlikely';
                  return (
                    <a key={i} href={`https://polymarket.com/event/${rm.slug}`} target="_blank" rel="noopener noreferrer"
                      style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}>
                      <div style={{ 
                        padding: '12px 20px', 
                        borderBottom: i < (data.relatedMarkets || []).length - 1 ? '1px solid var(--border)' : 'none',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        transition: 'background 0.12s'
                      }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface2)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        <div style={{ flex: 1, minWidth: 0, marginRight: 12 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 2 }}>
                            {rm.title} <span style={{ fontSize: 11, color: '#2563eb' }}>↗</span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'Geist Mono, monospace' }}>
                            Vol {rm.volume} · <span style={{ color: rmColor }}>{rmLabel}</span>
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 15, fontWeight: 700, color: rmColor }}>{rm.probability}%</div>
                          <div style={{ fontSize: 9, color: 'var(--muted)' }}>chance</div>
                        </div>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          )}

          {/* MARKET STATS */}
          <div className="card">
            <div className="card-header"><div className="card-label">Market Stats</div></div>
            <div style={{ padding: '16px 20px' }}>
              {[
                { label: 'Volume', value: m.volume },
                { label: 'Liquidity', value: m.liquidity },
                { label: '24h Change', value: m.delta24h, color: m.deltaDirection === 'up' ? '#1a6b4a' : m.deltaDirection === 'down' ? '#b03a2e' : 'var(--muted)' },
                { label: 'Type', value: isMulti ? `Multi-outcome · ${m.outcomes.length} entries` : 'Binary (Yes/No)' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>{label}</div>
                  <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 13, fontWeight: 500, color: color || 'var(--text)' }}>{value}</div>
                </div>
              ))}
              {m.slug && (
                <a href={`https://polymarket.com/event/${m.slug}`} target="_blank" rel="noopener noreferrer"
                  style={{ display: 'block', marginTop: 12, padding: '10px 14px', background: 'var(--blue-bg)', borderRadius: 10, textDecoration: 'none', textAlign: 'center', fontSize: 13, color: '#2563eb', fontWeight: 500 }}>
                  Open on Polymarket ↗
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
