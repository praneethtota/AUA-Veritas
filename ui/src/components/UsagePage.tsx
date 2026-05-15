// ui/src/components/UsagePage.tsx — Usage and cost statistics modal

import { useState, useEffect } from 'react'

interface UsageStat {
  model_id: string
  display_name: string
  query_count: number
  estimated_cost: number
  last_used: number | null
}

interface Props {
  onClose: () => void
}

export default function UsagePage({ onClose }: Props) {
  const [stats, setStats] = useState<UsageStat[]>([])
  const [totalCost, setTotalCost] = useState(0)
  const [totalQueries, setTotalQueries] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchUsage()
  }, [])

  const fetchUsage = async () => {
    try {
      const isElectron = !!(window as any).veritas
      const url = isElectron ? 'http://127.0.0.1:47821/usage' : '/api/usage'
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setStats(data.models || [])
        setTotalCost(data.total_cost || 0)
        setTotalQueries(data.total_queries || 0)
      }
    } catch {
      setStats([])
    } finally {
      setLoading(false)
    }
  }

  const maxQueries = Math.max(...stats.map(s => s.query_count), 1)

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9998, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, width: '100%', maxWidth: 500,
        maxHeight: '80vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 20px 14px', borderBottom: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>Usage & Cost</div>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 6, border: '1px solid #e5e7eb',
            background: '#f9fafb', cursor: 'pointer', fontSize: 16, color: '#6b7280',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {/* Summary */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            {[
              { label: 'Total queries', value: totalQueries.toString() },
              { label: 'Estimated cost', value: `$${totalCost.toFixed(4)}` },
            ].map(({ label, value }) => (
              <div key={label} style={{
                flex: 1, padding: 14, background: '#f9fafb',
                borderRadius: 10, border: '1px solid #e5e7eb',
              }}>
                <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Per-model breakdown */}
          <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 10 }}>
            Per model
          </div>

          {loading ? (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>Loading...</div>
          ) : stats.length === 0 ? (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>
              No usage data yet. Start chatting to see stats here.
            </div>
          ) : (
            stats.map(stat => (
              <div key={stat.model_id} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: '#374151', fontWeight: 500 }}>
                    {stat.display_name}
                  </span>
                  <div style={{ display: 'flex', gap: 14 }}>
                    <span style={{ fontSize: 12, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
                      {stat.query_count} queries
                    </span>
                    <span style={{ fontSize: 12, color: '#374151', fontVariantNumeric: 'tabular-nums', minWidth: 60, textAlign: 'right' }}>
                      ${stat.estimated_cost.toFixed(4)}
                    </span>
                  </div>
                </div>
                {/* Usage bar */}
                <div style={{ height: 4, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 2, background: '#4338ca',
                    width: `${(stat.query_count / maxQueries) * 100}%`,
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                {stat.last_used && (
                  <div style={{ fontSize: 10, color: '#d1d5db', marginTop: 2 }}>
                    Last used {new Date(stat.last_used * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </div>
                )}
              </div>
            ))
          )}

          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 16, lineHeight: 1.5 }}>
            Cost estimates are approximate. Actual charges appear in each provider's billing dashboard.
            Estimates assume ~$0.01 per primary model call and ~$0.001 per judge call.
          </div>
        </div>
      </div>
    </div>
  )
}
