// ui/src/components/Sidebar.tsx — Left panel
// Conversations list (top) + Model checkboxes + Accuracy slider (bottom)

import type { Conversation, AccuracyLevel, ModelInfo } from '../types'

const ACCURACY_LEVELS: { value: AccuracyLevel; label: string; desc: string; cost: string; time: string }[] = [
  { value: 'fast',     label: 'Fast',     desc: '1 model, fastest',            cost: '1×',        time: '+1-2%' },
  { value: 'balanced', label: 'Balanced', desc: '2 models, cross-checked',     cost: '~1.05×',    time: '+12% avg' },
  { value: 'high',     label: 'High',     desc: 'All models, VCG selects best',cost: 'N×',        time: '+5-15%' },
  { value: 'maximum',  label: 'Maximum',  desc: 'All models + peer review',    cost: '~N+0.1×',   time: '+50-70%' },
]

// Provider display names (short)
const PROVIDER_NAMES: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google',
  xai: 'xAI', mistral: 'Mistral', groq: 'Groq', deepseek: 'DeepSeek',
}

interface Props {
  conversations: Conversation[]
  activeConvId: string | null
  models: Record<string, ModelInfo>
  enabledModels: string[]
  accuracy: AccuracyLevel
  sessionCost: number
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onToggleModel: (modelId: string) => void
  onAccuracyChange: (level: AccuracyLevel) => void
}

export default function Sidebar({
  conversations, activeConvId, models, enabledModels,
  accuracy, sessionCost, onSelectConversation, onNewConversation,
  onToggleModel, onAccuracyChange,
}: Props) {
  const enabledCount = enabledModels.length
  const accuracyIdx = ACCURACY_LEVELS.findIndex(a => a.value === accuracy)
  const currentLevel = ACCURACY_LEVELS[accuracyIdx]

  // Models locked above balanced if only 1 connected provider
  const connectedProviders = new Set(
    Object.values(models)
      .filter((m) => enabledModels.includes(m.model_id || (m as any).model_id || ''))
      .map(m => m.provider)
  )

  // Group models by provider
  const providers = Array.from(
    new Set(Object.values(models).map(m => m.provider))
  )

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      background: '#f5f5f2', borderRight: '1px solid #e5e7eb',
      overflow: 'hidden',
    }}>
      {/* App title + new chat */}
      <div style={{
        padding: '16px 14px 12px',
        borderBottom: '1px solid #e5e7eb',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: '#111827', letterSpacing: '-0.02em' }}>
            AUA-Veritas
          </div>
        </div>
        <button onClick={onNewConversation} style={{
          width: '100%', padding: '7px 10px', borderRadius: 7, fontSize: 13, fontWeight: 600,
          background: '#4338ca', color: '#fff', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center',
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
          New chat
        </button>
      </div>

      {/* Conversations list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {conversations.length === 0 ? (
          <div style={{ padding: '12px 14px', fontSize: 12, color: '#9ca3af' }}>
            No conversations yet
          </div>
        ) : (
          conversations.map(conv => (
            <button
              key={conv.conversation_id}
              onClick={() => onSelectConversation(conv.conversation_id)}
              style={{
                width: '100%', textAlign: 'left', padding: '7px 14px',
                background: activeConvId === conv.conversation_id ? '#e8e8f0' : 'transparent',
                border: 'none', cursor: 'pointer', fontSize: 13, color: '#374151',
                borderRadius: 6, margin: '1px 4px', display: 'block',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                maxWidth: 'calc(100% - 8px)',
                transition: 'background 0.1s',
              }}
            >
              {conv.title || 'New Chat'}
            </button>
          ))
        )}
      </div>

      {/* Divider */}
      <div style={{ borderTop: '1px solid #e5e7eb', flexShrink: 0 }} />

      {/* Models section */}
      <div style={{ padding: '10px 14px 8px', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
          Models
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {Object.values(models).filter(m => m.connected && !m.is_cheap_judge).map(model => (
            <label key={model.model_id} style={{
              display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
              padding: '3px 0', fontSize: 13,
            }}>
              <input
                type="checkbox"
                checked={enabledModels.includes(model.model_id)}
                onChange={() => onToggleModel(model.model_id)}
                style={{ accentColor: '#4338ca', width: 13, height: 13 }}
              />
              <span style={{ color: '#374151', flex: 1 }}>{model.display_name}</span>
              <span style={{ fontSize: 10, color: '#9ca3af' }}>
                {PROVIDER_NAMES[model.provider] || model.provider}
              </span>
            </label>
          ))}
          {Object.values(models).filter(m => m.connected).length === 0 && (
            <div style={{ fontSize: 12, color: '#9ca3af' }}>No models connected</div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div style={{ borderTop: '1px solid #e5e7eb', flexShrink: 0 }} />

      {/* Accuracy slider */}
      <div style={{ padding: '10px 14px', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
          Accuracy
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          {ACCURACY_LEVELS.map((level, i) => (
            <button
              key={level.value}
              onClick={() => {
                if (level.value === 'fast' || level.value === 'balanced' || enabledCount >= 2) {
                  onAccuracyChange(level.value)
                }
              }}
              disabled={(level.value === 'high' || level.value === 'maximum') && enabledCount < 2}
              title={
                (level.value === 'high' || level.value === 'maximum') && enabledCount < 2
                  ? 'Add a second provider API key to unlock'
                  : level.desc
              }
              style={{
                flex: 1, padding: '4px 2px', border: 'none', cursor: 'pointer',
                borderRadius: 4, fontSize: 11, fontWeight: accuracy === level.value ? 700 : 400,
                background: accuracy === level.value ? '#4338ca' : 'transparent',
                color: accuracy === level.value
                  ? '#fff'
                  : (level.value === 'high' || level.value === 'maximum') && enabledCount < 2
                    ? '#d1d5db'
                    : '#6b7280',
                transition: 'all 0.15s',
              }}
            >
              {level.label}
            </button>
          ))}
        </div>
        {/* Cost estimate */}
        <div style={{ fontSize: 11, color: '#9ca3af', lineHeight: 1.4 }}>
          {currentLevel.cost} cost · {currentLevel.time} time
          {(currentLevel.value === 'high' || currentLevel.value === 'maximum') && enabledCount < 2 && (
            <span style={{ color: '#f59e0b', marginLeft: 4 }}>
              · needs 2+ providers
            </span>
          )}
        </div>
      </div>

      {/* Session cost */}
      <div style={{
        padding: '8px 14px', borderTop: '1px solid #e5e7eb',
        fontSize: 12, color: '#9ca3af', display: 'flex', justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span>Session cost</span>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>
          ~${sessionCost.toFixed(3)}
        </span>
      </div>
    </div>
  )
}
