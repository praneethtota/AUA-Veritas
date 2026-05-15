// ui/src/api.ts — API client for AUA-Veritas
// Works in both Electron (via IPC relay) and browser (via fetch)

const API_BASE = '/api'

// Detect if running in Electron
const isElectron = typeof window !== 'undefined' && !!(window as any).veritas

async function apiRequest<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  if (isElectron) {
    const result = await (window as any).veritas.apiRequest(method, path, body)
    if (!result.ok) {
      throw new Error(result.error || `API error: ${result.status}`)
    }
    return result.data as T
  }

  // Browser/dev mode — use Vite proxy
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Health ────────────────────────────────────────────────────────────────────

export const health = () => apiRequest<{ status: string; loaded_models: string[] }>('GET', '/health')

// ── Models ────────────────────────────────────────────────────────────────────

export const listModels = () =>
  apiRequest<Record<string, any>>('GET', '/models')

export const testModel = (model_id: string) =>
  apiRequest<{ status: string; model: string; latency_ms: number }>(
    'POST', `/keys/test/${model_id}`
  )

// ── API Keys ──────────────────────────────────────────────────────────────────

export const saveApiKey = (provider: string, api_key: string) =>
  apiRequest<{ saved: boolean; loaded_models: string[] }>('POST', '/keys/save', { provider, api_key })

export const deleteApiKey = (provider: string) =>
  apiRequest<{ deleted: boolean }>('DELETE', `/keys/${provider}`)

export const getKeyStatus = () =>
  apiRequest<Record<string, boolean>>('GET', '/keys/status')

// ── Conversations ─────────────────────────────────────────────────────────────

export const listConversations = () =>
  apiRequest<any[]>('GET', '/conversations')

export const createConversation = (title?: string) =>
  apiRequest<{ conversation_id: string }>('POST', '/conversations', { title: title || 'New Chat' })

export const getMessages = (conversation_id: string) =>
  apiRequest<any[]>('GET', `/conversations/${conversation_id}/messages`)

// ── Query ─────────────────────────────────────────────────────────────────────

export const sendQuery = (payload: {
  query: string
  conversation_id: string
  accuracy_level: string
  enabled_models: string[]
  conversation_history?: any[]
}) => apiRequest<any>('POST', '/query', payload)
