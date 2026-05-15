// ui/src/components/SettingsPage.tsx — Settings modal
// Manage API keys, connected models, and projects.

import { useState, useEffect } from 'react'
import { getKeyStatus, saveApiKey, deleteApiKey, testModel, listModels } from '../api'

const PROVIDERS = [
  { id: 'openai',    name: 'OpenAI (ChatGPT)',   helpUrl: 'https://platform.openai.com/api-keys',      keyPrefix: 'sk-proj-' },
  { id: 'anthropic', name: 'Anthropic (Claude)',  helpUrl: 'https://console.anthropic.com/settings/keys', keyPrefix: 'sk-ant-' },
  { id: 'google',    name: 'Google (Gemini)',     helpUrl: 'https://aistudio.google.com/app/apikey',    keyPrefix: 'AIza',  freeNote: 'Free tier available' },
  { id: 'xai',       name: 'xAI (Grok)',          helpUrl: 'https://console.x.ai/api-keys',             keyPrefix: 'xai-' },
  { id: 'mistral',   name: 'Mistral',             helpUrl: 'https://console.mistral.ai/api-keys',       keyPrefix: '' },
  { id: 'groq',      name: 'Groq (Llama)',        helpUrl: 'https://console.groq.com/keys',             keyPrefix: 'gsk_', freeNote: 'Generous free tier' },
  { id: 'deepseek',  name: 'DeepSeek',            helpUrl: 'https://platform.deepseek.com/api_keys',   keyPrefix: 'sk-' },
]

interface Props {
  onClose: () => void
}

export default function SettingsPage({ onClose }: Props) {
  const [keyStatus, setKeyStatus] = useState<Record<string, boolean>>({})
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})
  const [testing, setTesting] = useState<Record<string, 'idle' | 'loading' | 'ok' | 'error'>>({})
  const [removing, setRemoving] = useState<string | null>(null)
  const [models, setModels] = useState<Record<string, any>>({})

  useEffect(() => {
    getKeyStatus().then(setKeyStatus).catch(() => {})
    listModels().then(setModels).catch(() => {})
  }, [])

  const handleTestNew = async (provider: typeof PROVIDERS[0]) => {
    const key = newKeys[provider.id]?.trim()
    if (!key) return
    setTesting(t => ({ ...t, [provider.id]: 'loading' }))
    try {
      await saveApiKey(provider.id, key)
      const providerModels = Object.values(models).filter((m: any) => m.provider === provider.id)
      const testModelId = providerModels[0]?.model_id || provider.id
      const result = await testModel(testModelId)
      const ok = result.status === 'ok'
      setTesting(t => ({ ...t, [provider.id]: ok ? 'ok' : 'error' }))
      if (ok) {
        setKeyStatus(s => ({ ...s, [provider.id]: true }))
        setNewKeys(k => ({ ...k, [provider.id]: '' }))
        await listModels().then(setModels)
      }
    } catch {
      setTesting(t => ({ ...t, [provider.id]: 'error' }))
    }
  }

  const handleRemove = async (providerId: string) => {
    setRemoving(providerId)
    try {
      await deleteApiKey(providerId)
      setKeyStatus(s => ({ ...s, [providerId]: false }))
      await listModels().then(setModels)
    } catch {}
    setRemoving(null)
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9998, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, width: '100%', maxWidth: 520,
        maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 20px 14px', borderBottom: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#111827' }}>Settings</div>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 6, border: '1px solid #e5e7eb',
            background: '#f9fafb', cursor: 'pointer', fontSize: 16, color: '#6b7280',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
            API Keys
          </div>

          {PROVIDERS.map(provider => {
            const connected = keyStatus[provider.id]
            const status = testing[provider.id] || 'idle'

            return (
              <div key={provider.id} style={{
                padding: '12px 14px', borderRadius: 8,
                border: `1px solid ${connected ? '#a7f3d0' : '#e5e7eb'}`,
                background: connected ? '#f0fdf4' : '#fafaf8',
                marginBottom: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: connected ? 0 : 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#111827', flex: 1 }}>
                    {provider.name}
                  </span>
                  {provider.freeNote && (
                    <span style={{
                      fontSize: 10, background: '#ecfdf5', color: '#059669',
                      padding: '2px 6px', borderRadius: 4, fontWeight: 500,
                    }}>
                      Free
                    </span>
                  )}
                  {connected ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 12, color: '#059669', fontWeight: 600 }}>✓ Connected</span>
                      <button
                        onClick={() => handleRemove(provider.id)}
                        disabled={removing === provider.id}
                        style={{
                          padding: '3px 8px', borderRadius: 5, fontSize: 11,
                          background: '#fee2e2', color: '#dc2626',
                          border: 'none', cursor: 'pointer', fontWeight: 500,
                        }}
                      >
                        {removing === provider.id ? '...' : 'Remove'}
                      </button>
                    </div>
                  ) : (
                    <a
                      href={provider.helpUrl}
                      target="_blank"
                      onClick={e => {
                        e.preventDefault()
                        if ((window as any).veritas?.openExternal) {
                          (window as any).veritas.openExternal(provider.helpUrl)
                        } else {
                          window.open(provider.helpUrl)
                        }
                      }}
                      style={{ fontSize: 11, color: '#4338ca' }}
                    >
                      Get key →
                    </a>
                  )}
                </div>

                {!connected && (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      type="password"
                      placeholder={`${provider.keyPrefix || 'API key'}...`}
                      value={newKeys[provider.id] || ''}
                      onChange={e => setNewKeys(k => ({ ...k, [provider.id]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && handleTestNew(provider)}
                      style={{
                        flex: 1, padding: '6px 8px', borderRadius: 6, fontSize: 12,
                        border: `1px solid ${status === 'error' ? '#fca5a5' : '#e5e7eb'}`,
                        outline: 'none', background: '#fff', fontFamily: 'monospace',
                      }}
                    />
                    <button
                      onClick={() => handleTestNew(provider)}
                      disabled={!newKeys[provider.id]?.trim() || status === 'loading'}
                      style={{
                        padding: '6px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                        background: '#4338ca', color: '#fff', border: 'none',
                        cursor: newKeys[provider.id]?.trim() ? 'pointer' : 'default',
                        opacity: newKeys[provider.id]?.trim() ? 1 : 0.5,
                      }}
                    >
                      {status === 'loading' ? '...' : status === 'error' ? 'Invalid' : 'Connect'}
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 12, lineHeight: 1.5 }}>
            API keys are stored in your system keychain and never uploaded.
          </div>
        </div>
      </div>
    </div>
  )
}
