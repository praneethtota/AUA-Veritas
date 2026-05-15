// ui/src/components/SetupScreen.tsx — First-launch API key setup

import { useState } from 'react'
import { saveApiKey, testModel } from '../api'

interface Provider {
  id: string
  name: string
  keyPrefix: string
  models: string[]
  freeNote?: string
  helpUrl: string
  keyName: string
}

const PROVIDERS: Provider[] = [
  {
    id: 'openai', name: 'ChatGPT (OpenAI)', keyPrefix: 'sk-proj-',
    models: ['gpt-4o', 'gpt-4o-mini'], keyName: 'OPENAI_API_KEY',
    helpUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'anthropic', name: 'Claude (Anthropic)', keyPrefix: 'sk-ant-',
    models: ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001'], keyName: 'ANTHROPIC_API_KEY',
    helpUrl: 'https://console.anthropic.com/settings/keys',
  },
  {
    id: 'google', name: 'Gemini (Google)', keyPrefix: 'AIza',
    models: ['gemini-1.5-pro', 'gemini-2.0-flash'], keyName: 'GOOGLE_API_KEY',
    freeNote: 'Free tier available — no credit card needed',
    helpUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'xai', name: 'Grok (xAI)', keyPrefix: 'xai-',
    models: ['grok-2'], keyName: 'XAI_API_KEY',
    helpUrl: 'https://console.x.ai/api-keys',
  },
  {
    id: 'mistral', name: 'Mistral', keyPrefix: '',
    models: ['mistral-large-latest'], keyName: 'MISTRAL_API_KEY',
    helpUrl: 'https://console.mistral.ai/api-keys',
  },
  {
    id: 'groq', name: 'Llama via Groq', keyPrefix: 'gsk_',
    models: ['llama-3.3-70b-versatile'], keyName: 'GROQ_API_KEY',
    freeNote: 'Generous free tier — no credit card needed',
    helpUrl: 'https://console.groq.com/keys',
  },
  {
    id: 'deepseek', name: 'DeepSeek', keyPrefix: 'sk-',
    models: ['deepseek-chat'], keyName: 'DEEPSEEK_API_KEY',
    helpUrl: 'https://platform.deepseek.com/api_keys',
  },
]

interface Props { onComplete: () => void }

