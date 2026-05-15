// ui/src/components/LookUnderTheHood.tsx
// Model reliability panel — subtle, found by curious users.
// Time-series graphs per model with clickable data points.
// Shows the same 0-100 scores the models see in their system prompts.

import { useState, useEffect } from 'react'

interface ScoreEvent {
  audit_id: string
  model_id: string
  score_before: number
  score_after: number
  verdict: string
  correction_stored: boolean
  query_preview: string
  created_at: number
}

interface ModelHistory {
  model_id: string
  display_name: string
  events: ScoreEvent[]
  current_score: number
  trend: 'up' | 'down' | 'flat'
}

interface Props {
  onClose: () => void
}

function ScoreGraph({
  events,
  modelId,
  onSelectPoint,
}: {
  events: ScoreEvent[]
  modelId: string
  onSelectPoint: (event: ScoreEvent | null) => void
}) {
  if (events.length < 2) return null

  const scores = events.map(e => e.score_after)
  const min = Math.max(0, Math.min(...scores) - 5)
  const max = Math.min(100, Math.max(...scores) + 5)
  const range = max - min || 10

  const W = 260
  const H = 70
  const PAD = 8

  const plotX = (i: number) => PAD + (i / (scores.length - 1)) * (W - PAD * 2)
  const plotY = (score: number) => H - PAD - ((score - min) / range) * (H - PAD * 2)

  const pathD = scores
    .map((s, i) => `${i === 0 ? 'M' : 'L'} ${plotX(i).toFixed(1)} ${plotY(s).toFixed(1)}`)
    .join(' ')

  return (
    <svg
      width={W} height={H}
      style={{ cursor: 'pointer', overflow: 'visible' }}
    >
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map(t => (
        <line
          key={t}
          x1={PAD} y1={PAD + t * (H - PAD * 2)}
          x2={W - PAD} y2={PAD + t * (H - PAD * 2)}
          stroke="#f3f4f6" strokeWidth={1}
        />
      ))}

      {/* Line */}
      <path d={pathD} fill="none" stroke="#4338ca" strokeWidth={1.5} strokeLinejoin="round" />

      {/* Points */}
      {events.map((event, i) => (
        <circle
          key={event.audit_id}
          cx={plotX(i)} cy={plotY(event.score_after)}
          r={5}
          fill={event.verdict === 'incorrect' ? '#ef4444' : '#4338ca'}
          stroke="#fff" strokeWidth={1.5}
          style={{ cursor: 'pointer' }}
          onClick={() => onSelectPoint(event)}
        />
      ))}
    </svg>
  )
}

function EventCard({ event, onClose }: { event: ScoreEvent; onClose: () => void }) {
  const delta = event.score_after - event.score_before
  const direction = delta > 0 ? 'improved' : delta < 0 ? 'dropped' : 'unchanged'
  const date = new Date(event.created_at * 1000).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  return (
    <div style={{
      marginTop: 12, padding: '12px 14px', borderRadius: 8,
      background: '#fafaf8', border: '1px solid #e5e7eb',
      borderLeft: `3px solid ${delta < 0 ? '#ef4444' : '#22c55e'}`,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>
          {date} — score {direction}: {event.score_before} → {event.score_after}
          {' '}
          <span style={{ color: delta < 0 ? '#ef4444' : '#22c55e', fontWeight: 800 }}>
            ({delta > 0 ? '+' : ''}{delta})
          </span>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 14, color: '#9ca3af',
        }}>×</button>
      </div>
      <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.6 }}>
        <div><strong>Query:</strong> {event.query_preview || '—'}</div>
        <div><strong>Verdict:</strong> {event.verdict}</div>
        <div><strong>Correction stored:</strong> {event.correction_stored ? 'Yes' : 'No'}</div>
        <div style={{ marginTop: 4, color: delta < 0 ? '#ef4444' : '#059669', fontWeight: 600 }}>
          Effect: reliability score {delta > 0 ? '+' : ''}{delta} points
        </div>
      </div>
    </div>
  )
}

