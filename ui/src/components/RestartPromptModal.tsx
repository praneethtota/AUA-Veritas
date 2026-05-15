// ui/src/components/RestartPromptModal.tsx
// Generates a restart prompt from project memory.
// Two formats: Veritas (layered) and IDE (plain numbered list for Claude Code / Cursor).

import { useState, useEffect } from 'react'
import { getRestartPrompt } from '../api'

interface Props {
  project?: string
  onClose: () => void
}

type Format = 'veritas' | 'ide'

export default function RestartPromptModal({ project, onClose }: Props) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<{
    veritas_format: string
    ide_format: string
    item_count: number
    layer_counts: Record<string, number>
  } | null>(null)
  const [format, setFormat] = useState<Format>('ide')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    getRestartPrompt(project)
      .then(setData)
      .catch(() => setError('Failed to load project memories.'))
      .finally(() => setLoading(false))
  }, [project])

  const content = data ? (format === 'ide' ? data.ide_format : data.veritas_format) : ''

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {}
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9998, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, padding: 24,
        width: '100%', maxWidth: 560, boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        display: 'flex', flexDirection: 'column', maxHeight: '80vh',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#111827' }}>
              Restart prompt
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
              {project ? `Project: ${project}` : 'Global memories'}
              {data && data.item_count > 0 && ` · ${data.item_count} item${data.item_count !== 1 ? 's' : ''}`}
            </div>
          </div>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 6, border: '1px solid #e5e7eb',
            background: '#f9fafb', cursor: 'pointer', fontSize: 16, color: '#6b7280',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        {/* Format tabs */}
        <div style={{
          display: 'flex', gap: 4, marginBottom: 12,
          background: '#f3f4f6', padding: 4, borderRadius: 8,
        }}>
          {(['ide', 'veritas'] as Format[]).map(f => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              style={{
                flex: 1, padding: '5px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: format === f ? '#fff' : 'transparent',
                color: format === f ? '#111827' : '#6b7280',
                border: 'none', cursor: 'pointer',
                boxShadow: format === f ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s',
              }}
            >
              {f === 'ide' ? '💻 For IDE (Claude Code / Cursor)' : '⚡ For Veritas'}
            </button>
          ))}
        </div>

        {/* Format description */}
        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
          {format === 'ide'
            ? 'Paste into Claude Code, Cursor, or any AI tool\'s system prompt box.'
            : 'Paste back into AUA-Veritas to restore your full project context.'}
        </div>

        {/* Content */}
        <div style={{
          flex: 1, overflow: 'auto', minHeight: 160,
          background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb',
          padding: 12, marginBottom: 16,
        }}>
          {loading ? (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>Loading memories...</div>
          ) : error ? (
            <div style={{ color: '#ef4444', fontSize: 13 }}>{error}</div>
          ) : (
            <pre style={{
              margin: 0, fontSize: 12, lineHeight: 1.6, color: '#374151',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit',
            }}>
              {content || 'No memories stored for this project yet.'}
            </pre>
          )}
        </div>

        {/* Layer breakdown */}
        {data && data.layer_counts && Object.keys(data.layer_counts).length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {Object.entries(data.layer_counts).map(([type, count]) => (
              <span key={type} style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 10,
                background: '#f3f4f6', color: '#6b7280',
              }}>
                {type.replace(/_/g, ' ')}: {count}
              </span>
            ))}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={handleCopy}
            disabled={!content}
            style={{
              flex: 1, padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: copied ? '#059669' : '#4338ca', color: '#fff',
              border: 'none', cursor: content ? 'pointer' : 'default',
              transition: 'background 0.2s',
            }}
          >
            {copied
              ? '✓ Copied!'
              : format === 'ide'
                ? '📋 Copy for IDE'
                : '📋 Copy for Veritas'}
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '9px 16px', borderRadius: 8, fontSize: 13, fontWeight: 400,
              background: '#f3f4f6', color: '#374151',
              border: 'none', cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
