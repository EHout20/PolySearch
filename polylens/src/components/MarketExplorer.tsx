'use client';
import React, { useState } from 'react';
import { MarketData } from './Common';

interface Props {
  title: string;
  data: MarketData[];
  onSelect?: (q: string) => void;
}

export default function MarketExplorer({ title, data, onSelect }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const displayData = isExpanded ? data : data.slice(0, 10);

  return (
    <div className="explorer-section">
      <div className="explorer-header">
        <div className="explorer-title">{title}</div>
        <div className="header-tag">{data.length} live events</div>
      </div>
      
      <div className="card">
        <div className="odds-row header" style={{ gridTemplateColumns: '1fr 120px 140px' }}>
          <div className="odds-col">Market</div>
          <div className="odds-col center">Odds</div>
          <div className="odds-col right">Volume</div>
        </div>
        
        {displayData.map((m, i) => {
          const pColor = m.probability >= 60 ? 'var(--green)' : m.probability >= 35 ? 'var(--amber)' : 'var(--red)';
          return (
            <div key={m.slug + i} className="odds-row" style={{ gridTemplateColumns: '1fr 120px 140px' }} onClick={() => onSelect?.(m.title)}>
              <div className="odds-col">
                <div className="odds-m-title">{m.title}</div>
                {m.isMulti && (
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    Multi-Outcome · Leading: {m.outcomes[0]}
                  </div>
                )}
              </div>
              <div className="odds-col center">
                <div className="odds-prob" style={{ color: pColor }}>{m.probability}%</div>
              </div>
              <div className="odds-col right">
                <div className="odds-vol">{m.volume}</div>
              </div>
            </div>
          );
        })}
      </div>
      
      {data.length > 10 && (
        <button className="show-more-btn" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? 'Show Less ↑' : 'Show More Markets ↓'}
        </button>
      )}
    </div>
  );
}