export default function LookUnderTheHood({ onClose }: Props) {
  const [histories, setHistories] = useState<ModelHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState<ScoreEvent | null>(null)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      const isElectron = !!(window as any).veritas
      const url = isElectron ? 'http://127.0.0.1:47821/reliability' : '/api/reliability'
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setHistories(data)
      }
    } catch {
      // API not available — show empty state
      setHistories([])
    } finally {
      setLoading(false)
    }
  }

  const MIN_EVENTS = 2

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9998, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, width: '100%', maxWidth: 600,
        maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 20px 14px', borderBottom: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>
              Look under the hood
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 3, lineHeight: 1.5 }}>
              Model reliability scores — how each model has performed for you.
              These are the same scores models see when answering your queries.
            </div>
          </div>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 6, border: '1px solid #e5e7eb',
            background: '#f9fafb', cursor: 'pointer', fontSize: 16, color: '#6b7280',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {loading ? (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>Loading reliability history...</div>
          ) : histories.length === 0 ? (
            <div style={{ color: '#9ca3af', fontSize: 13, lineHeight: 1.6 }}>
              No reliability data yet. Keep chatting — scores build up after each query.
              <br /><br />
              Models need at least 10 queries each before a graph appears.
            </div>
          ) : (
            histories.map(model => {
              const hasGraph = model.events.length >= MIN_EVENTS
              const trendIcon = model.trend === 'up' ? '▲' : model.trend === 'down' ? '▼' : '→'
              const trendColor = model.trend === 'up' ? '#059669' : model.trend === 'down' ? '#ef4444' : '#9ca3af'

              return (
                <div key={model.model_id} style={{ marginBottom: 24 }}>
                  {/* Model header */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>
                      {model.display_name}
                    </span>
                    <span style={{ fontSize: 13, color: '#374151' }}>
                      Current: <strong>{model.current_score}</strong>
                    </span>
                    {hasGraph && (
                      <span style={{ fontSize: 11, color: trendColor, fontWeight: 600 }}>
                        {trendIcon} trending {model.trend}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    <span style={{ fontSize: 11, color: '#9ca3af' }}>
                      {model.events.length} event{model.events.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {hasGraph ? (
                    <>
                      <div style={{
                        background: '#fafaf8', borderRadius: 8, border: '1px solid #e5e7eb',
                        padding: '10px 12px', overflowX: 'auto',
                      }}>
                        <ScoreGraph
                          events={model.events}
                          modelId={model.model_id}
                          onSelectPoint={event => {
                            if (selectedEvent?.audit_id === event?.audit_id && selectedModel === model.model_id) {
                              setSelectedEvent(null)
                              setSelectedModel(null)
                            } else {
                              setSelectedEvent(event)
                              setSelectedModel(model.model_id)
                            }
                          }}
                        />
                        {/* Date labels */}
                        <div style={{
                          display: 'flex', justifyContent: 'space-between',
                          marginTop: 4, padding: '0 8px',
                        }}>
                          {[0, Math.floor(model.events.length / 2), model.events.length - 1]
                            .filter((v, i, a) => a.indexOf(v) === i)
                            .map(i => {
                              const e = model.events[i]
                              if (!e) return null
                              return (
                                <span key={i} style={{ fontSize: 10, color: '#9ca3af' }}>
                                  {new Date(e.created_at * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                </span>
                              )
                            })}
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: '#d1d5db', marginTop: 4 }}>
                        Click any point to see what caused the score change.
                      </div>
                      {selectedEvent && selectedModel === model.model_id && (
                        <EventCard
                          event={selectedEvent}
                          onClose={() => { setSelectedEvent(null); setSelectedModel(null) }}
                        />
                      )}
                    </>
                  ) : (
                    <div style={{
                      padding: '10px 14px', background: '#f9fafb', borderRadius: 8,
                      border: '1px dashed #e5e7eb', fontSize: 12, color: '#9ca3af',
                    }}>
                      Not enough data yet ({model.events.length} of 10 queries needed) — keep chatting to build a reliability history.
                    </div>
                  )}
                </div>
              )
            })
          )}

          {/* Explainer */}
          <div style={{
            marginTop: 8, padding: '12px 14px', background: '#f0f9ff',
            borderRadius: 8, border: '1px solid #bae6fd',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#0369a1', marginBottom: 6 }}>
              How scores work
            </div>
            <div style={{ fontSize: 12, color: '#0c4a6e', lineHeight: 1.6 }}>
              Models are scored on accuracy and calibration — the same way a doctor or analyst builds a track record.
              Scores go up when a model gives correct, well-calibrated answers. Scores go down when peer review catches an error or a correction is contradicted.
              <br /><br />
              Models see their own scores and know they are being evaluated. This gives them an incentive to be honest about uncertainty rather than guessing confidently — which produces better answers.
              <br /><br />
              Scores start building after 2+ events per model. They are private to your device and never shared.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
