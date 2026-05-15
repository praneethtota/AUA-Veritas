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

export const health = () =>
  apiRequest<{ status: string; loaded_models: string[] }>('GET', '/health')

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

// ── Streaming query (Fast mode only) ──────────────────────────────────────────
// Uses SSE — yields token strings as they arrive, then a final JSON envelope.

export async function* streamQuery(payload: {
  query: string
  conversation_id: string
  enabled_models: string[]
  conversation_history?: any[]
}): AsyncGenerator<{ type: 'token'; text: string } | { type: 'done'; response: any }> {
  const url = isElectron
    ? `http://127.0.0.1:47821/query/stream`
    : `${API_BASE}/query/stream`

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, accuracy_level: 'fast' }),
  })

  if (!res.ok || !res.body) {
    throw new Error(`Stream error: ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') return
      try {
        const parsed = JSON.parse(data)
        if (parsed.type === 'token') {
          yield { type: 'token', text: parsed.text }
        } else if (parsed.type === 'done') {
          yield { type: 'done', response: parsed.response }
          return
        }
      } catch {}
    }
  }
}

// ── Memory (corrections) ───────────────────────────────────────────────────────

export const getMemories = (user_id = 'local', project?: string) =>
  apiRequest<any[]>('GET', `/memory${project ? `?project=${encodeURIComponent(project)}` : ''}`)

export const pinMemory = (correction_id: string, pinned: boolean) =>
  apiRequest<{ updated: boolean }>('PATCH', `/memory/${correction_id}`, { pinned })

export const deleteMemory = (correction_id: string) =>
  apiRequest<{ deleted: boolean }>('DELETE', `/memory/${correction_id}`)

export const editMemory = (correction_id: string, corrective_instruction: string) =>
  apiRequest<{ updated: boolean }>('PATCH', `/memory/${correction_id}`, { corrective_instruction })

// ── Restart prompt ─────────────────────────────────────────────────────────────

export const getRestartPrompt = (project?: string) =>
  apiRequest<{
    project: string | null
    veritas_format: string
    ide_format: string
    item_count: number
    layer_counts: Record<string, number>
  }>('GET', `/restart-prompt${project ? `?project=${encodeURIComponent(project)}` : ''}`)

// ── Projects ───────────────────────────────────────────────────────────────────

export const listProjects = () =>
  apiRequest<{ project_id: string; name: string; created_at: number }[]>('GET', '/projects')

export const createProject = (name: string) =>
  apiRequest<{ project_id: string; name: string }>('POST', '/projects', { name })

