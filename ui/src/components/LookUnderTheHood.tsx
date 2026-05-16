// ui/src/components/LookUnderTheHood.tsx
// Full analytics dashboard for technical users.
// 4 tabs: Overview · Models · Decisions · Memory
// Accessed via 🔩 button in QualityPanel — discoverable by curious users only.

import { useState, useEffect } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ModelStat {
  model_id: string
  display_name: string
  connected: boolean
  is_judge: boolean
  reliability_score: number
  trend: 'up' | 'down' | 'flat'
  total_runs: number
  winner_count: number
  win_rate_pct: number
  avg_latency_ms: number | null
  avg_welfare_score: number | null
  score_events: ScoreEvent[]
}

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

interface Decision {
  query_id: string
  created_at: number
  winner_model: string
  all_models: string[]
  confidence_score: number | null
  vcg_welfare_score: number | null
  latency_ms: number | null
  corrections_applied: { type: string; scope: string; instruction: string }[]
  peer_review: boolean
}

interface Analytics {
  models: ModelStat[]
  confidence_dist: { high: number; medium: number; uncertain: number; total: number }
  correction_stats: { total_active: number; by_type: Record<string, number>; by_domain: Record<string, number> }
  domain_dist: Record<string, number>
  recent_decisions: Decision[]
  welfare_summary: { avg: number | null; max: number | null; min: number | null; total_scored: number }
  total_conversations: number
  total_model_runs: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const BASE = () => (window as any).veritas ? 'http://127.0.0.1:47821' : '/api'

const ACCENT = '#4338ca'
const SURFACE = '#fafaf8'
const BORDER = '#e5e7eb'

const CONF_COLORS = { high: '#059669', medium: '#f59e0b', uncertain: '#ef4444' }
const TREND_ICON  = { up: '▲', down: '▼', flat: '→' }
const TREND_COLOR = { up: '#059669', down: '#ef4444', flat: '#9ca3af' }

const TYPE_LABELS: Record<string, string> = {
  factual_correction:     'Factual fix',
  persistent_instruction: 'Instruction',
  project_decision:       'Decision',
  preference:             'Preference',
  failure_pattern:        'Failure pattern',
}

function pct(n: number, total: number) { return total ? Math.round(n / total * 100) : 0 }
function fmt(ms: number | null) { return ms != null ? `${ms.toFixed(0)} ms` : '—' }
function score(s: number | null) { return s != null ? s.toFixed(3) : '—' }
function confLabel(cs: number | null): 'high' | 'medium' | 'uncertain' {
  if (cs == null) return 'uncertain'
  if (cs >= 0.75) return 'high'
  if (cs >= 0.50) return 'medium'
  return 'uncertain'
}

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({ events, width = 120, height = 32 }: { events: ScoreEvent[]; width?: number; height?: number }) {
  if (events.length < 2) return <span style={{ color: '#d1d5db', fontSize: 11 }}>no data</span>
  const scores = events.map(e => e.score_after)
  const lo = Math.max(0, Math.min(...scores) - 3)
  const hi = Math.min(100, Math.max(...scores) + 3)
  const range = hi - lo || 10
  const pad = 4
  const x = (i: number) => pad + (i / (scores.length - 1)) * (width - pad * 2)
  const y = (s: number) => height - pad - ((s - lo) / range) * (height - pad * 2)
  const d = scores.map((s, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(s).toFixed(1)}`).join(' ')
  const last = events[events.length - 1]
  const delta = last.score_after - last.score_before
  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <path d={d} fill="none" stroke={delta >= 0 ? ACCENT : '#ef4444'} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={x(scores.length - 1)} cy={y(scores[scores.length - 1])} r={3}
        fill={delta >= 0 ? ACCENT : '#ef4444'} />
    </svg>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      padding: '14px 16px', borderRadius: 10, background: '#fff',
      border: `1px solid ${BORDER}`, minWidth: 110,
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color || '#111827', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfBar({ dist }: { dist: Analytics['confidence_dist'] }) {
  const total = dist.total || 1
  const segments = [
    { key: 'high',      label: 'High',      color: CONF_COLORS.high,      n: dist.high },
    { key: 'medium',    label: 'Medium',     color: CONF_COLORS.medium,    n: dist.medium },
    { key: 'uncertain', label: 'Uncertain',  color: CONF_COLORS.uncertain, n: dist.uncertain },
  ] as const

  return (
    <div>
      <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', marginBottom: 8 }}>
        {segments.map(s => (
          <div key={s.key} style={{
            width: `${pct(s.n, total)}%`, background: s.color,
            transition: 'width 0.4s ease',
          }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14 }}>
        {segments.map(s => (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
            <span style={{ fontSize: 11, color: '#6b7280' }}>{s.label} {pct(s.n, total)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Score ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score, size = 48 }: { score: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const filled = circ * (score / 100)
  const color = score >= 75 ? '#059669' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <svg width={size} height={size}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f3f4f6" strokeWidth={6} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={`${filled} ${circ - filled}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x={size / 2} y={size / 2 + 4} textAnchor="middle"
        style={{ fontSize: 11, fontWeight: 700, fill: color, fontVariantNumeric: 'tabular-nums' }}>
        {score}
      </text>
    </svg>
  )
}

// ── Tab ───────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'models' | 'decisions' | 'memory'
const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'overview',  label: 'Overview',  icon: '◈' },
  { id: 'models',    label: 'Models',    icon: '⚖' },
  { id: 'decisions', label: 'Decisions', icon: '⛓' },
  { id: 'memory',    label: 'Memory',    icon: '🧠' },
]

