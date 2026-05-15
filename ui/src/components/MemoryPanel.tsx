// ui/src/components/MemoryPanel.tsx — Memory tab (right panel)
// Shows stored project corrections: view, pin, edit, delete.
// Restart prompt button at the bottom.

import { useState, useEffect, useCallback } from 'react'
import { getMemories, pinMemory, deleteMemory, editMemory } from '../api'
import RestartPromptModal from './RestartPromptModal'

interface Memory {
  correction_id: string
  type: string
  scope: string
  corrective_instruction: string
  canonical_query: string
  domain: string
  confidence: number
  decay_class: string
  pinned?: boolean
  created_at: number
}

interface Props {
  activeProject?: string
}

const TYPE_LABELS: Record<string, string> = {
  factual_correction:     'Fact',
  persistent_instruction: 'Rule',
  project_decision:       'Decision',
  preference:             'Preference',
  failure_pattern:        'Pattern',
}

const TYPE_COLORS: Record<string, string> = {
  factual_correction:     '#dbeafe',
  persistent_instruction: '#d1fae5',
  project_decision:       '#ede9fe',
  preference:             '#fef3c7',
  failure_pattern:        '#fee2e2',
}

const TYPE_TEXT_COLORS: Record<string, string> = {
  factual_correction:     '#1e40af',
  persistent_instruction: '#065f46',
  project_decision:       '#5b21b6',
  preference:             '#92400e',
  failure_pattern:        '#991b1b',
}

function MemoryCard({
  memory,
  onPin,
  onDelete,
  onEdit,
}: {
  memory: Memory
  onPin: (id: string, pinned: boolean) => void
  onDelete: (id: string) => void
  onEdit: (id: string, text: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(memory.corrective_instruction)
  const [saving, setSaving] = useState(false)

  const handleSaveEdit = async () => {
    if (!editText.trim()) return
    setSaving(true)
    await onEdit(memory.correction_id, editText)
    setSaving(false)
    setEditing(false)
  }

  const typeColor = TYPE_COLORS[memory.type] || '#f3f4f6'
  const typeTextColor = TYPE_TEXT_COLORS[memory.type] || '#374151'

  return (
    <div style={{
      padding: '10px 12px', borderRadius: 8,
      border: '1px solid #f3f4f6', background: '#fff',
      marginBottom: 6,
      boxShadow: memory.pinned ? '0 0 0 2px #4338ca22' : 'none',
      transition: 'box-shadow 0.15s',
    }}>
      {/* Type badge + scope + pin */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{
          fontSize: 10, padding: '2px 6px', borderRadius: 4,
          background: typeColor, color: typeTextColor, fontWeight: 700,
        }}>
          {TYPE_LABELS[memory.type] || memory.type}
        </span>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>
          {memory.scope}
        </span>
        <span style={{ flex: 1 }} />
        <button
          onClick={() => onPin(memory.correction_id, !memory.pinned)}
          title={memory.pinned ? 'Unpin' : 'Pin to top'}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, opacity: memory.pinned ? 1 : 0.3,
            transition: 'opacity 0.15s', padding: 0,
          }}
        >
          📌
        </button>
        <button
          onClick={() => setEditing(e => !e)}
          title="Edit"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 12, color: '#9ca3af', padding: '0 2px',
          }}
        >
          ✏
        </button>
        <button
          onClick={() => onDelete(memory.correction_id)}
          title="Delete"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, color: '#fca5a5', padding: 0,
          }}
        >
          ×
        </button>
      </div>

      {/* Instruction */}
      {editing ? (
        <div>
          <textarea
            value={editText}
            onChange={e => setEditText(e.target.value)}
            style={{
              width: '100%', padding: '5px 7px', borderRadius: 5,
              border: '1px solid #e5e7eb', fontSize: 12, lineHeight: 1.5,
              background: '#fafaf8', outline: 'none', resize: 'vertical',
              minHeight: 48, fontFamily: 'inherit', marginBottom: 6,
            }}
            autoFocus
          />
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={handleSaveEdit}
              disabled={saving}
              style={{
                padding: '3px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                background: '#4338ca', color: '#fff', border: 'none', cursor: 'pointer',
              }}
            >
              {saving ? '...' : 'Save'}
            </button>
            <button
              onClick={() => { setEditing(false); setEditText(memory.corrective_instruction) }}
              style={{
                padding: '3px 10px', borderRadius: 5, fontSize: 11,
                background: '#f3f4f6', color: '#374151', border: 'none', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.5 }}>
          {memory.corrective_instruction}
        </div>
      )}
    </div>
  )
}

