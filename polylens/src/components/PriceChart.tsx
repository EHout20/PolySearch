'use client';
import React, { useEffect, useState } from 'react';

interface PricePoint { t: number; p: number; }

interface Props {
  tokenId: string;
  color?: string;
  height?: number;
  title?: string;
}

export default function PriceChart({ tokenId, color = '#1a6b4a', height = 120, title }: Props) {
  const [history, setHistory] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenId) return;
    setLoading(true);
    fetch(`/api/prices?market=${encodeURIComponent(tokenId)}&interval=max&fidelity=1440`)
      .then(r => r.json())
      .then(d => setHistory(d.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [tokenId]);

  if (loading) {
    return (
      <div style={{ height, background: 'var(--surface2)', borderRadius: 8, overflow: 'hidden' }}>
        <div className="shimmer" style={{ width: '100%', height: '100%' }} />
      </div>
    );
  }

  if (!history.length) return null;

  const W = 860, H = height;
  const pad = { top: 16, right: 8, bottom: 20, left: 36 };
  const inner = { w: W - pad.left - pad.right, h: H - pad.top - pad.bottom };

  // Only keep last 90 days for clarity
  const recent = history.slice(-90);
  const prices = recent.map(d => d.p);
  const times  = recent.map(d => d.t);

  const minP = Math.max(0, Math.min(...prices) - 0.02);
  const maxP = Math.min(1, Math.max(...prices) + 0.02);
  const minT = times[0], maxT = times[times.length - 1];

  const x = (t: number) => pad.left + ((t - minT) / (maxT - minT || 1)) * inner.w;
  const y = (p: number) => pad.top + (1 - (p - minP) / (maxP - minP || 0.01)) * inner.h;

  // SVG path
  const pts = recent.map((d, i) => `${i === 0 ? 'M' : 'L'}${x(d.t).toFixed(1)},${y(d.p).toFixed(1)}`).join(' ');
  const area = `${pts} L${x(times[times.length - 1]).toFixed(1)},${(pad.top + inner.h).toFixed(1)} L${x(times[0]).toFixed(1)},${(pad.top + inner.h).toFixed(1)} Z`;

  // Current vs start price
  const startP = prices[0], endP = prices[prices.length - 1];
  const trend = endP > startP + 0.01 ? 'up' : endP < startP - 0.01 ? 'down' : 'flat';
  const lineColor = trend === 'up' ? '#1a6b4a' : trend === 'down' ? '#b03a2e' : color;
  const areaColor = trend === 'up' ? 'rgba(26,107,74,0.08)' : trend === 'down' ? 'rgba(176,58,46,0.08)' : 'rgba(37,99,235,0.06)';

  // Y-axis labels (25%, 50%, 75%)
  const yLabels = [0, 0.25, 0.5, 0.75, 1].filter(v => v >= minP && v <= maxP);

  // Date labels
  const dateLabel = (t: number) => {
    const d = new Date(t * 1000);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        {title && <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'Geist Mono, monospace', textTransform: 'uppercase', letterSpacing: 0.5 }}>{title}</div>}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginLeft: 'auto' }}>
          <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'Geist Mono, monospace' }}>
            90d · {recent.length} pts
          </span>
          <span style={{ fontSize: 12, fontFamily: 'Geist Mono, monospace', fontWeight: 600, color: lineColor }}>
            {trend === 'up' ? '▲' : trend === 'down' ? '▼' : '—'} {Math.abs(Math.round((endP - startP) * 100))}pp
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height, display: 'block' }}>
        {/* Grid lines */}
        {yLabels.map(v => (
          <g key={v}>
            <line x1={pad.left} y1={y(v)} x2={W - pad.right} y2={y(v)} stroke="var(--border)" strokeWidth={0.5} strokeDasharray="4,4" />
            <text x={pad.left - 4} y={y(v) + 4} textAnchor="end" fontSize={9} fill="var(--muted)" fontFamily="Geist Mono, monospace">
              {Math.round(v * 100)}%
            </text>
          </g>
        ))}

        {/* Area fill */}
        <path d={area} fill={areaColor} />

        {/* Price line */}
        <path d={pts} fill="none" stroke={lineColor} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* Current price dot */}
        <circle
          cx={x(times[times.length - 1])}
          cy={y(prices[prices.length - 1])}
          r={4}
          fill={lineColor}
          stroke="white"
          strokeWidth={2}
        />

        {/* Date labels */}
        <text x={x(times[0])} y={H - 4} textAnchor="start" fontSize={9} fill="var(--muted)" fontFamily="Geist Mono, monospace">
          {dateLabel(times[0])}
        </text>
        <text x={x(times[times.length - 1])} y={H - 4} textAnchor="end" fontSize={9} fill="var(--muted)" fontFamily="Geist Mono, monospace">
          {dateLabel(times[times.length - 1])}
        </text>
      </svg>
    </div>
  );
}