// ── Overview tab ──────────────────────────────────────────────────────────────

function OverviewTab({ data }: { data: Analytics }) {
  const total = data.total_model_runs
  const answered = data.confidence_dist.total

  const topModel = data.models.filter(m => !m.is_judge && m.total_runs > 0)
    .sort((a, b) => b.reliability_score - a.reliability_score)[0]

  const correctionTypes = Object.entries(data.correction_stats.by_type)
  const domainEntries = Object.entries(data.domain_dist).sort((a, b) => b[1] - a[1]).slice(0, 5)
  const maxDomain = Math.max(...domainEntries.map(d => d[1]), 1)

  return (
    <div style={{ padding: '18px 20px' }}>
      {/* Stat row */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        <StatCard label="Queries answered" value={answered} sub={`of ${total} model runs`} />
        <StatCard label="Conversations"    value={data.total_conversations} />
        <StatCard label="Corrections saved" value={data.correction_stats.total_active} />
        <StatCard label="Top model score"  value={topModel ? topModel.reliability_score : '—'}
          sub={topModel?.display_name} color={ACCENT} />
        <StatCard label="Avg welfare score" value={data.welfare_summary.avg != null ? data.welfare_summary.avg.toFixed(3) : '—'}
          sub="VCG W = P(domain) × conf × prior" />
      </div>

      {/* Confidence distribution */}
      <Section title="Confidence distribution" sub={`across ${answered} answered queries`}>
        <ConfBar dist={data.confidence_dist} />
      </Section>

      {/* Correction breakdown */}
      {correctionTypes.length > 0 && (
        <Section title="Correction memory breakdown" sub="types of corrections stored">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {correctionTypes.map(([type, count]) => (
              <div key={type} style={{
                padding: '6px 12px', borderRadius: 20,
                background: '#ede9fe', fontSize: 12, color: '#5b21b6', fontWeight: 600,
              }}>
                {TYPE_LABELS[type] || type}: {count}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Domain activity */}
      {domainEntries.length > 0 && (
        <Section title="Domain activity" sub="which topic areas you query most">
          {domainEntries.map(([domain, count]) => (
            <div key={domain} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 12, color: '#374151', textTransform: 'capitalize' }}>{domain.replace(/_/g, ' ')}</span>
                <span style={{ fontSize: 12, color: '#9ca3af' }}>{count}</span>
              </div>
              <div style={{ height: 4, background: '#f3f4f6', borderRadius: 2 }}>
                <div style={{
                  height: '100%', borderRadius: 2, background: ACCENT,
                  width: `${pct(count, maxDomain)}%`, transition: 'width 0.4s ease',
                }} />
              </div>
            </div>
          ))}
        </Section>
      )}

      {/* VCG summary */}
      {data.welfare_summary.avg != null && (
        <Section title="VCG welfare scores" sub="higher = stronger confidence in the selected answer">
          <div style={{ display: 'flex', gap: 16 }}>
            {[
              { label: 'Average', value: score(data.welfare_summary.avg) },
              { label: 'Highest', value: score(data.welfare_summary.max) },
              { label: 'Lowest',  value: score(data.welfare_summary.min) },
              { label: 'Scored',  value: `${data.welfare_summary.total_scored} runs` },
            ].map(s => (
              <div key={s.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#111827', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
                <div style={{ fontSize: 11, color: '#9ca3af' }}>{s.label}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 10, fontSize: 11, color: '#9ca3af', lineHeight: 1.5 }}>
            Formula: W = P(domain) × confidence × prior_score. Models with higher domain specialisation and reliability get higher welfare scores and are more likely to win the VCG selection.
          </div>
        </Section>
      )}
    </div>
  )
}

// ── Models tab ────────────────────────────────────────────────────────────────

function ModelsTab({ data }: { data: Analytics }) {
  const [selectedEvent, setSelectedEvent] = useState<ScoreEvent | null>(null)
  const [selectedMid, setSelectedMid]     = useState<string | null>(null)

  const mainModels = data.models.filter(m => !m.is_judge)

  return (
    <div style={{ padding: '18px 20px' }}>
      {mainModels.map(model => (
        <div key={model.model_id} style={{
          marginBottom: 20, padding: '14px 16px', borderRadius: 10,
          border: `1px solid ${BORDER}`, background: '#fff',
        }}>
          {/* Model header row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <ScoreRing score={model.reliability_score} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', display: 'flex', alignItems: 'center', gap: 8 }}>
                {model.display_name}
                {model.connected
                  ? <span style={{ fontSize: 10, background: '#d1fae5', color: '#065f46', padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>connected</span>
                  : <span style={{ fontSize: 10, background: '#f3f4f6', color: '#9ca3af', padding: '1px 6px', borderRadius: 4 }}>not connected</span>
                }
              </div>
              <div style={{ fontSize: 12, color: TREND_COLOR[model.trend], fontWeight: 600, marginTop: 2 }}>
                {TREND_ICON[model.trend]} {model.trend === 'up' ? 'Improving' : model.trend === 'down' ? 'Declining' : 'Stable'}
              </div>
            </div>
            <Sparkline events={model.score_events} width={100} height={30} />
          </div>

          {/* Stats grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {[
              { label: 'Reliability',   value: `${model.reliability_score}/100` },
              { label: 'Win rate',      value: model.total_runs ? `${model.win_rate_pct}%` : '—' },
              { label: 'Avg latency',   value: fmt(model.avg_latency_ms) },
              { label: 'Avg welfare',   value: score(model.avg_welfare_score) },
              { label: 'Total runs',    value: model.total_runs },
              { label: 'Times selected', value: model.winner_count },
              { label: 'Score events',  value: model.score_events.length },
            ].map(s => (
              <div key={s.label} style={{ padding: '6px 8px', background: SURFACE, borderRadius: 6 }}>
                <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 2 }}>{s.label}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#374151', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Score event list — clickable */}
          {model.score_events.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>
                Score history — click a row for details
              </div>
              <div style={{ maxHeight: 140, overflowY: 'auto' }}>
                {[...model.score_events].reverse().map(ev => {
                  const delta = ev.score_after - ev.score_before
                  const isSelected = selectedEvent?.audit_id === ev.audit_id && selectedMid === model.model_id
                  return (
                    <div
                      key={ev.audit_id}
                      onClick={() => {
                        if (isSelected) { setSelectedEvent(null); setSelectedMid(null) }
                        else { setSelectedEvent(ev); setSelectedMid(model.model_id) }
                      }}
                      style={{
                        display: 'flex', gap: 8, alignItems: 'center',
                        padding: '4px 8px', borderRadius: 5, marginBottom: 2,
                        background: isSelected ? '#ede9fe' : 'transparent',
                        cursor: 'pointer', fontSize: 12,
                      }}
                    >
                      <span style={{
                        minWidth: 36, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                        color: delta > 0 ? '#059669' : delta < 0 ? '#ef4444' : '#9ca3af',
                      }}>
                        {delta > 0 ? '+' : ''}{delta}
                      </span>
                      <span style={{ color: '#374151' }}>
                        {ev.score_before} → {ev.score_after}
                      </span>
                      <span style={{ color: '#9ca3af', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {ev.query_preview || ev.verdict}
                      </span>
                      <span style={{ color: '#d1d5db', flexShrink: 0, fontSize: 10 }}>
                        {new Date(ev.created_at * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )
                })}
              </div>
              {selectedEvent && selectedMid === model.model_id && (
                <div style={{
                  marginTop: 8, padding: '10px 12px', borderRadius: 7,
                  background: SURFACE, border: `1px solid ${BORDER}`,
                  borderLeft: `3px solid ${selectedEvent.score_after >= selectedEvent.score_before ? '#059669' : '#ef4444'}`,
                  fontSize: 12, color: '#374151', lineHeight: 1.6,
                }}>
                  <strong>Verdict:</strong> {selectedEvent.verdict} ·{' '}
                  <strong>Correction stored:</strong> {selectedEvent.correction_stored ? 'Yes' : 'No'}
                  {selectedEvent.query_preview && <><br /><strong>Query:</strong> {selectedEvent.query_preview}</>}
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {/* Judge models — collapsed */}
      {data.models.filter(m => m.is_judge && m.connected).length > 0 && (
        <Section title="Judge models (cheap cross-checkers)" sub="used for peer review and balanced-mode cross-checks">
          {data.models.filter(m => m.is_judge && m.connected).map(m => (
            <div key={m.model_id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '6px 0', borderBottom: `1px solid ${BORDER}`, fontSize: 13,
            }}>
              <span style={{ color: '#374151', flex: 1 }}>{m.display_name}</span>
              <span style={{ color: '#9ca3af' }}>{m.total_runs} runs</span>
            </div>
          ))}
        </Section>
      )}

      {/* How scores work */}
      <Explainer title="How reliability scores work">
        Models start at 70/100. Scores go up when peer review confirms their answer, down when a correction contradicts them. Models see their own score in their system prompt — this creates an incentive to be honest about uncertainty rather than confidently wrong.
      </Explainer>
    </div>
  )
}

// ── Decisions tab ─────────────────────────────────────────────────────────────

function DecisionsTab({ data, modelMap }: { data: Analytics; modelMap: Record<string, string> }) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (data.recent_decisions.length === 0) {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
        No query decisions recorded yet. Start chatting to see the decision trace here.
      </div>
    )
  }

  return (
    <div style={{ padding: '18px 20px' }}>
      <Explainer title="What is a decision trace?">
        Each query goes through: domain classification → correction retrieval → model calls → VCG welfare scoring → winner selection → optional peer review. This tab shows that chain for your last 15 queries.
      </Explainer>

      {data.recent_decisions.map((d, i) => {
        const cl = confLabel(d.confidence_score)
        const isExp = expanded === d.query_id
        return (
          <div key={d.query_id} style={{
            marginBottom: 8, borderRadius: 9, border: `1px solid ${BORDER}`,
            background: '#fff', overflow: 'hidden',
          }}>
            {/* Header row */}
            <div
              onClick={() => setExpanded(isExp ? null : d.query_id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', cursor: 'pointer',
              }}
            >
              <span style={{
                minWidth: 24, height: 24, borderRadius: 5,
                background: '#f3f4f6', color: '#6b7280', fontSize: 11, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>{data.recent_decisions.length - i}</span>

              {/* Models used */}
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {d.all_models.map(mid => (
                  <span key={mid} style={{
                    padding: '2px 6px', borderRadius: 4, fontSize: 11,
                    background: mid === d.winner_model ? ACCENT : '#f3f4f6',
                    color: mid === d.winner_model ? '#fff' : '#6b7280',
                    fontWeight: mid === d.winner_model ? 700 : 400,
                  }}>
                    {modelMap[mid] || mid}
                    {mid === d.winner_model && ' ✓'}
                  </span>
                ))}
              </div>

              <span style={{ flex: 1 }} />

              {/* Confidence pill */}
              <span style={{
                padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                background: cl === 'high' ? '#d1fae5' : cl === 'medium' ? '#fef3c7' : '#fee2e2',
                color: CONF_COLORS[cl],
              }}>
                {cl}
              </span>

              {d.peer_review && (
                <span style={{ fontSize: 10, color: '#9ca3af' }}>+ peer review</span>
              )}

              <span style={{ fontSize: 11, color: '#d1d5db' }}>{isExp ? '▲' : '▼'}</span>
            </div>

            {/* Expanded detail */}
            {isExp && (
              <div style={{
                borderTop: `1px solid ${BORDER}`,
                padding: '12px 14px', background: SURFACE,
                fontSize: 12, color: '#374151',
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
                  {[
                    { label: 'Latency',       value: fmt(d.latency_ms) },
                    { label: 'Welfare score', value: score(d.vcg_welfare_score) },
                    { label: 'Confidence',    value: d.confidence_score != null ? (d.confidence_score * 100).toFixed(0) + '%' : '—' },
                    { label: 'Winner',        value: modelMap[d.winner_model] || d.winner_model },
                    { label: 'Models called', value: d.all_models.length },
                    { label: 'Peer review',   value: d.peer_review ? 'Yes' : 'No' },
                  ].map(s => (
                    <div key={s.label} style={{ background: '#fff', borderRadius: 6, padding: '6px 10px', border: `1px solid ${BORDER}` }}>
                      <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 2 }}>{s.label}</div>
                      <div style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
                    </div>
                  ))}
                </div>

                {/* Decision chain */}
                <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>Decision chain</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {[
                    { step: '1', label: 'Correction check', detail: d.corrections_applied.length > 0 ? 'correction signal detected' : 'no correction signal', ok: true },
                    { step: '2', label: 'Memory retrieved',  detail: d.corrections_applied.length > 0 ? `${d.corrections_applied.length} correction(s) injected` : 'no relevant memories', ok: d.corrections_applied.length > 0 },
                    { step: '3', label: 'Models called',     detail: d.all_models.map(m => modelMap[m] || m).join(' · '), ok: true },
                    { step: '4', label: 'VCG selection',     detail: `${modelMap[d.winner_model] || d.winner_model} selected (W = ${score(d.vcg_welfare_score)})`, ok: true },
                    { step: '5', label: 'Peer review',       detail: d.peer_review ? 'conducted — cross-model check' : 'skipped (Fast or Balanced mode)', ok: d.peer_review },
                    { step: '6', label: 'Confidence label',  detail: `${cl.charAt(0).toUpperCase() + cl.slice(1)} (${d.confidence_score != null ? (d.confidence_score * 100).toFixed(0) : '?'}%)`, ok: cl !== 'uncertain' },
                  ].map(step => (
                    <div key={step.step} style={{
                      display: 'flex', gap: 8, alignItems: 'flex-start',
                      padding: '5px 8px', borderRadius: 5, background: '#fff',
                      border: `1px solid ${BORDER}`,
                    }}>
                      <span style={{
                        minWidth: 18, height: 18, borderRadius: 4,
                        background: ACCENT, color: '#fff', fontSize: 10, fontWeight: 700,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>{step.step}</span>
                      <span style={{ fontWeight: 600, color: '#374151', minWidth: 110 }}>{step.label}</span>
                      <span style={{ color: '#6b7280', flex: 1 }}>{step.detail}</span>
                    </div>
                  ))}
                </div>

                {/* Corrections applied */}
                {d.corrections_applied.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 5 }}>Corrections injected into prompt</div>
                    {d.corrections_applied.map((c, ci) => (
                      <div key={ci} style={{
                        padding: '5px 10px', borderRadius: 5, background: '#fffbeb',
                        border: '1px solid #fde68a', fontSize: 11, color: '#92400e', marginBottom: 4,
                      }}>
                        <span style={{ fontWeight: 700, marginRight: 6 }}>[{TYPE_LABELS[c.type] || c.type}]</span>
                        {c.instruction}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Memory tab ────────────────────────────────────────────────────────────────

function MemoryTab({ data }: { data: Analytics }) {
  const types = Object.keys(data.correction_stats.by_type)
  const [filter, setFilter] = useState<string>('all')

  // Fetch corrections list from /memory endpoint
  const [corrections, setCorrections] = useState<any[]>([])
  useEffect(() => {
    fetch(`${BASE()}/memory`).then(r => r.json()).then(setCorrections).catch(() => {})
  }, [])

  const filtered = filter === 'all' ? corrections : corrections.filter(c => c.type === filter)

  return (
    <div style={{ padding: '18px 20px' }}>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <StatCard label="Active memories" value={data.correction_stats.total_active} />
        {Object.entries(data.correction_stats.by_domain).map(([d, n]) => (
          <StatCard key={d} label={d.replace(/_/g, ' ')} value={n} />
        ))}
      </div>

      {/* Filter */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {['all', ...types].map(t => (
          <button key={t} onClick={() => setFilter(t)} style={{
            padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: filter === t ? 700 : 400,
            background: filter === t ? ACCENT : '#f3f4f6',
            color: filter === t ? '#fff' : '#6b7280',
            border: 'none', cursor: 'pointer',
          }}>
            {t === 'all' ? 'All' : TYPE_LABELS[t] || t}
          </button>
        ))}
      </div>

      {/* Correction list */}
      {filtered.length === 0 ? (
        <div style={{ color: '#9ca3af', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
          No corrections stored yet.
        </div>
      ) : filtered.map(c => (
        <div key={c.correction_id} style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 8,
          background: '#fff', border: `1px solid ${BORDER}`,
        }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: '#ede9fe', color: '#5b21b6', fontWeight: 700,
            }}>{TYPE_LABELS[c.type] || c.type}</span>
            <span style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: '#f3f4f6', color: '#6b7280',
            }}>{c.scope}</span>
            <span style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: '#f0fdf4', color: '#065f46',
            }}>{c.domain}</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 10, color: '#d1d5db' }}>
              confidence: {c.confidence != null ? (c.confidence * 100).toFixed(0) + '%' : '—'}
            </span>
            <span style={{ fontSize: 10, color: '#d1d5db' }}>
              {new Date(c.created_at * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.5 }}>
            {c.corrective_instruction}
          </div>
          {c.canonical_query && (
            <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4 }}>
              topic key: {c.canonical_query.replace(/_/g, ' ')}
            </div>
          )}
        </div>
      ))}

      <Explainer title="How memory injection works">
        Before every query, Veritas scores each stored correction against the current question using 8 factors: relevance, failure prevention value, importance, recency, confidence, pinned status, staleness, and token cost. Only corrections scoring above 0.30 are injected. The formula prevents the prompt from becoming a memory dump.
      </Explainer>
    </div>
  )
}

// ── Section + Explainer helpers ───────────────────────────────────────────────

function Section({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 2 }}>{title}</div>
      {sub && <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>{sub}</div>}
      {children}
    </div>
  )
}

function Explainer({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{
      marginBottom: 16, borderRadius: 8,
      border: '1px solid #bae6fd', background: '#f0f9ff',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '8px 12px', background: 'transparent', border: 'none', cursor: 'pointer',
          fontSize: 12, fontWeight: 600, color: '#0369a1',
        }}
      >
        {title}
        <span style={{ fontSize: 10, color: '#7dd3fc' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 12px 10px', fontSize: 12, color: '#0c4a6e', lineHeight: 1.7 }}>
          {children}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props { onClose: () => void }

export default function LookUnderTheHood({ onClose }: Props) {
  const [tab, setTab]         = useState<Tab>('overview')
  const [data, setData]       = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    fetch(`${BASE()}/analytics`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setData)
      .catch(e => setError(`Failed to load analytics (${e})`))
      .finally(() => setLoading(false))
  }, [])

  // Build model_id → display_name map
  const modelMap: Record<string, string> = {}
  data?.models.forEach(m => { modelMap[m.model_id] = m.display_name })

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9998, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        width: '100%', maxWidth: 780,
        maxHeight: '90vh', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px 0', borderBottom: `1px solid ${BORDER}`,
          display: 'flex', alignItems: 'flex-end', gap: 16,
        }}>
          <div style={{ paddingBottom: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#111827', letterSpacing: '-0.01em' }}>
              Look under the hood
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
              Full analytics — model scoring, decision traces, memory
            </div>
          </div>

          <div style={{ display: 'flex', gap: 2, flex: 1 }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: '8px 14px', fontSize: 13, fontWeight: tab === t.id ? 700 : 400,
                color: tab === t.id ? ACCENT : '#9ca3af',
                border: 'none', background: 'transparent', cursor: 'pointer',
                borderBottom: tab === t.id ? `2px solid ${ACCENT}` : '2px solid transparent',
                marginBottom: -1, transition: 'all 0.15s',
              }}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 7, border: `1px solid ${BORDER}`,
            background: '#f9fafb', cursor: 'pointer', fontSize: 16, color: '#6b7280',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 12, flexShrink: 0,
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
              Loading analytics...
            </div>
          ) : error ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#ef4444', fontSize: 13 }}>
              {error}
            </div>
          ) : data ? (
            <>
              {tab === 'overview'  && <OverviewTab  data={data} />}
              {tab === 'models'    && <ModelsTab    data={data} />}
              {tab === 'decisions' && <DecisionsTab data={data} modelMap={modelMap} />}
              {tab === 'memory'    && <MemoryTab    data={data} />}
            </>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
              No data yet — start chatting to build your analytics.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