export default function MemoryPanel({ activeProject }: Props) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [showRestart, setShowRestart] = useState(false)
  const [filter, setFilter] = useState<'all' | 'project' | 'global'>('all')

  const loadMemories = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getMemories('local', activeProject)
      setMemories(result)
    } catch {
      setMemories([])
    } finally {
      setLoading(false)
    }
  }, [activeProject])

  useEffect(() => {
    loadMemories()
  }, [loadMemories])

  const handlePin = async (id: string, pinned: boolean) => {
    try {
      await pinMemory(id, pinned)
      setMemories(prev => prev.map(m =>
        m.correction_id === id ? { ...m, pinned } : m
      ))
    } catch {}
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMemory(id)
      setMemories(prev => prev.filter(m => m.correction_id !== id))
    } catch {}
  }

  const handleEdit = async (id: string, text: string) => {
    try {
      await editMemory(id, text)
      setMemories(prev => prev.map(m =>
        m.correction_id === id ? { ...m, corrective_instruction: text } : m
      ))
    } catch {}
  }

  const filtered = memories.filter(m => {
    if (filter === 'all') return true
    return m.scope === filter
  })

  // Pinned first, then by created_at desc
  const sorted = [...filtered].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1
    if (!a.pinned && b.pinned) return 1
    return b.created_at - a.created_at
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Filter tabs */}
      <div style={{ padding: '10px 14px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 2, marginBottom: 10 }}>
          {(['all', 'project', 'global'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: filter === f ? 600 : 400,
                background: filter === f ? '#ede9fe' : 'transparent',
                color: filter === f ? '#5b21b6' : '#9ca3af',
                border: 'none', cursor: 'pointer', textTransform: 'capitalize',
              }}
            >
              {f}
            </button>
          ))}
          <span style={{ flex: 1 }} />
          <button
            onClick={loadMemories}
            title="Refresh"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#9ca3af', fontSize: 13, padding: '4px 6px',
            }}
          >
            ↻
          </button>
        </div>
      </div>

      {/* Memory list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 14px' }}>
        {loading ? (
          <div style={{ fontSize: 12, color: '#9ca3af', padding: '12px 0' }}>
            Loading memories...
          </div>
        ) : sorted.length === 0 ? (
          <div style={{
            fontSize: 12, color: '#9ca3af', lineHeight: 1.6, padding: '12px 0',
            textAlign: 'center',
          }}>
            No memories stored yet.
            <br />
            Corrections and decisions are captured automatically as you chat.
          </div>
        ) : (
          sorted.map(m => (
            <MemoryCard
              key={m.correction_id}
              memory={m}
              onPin={handlePin}
              onDelete={handleDelete}
              onEdit={handleEdit}
            />
          ))
        )}
      </div>

      {/* Restart prompt button */}
      <div style={{
        padding: '10px 14px', borderTop: '1px solid #e5e7eb', flexShrink: 0,
      }}>
        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>
          {sorted.length} memor{sorted.length !== 1 ? 'ies' : 'y'} stored
        </div>
        <button
          onClick={() => setShowRestart(true)}
          style={{
            width: '100%', padding: '8px', borderRadius: 7, fontSize: 12, fontWeight: 600,
            background: '#f3f4f6', color: '#374151', border: '1px solid #e5e7eb',
            cursor: 'pointer', transition: 'all 0.15s',
          }}
        >
          Generate restart prompt ↗
        </button>
      </div>

      {/* Restart prompt modal */}
      {showRestart && (
        <RestartPromptModal
          project={activeProject}
          onClose={() => setShowRestart(false)}
        />
      )}
    </div>
  )
}