export default function SetupScreen({ onComplete }: Props) {
  const [keys, setKeys] = useState<Record<string, string>>({})
  const [testing, setTesting] = useState<Record<string, 'idle' | 'loading' | 'ok' | 'error'>>({})
  const [saving, setSaving] = useState(false)
  const [helpOpen, setHelpOpen] = useState<string | null>(null)
  const [projectName, setProjectName] = useState('My Project')
  const [error, setError] = useState('')

  const connectedCount = Object.values(testing).filter(s => s === 'ok').length

  const testKey = async (provider: Provider) => {
    const key = keys[provider.id]
    if (!key?.trim()) return
    setTesting(t => ({ ...t, [provider.id]: 'loading' }))
    try {
      await saveApiKey(provider.id, key.trim())
      const model = provider.models[0]
      const result = await testModel(model)
      setTesting(t => ({ ...t, [provider.id]: result.status === 'ok' ? 'ok' : 'error' }))
    } catch {
      setTesting(t => ({ ...t, [provider.id]: 'error' }))
    }
  }

  const handleStart = async () => {
    if (connectedCount === 0) {
      setError('Connect at least one AI model to get started.')
      return
    }
    setSaving(true)
    // Save any untested keys
    for (const p of PROVIDERS) {
      const key = keys[p.id]
      if (key?.trim() && testing[p.id] !== 'ok') {
        try { await saveApiKey(p.id, key.trim()) } catch {}
      }
    }
    onComplete()
  }

  return (
    <div style={{
      height: '100vh', overflow: 'auto', background: '#fafaf8',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 32,
    }}>
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#1a1a1a', marginBottom: 8 }}>
            AUA-Veritas
          </div>
          <div style={{ fontSize: 15, color: '#6b7280', lineHeight: 1.5 }}>
            Connect your AI models. Your keys are stored on this device only — never in the cloud.
          </div>
        </div>

        {/* Providers */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
          {PROVIDERS.map(provider => {
            const status = testing[provider.id] || 'idle'
            const hasKey = !!(keys[provider.id]?.trim())
            return (
              <div key={provider.id} style={{
                background: '#fff', borderRadius: 10, padding: '12px 16px',
                border: `1px solid ${status === 'ok' ? '#6ee7b7' : status === 'error' ? '#fca5a5' : '#e5e7eb'}`,
                transition: 'border-color 0.2s',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 14, flex: 1, color: '#111827' }}>
                    {provider.name}
                  </span>
                  {status === 'ok' && (
                    <span style={{ fontSize: 12, color: '#059669', fontWeight: 600 }}>✓ Connected</span>
                  )}
                  {status === 'error' && (
                    <span style={{ fontSize: 12, color: '#dc2626' }}>✗ Invalid key</span>
                  )}
                  {provider.freeNote && (
                    <span style={{
                      fontSize: 11, background: '#ecfdf5', color: '#059669',
                      padding: '2px 6px', borderRadius: 4, fontWeight: 500,
                    }}>
                      Free
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="password"
                    placeholder={`${provider.keyPrefix}...`}
                    value={keys[provider.id] || ''}
                    onChange={e => setKeys(k => ({ ...k, [provider.id]: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && testKey(provider)}
                    style={{
                      flex: 1, padding: '7px 10px', borderRadius: 6, fontSize: 13,
                      border: '1px solid #e5e7eb', outline: 'none', fontFamily: 'monospace',
                      background: '#fafaf8',
                    }}
                  />
                  <button
                    onClick={() => testKey(provider)}
                    disabled={!hasKey || status === 'loading'}
                    style={{
                      padding: '7px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                      border: '1px solid #e5e7eb', background: '#fff', cursor: hasKey ? 'pointer' : 'default',
                      color: hasKey ? '#4338ca' : '#9ca3af', transition: 'all 0.15s',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {status === 'loading' ? '...' : 'Test'}
                  </button>
                  <button
                    onClick={() => setHelpOpen(helpOpen === provider.id ? null : provider.id)}
                    title="How to get this API key"
                    style={{
                      width: 32, height: 32, borderRadius: 6, border: '1px solid #e5e7eb',
                      background: '#fff', cursor: 'pointer', fontSize: 14, color: '#6b7280',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >?</button>
                </div>
                {helpOpen === provider.id && (
                  <div style={{
                    marginTop: 10, padding: 12, background: '#f3f4f6', borderRadius: 8,
                    fontSize: 13, lineHeight: 1.6, color: '#374151',
                  }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>
                      How to get your {provider.name} API key:
                    </div>
                    <ol style={{ paddingLeft: 18, marginBottom: 8 }}>
                      <li>Go to <a href={provider.helpUrl} target="_blank" style={{ color: '#4338ca' }}
                          onClick={e => { e.preventDefault(); (window as any).veritas?.openExternal(provider.helpUrl) || window.open(provider.helpUrl) }}>
                          {provider.helpUrl}
                        </a></li>
                      <li>Sign in or create a free account</li>
                      <li>Create a new API key</li>
                      <li>Copy it and paste it above</li>
                    </ol>
                    {provider.freeNote && (
                      <div style={{ color: '#059669', fontSize: 12, fontWeight: 500 }}>
                        ✓ {provider.freeNote}
                      </div>
                    )}
                    <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>
                      Your key starts with: <code>{provider.keyPrefix || 'varies'}</code>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Project name */}
        <div style={{
          background: '#fff', borderRadius: 10, padding: '14px 16px',
          border: '1px solid #e5e7eb', marginBottom: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#111827', marginBottom: 8 }}>
            Name your first project
          </div>
          <input
            type="text"
            value={projectName}
            onChange={e => setProjectName(e.target.value)}
            placeholder="My Project"
            style={{
              width: '100%', padding: '8px 10px', borderRadius: 6, fontSize: 14,
              border: '1px solid #e5e7eb', outline: 'none', background: '#fafaf8',
            }}
          />
        </div>

        {error && (
          <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>
            {error}
          </div>
        )}

        {/* Start button */}
        <button
          onClick={handleStart}
          disabled={saving}
          style={{
            width: '100%', padding: '12px', borderRadius: 10, fontSize: 15, fontWeight: 700,
            background: connectedCount > 0 ? '#4338ca' : '#d1d5db',
            color: connectedCount > 0 ? '#fff' : '#9ca3af',
            border: 'none', cursor: connectedCount > 0 ? 'pointer' : 'default',
            transition: 'all 0.2s',
          }}
        >
          {saving ? 'Setting up...' : connectedCount > 0
            ? `Start chatting →  (${connectedCount} model${connectedCount !== 1 ? 's' : ''} connected)`
            : 'Connect at least one model to continue'}
        </button>

        <div style={{ textAlign: 'center', marginTop: 16, fontSize: 12, color: '#9ca3af' }}>
          API keys are stored in your system keychain, never uploaded.
        </div>
      </div>
    </div>
  )
}
