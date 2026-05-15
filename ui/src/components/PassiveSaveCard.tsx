// ui/src/components/PassiveSaveCard.tsx
// Appears inline in the chat for store_utility 0.60–0.85 memories.
// User can Save / Edit / Skip without leaving the conversation.

import { useState } from 'react'
import { editMemory } from '../api'

export interface PendingMemory {
  id: string
  corrective_instruction: string
  type: string
  scope: string
  domain: string
  canonical_query: string
}

interface Props {
  memory: PendingMemory
  onSave: (memory: PendingMemory) => void
  onSkip: (id: string) => void
}

export default function PassiveSaveCard({ memory, onSave, onSkip }: Props) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(memory.corrective_instruction)
  const [saving, setSaving] = useState(false)

  const scopeLabel = memory.scope === 'global' ? 'Global rule' : 'Project memory'
  const typeLabel: Record<string, string> = {
    factual_correction:     'Factual correction',
    persistent_instruction: 'Instruction',
    project_decision:       'Project decision',
    preference:             'Preference',
    failure_pattern:        'Failure pattern',
  }

  const handleSave = async () => {
    setSaving(true)
    onSave({ ...memory, corrective_instruction: text })
    setSaving(false)
  }

  return (
    <div style={{
      margin: '6px 0 10px',
      padding: '10px 14px',
      borderRadius: 8,
      border: '1px solid #f59e0b',
      borderLeft: '3px solid #f59e0b',
      background: '#fffbeb',
      maxWidth: '80%',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
      }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#92400e' }}>
          Save this {typeLabel[memory.type] || 'memory'}?
        </span>
        <span style={{
          fontSize: 10, padding: '2px 6px', borderRadius: 4,
          background: '#fef3c7', color: '#92400e', fontWeight: 600,
        }}>
          {scopeLabel}
        </span>
      </div>

      {/* Instruction text */}
      {editing ? (
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          style={{
            width: '100%', padding: '6px 8px', borderRadius: 6,
            border: '1px solid #fbbf24', fontSize: 13, lineHeight: 1.5,
            background: '#fff', outline: 'none', resize: 'vertical',
            minHeight: 56, fontFamily: 'inherit', marginBottom: 8,
          }}
          autoFocus
        />
      ) : (
        <div style={{
          fontSize: 13, color: '#374151', lineHeight: 1.5, marginBottom: 10,
          padding: '5px 8px', background: '#fef9ee', borderRadius: 5,
          border: '1px solid #fde68a',
        }}>
          {text}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6 }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: '#4338ca', color: '#fff', border: 'none', cursor: 'pointer',
          }}
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={() => setEditing(e => !e)}
          style={{
            padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500,
            background: '#fff', color: '#374151', border: '1px solid #e5e7eb',
            cursor: 'pointer',
          }}
        >
          {editing ? 'Done' : 'Edit'}
        </button>
        <button
          onClick={() => onSkip(memory.id)}
          style={{
            padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 400,
            background: 'transparent', color: '#9ca3af', border: 'none',
            cursor: 'pointer',
          }}
        >
          Skip
        </button>
      </div>
    </div>
  )
}
