// ui/src/components/QualityPanel.tsx — Right panel
// Quality tab: confidence, models used, what happened
// Memory tab: stored corrections, restart prompt

import { useState } from 'react'
import type { QueryResponse, ModelInfo } from '../types'
import MemoryPanel from './MemoryPanel'

interface Props {
  response: QueryResponse | null
  models: Record<string, ModelInfo>
  activeProject?: string
  activeTab?: 'quality' | 'memory'
  onTabChange?: (tab: 'quality' | 'memory') => void
  onOpenHood?: () => void
  onOpenUsage?: () => void
}

type Tab = 'quality' | 'memory'

function ConfidenceIndicator({ label }: { label: string }) {
  const colors = {
    High:     { dot: '#22c55e', text: '#166534', bg: '#f0fdf4' },
    Medium:   { dot: '#f59e0b', text: '#92400e', bg: '#fffbeb' },
    Uncertain:{ dot: '#ef4444', text: '#991b1b', bg: '#fef2f2' },
  }
  const style = colors[label as keyof typeof colors] || colors.Uncertain
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 10, height: 10, borderRadius: '50%', background: style.dot }} />
      <span style={{
        fontSize: 14, fontWeight: 600, color: style.text,
        background: style.bg, padding: '3px 10px', borderRadius: 6,
      }}>
        {label}
      </span>
    </div>
  )
}

function WelfareBar({ model, score, isWinner }: { model: string; score: number; isWinner: boolean }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 12, color: '#374151', fontWeight: isWinner ? 700 : 400 }}>
          {model} {isWinner && '✓'}
        </span>
        <span style={{ fontSize: 12, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
          {score.toFixed(3)}
        </span>
      </div>
      <div style={{ height: 4, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 2,
          background: isWinner ? '#4338ca' : '#9ca3af',
          width: `${Math.min(100, score * 200)}%`,
          transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  )
}

function QualityTab({ response }: { response: QueryResponse | null }) {
  if (!response) {
    return (
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: 20, textAlign: 'center',
      }}>
        <div style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.6 }}>
          Send a message to see response quality information.
        </div>
      </div>
    )
  }

  const maxWelfare = response.welfare_scores
    ? Math.max(...Object.values(response.welfare_scores))
    : 0

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '16px 14px' }}>

      {/* Confidence */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
          Confidence
        </div>
        <ConfidenceIndicator label={response.confidence_label} />
      </div>

      {/* Models used */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
          Models
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {response.all_models_used?.map(m => (
            <div key={m} style={{
              fontSize: 13, color: '#374151',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: m === response.primary_model ? '#4338ca' : '#9ca3af', flexShrink: 0 }} />
              {m}
              {m === response.primary_model && (
                <span style={{ fontSize: 10, color: '#4338ca', fontWeight: 600 }}>winner</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* What happened */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
          What happened
        </div>
        <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
          {response.peer_review_used
            ? "All models answered, then reviewed each other's responses."
            : response.all_models_used?.length > 1
              ? `${response.all_models_used.length} models answered in parallel. Best selected by welfare score.`
              : 'One model answered. Local validation passed.'}
          {response.corrections_applied?.length > 0 && (
            <span style={{ display: 'block', marginTop: 4, color: '#92400e', fontSize: 12 }}>
              {response.corrections_applied.length} past correction{response.corrections_applied.length !== 1 ? 's' : ''} applied.
            </span>
          )}
        </div>
      </div>

      {/* VCG welfare scores */}
      {response.welfare_scores && Object.keys(response.welfare_scores).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Welfare scores
          </div>
          {Object.entries(response.welfare_scores)
            .sort(([, a], [, b]) => b - a)
            .map(([model, score]) => (
              <WelfareBar
                key={model}
                model={model}
                score={score}
                isWinner={score === maxWelfare}
              />
            ))
          }
          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 6 }}>
            W = P(domain) × confidence × prior score
          </div>
        </div>
      )}

      {/* Latency */}
      {response.latency_ms && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
            Latency
          </div>
          <div style={{ fontSize: 13, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
            {response.latency_ms.toFixed(0)} ms
          </div>
        </div>
      )}
    </div>
  )
}

export default function QualityPanel({ response, models, activeProject, activeTab, onTabChange, onOpenHood, onOpenUsage }: Props) {
  const [tab, setTab] = useState<Tab>('quality')
  const currentTab = activeTab ?? tab
  const setCurrentTab = (t: Tab) => { setTab(t); onTabChange?.(t) }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      background: '#fafaf8',
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', borderBottom: '1px solid #e5e7eb',
        padding: '0 14px', flexShrink: 0, alignItems: 'center',
      }}>
        {(['quality', 'memory'] as Tab[]).map(t => (
          <button key={t} onClick={() => setCurrentTab(t)} style={{
            padding: '12px 12px 10px', fontSize: 13, fontWeight: currentTab === t ? 600 : 400,
            color: currentTab === t ? '#4338ca' : '#9ca3af',
            border: 'none', background: 'transparent', cursor: 'pointer',
            borderBottom: currentTab === t ? '2px solid #4338ca' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.15s', textTransform: 'capitalize',
          }}>
            {t}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        {/* Usage link */}
        {onOpenUsage && (
          <button onClick={onOpenUsage} title="Usage & Cost" style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, color: '#d1d5db', padding: '8px 4px',
          }}>📊</button>
        )}
        {/* Look Under the Hood */}
        {onOpenHood && (
          <button onClick={onOpenHood} title="Look under the hood" style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 12, color: '#d1d5db', padding: '8px 4px',
            whiteSpace: 'nowrap',
          }}>🔩</button>
        )}
      </div>

      {/* Tab content */}
      {currentTab === 'quality' ? (
        <QualityTab response={response} />
      ) : (
        <MemoryPanel activeProject={activeProject} />
      )}
    </div>
  )
}
