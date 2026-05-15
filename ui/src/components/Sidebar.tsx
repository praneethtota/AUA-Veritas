// ui/src/components/Sidebar.tsx — Left panel
// Conversations list + Project switcher + Model checkboxes + Accuracy slider

import { useState } from 'react'
import type { Conversation, AccuracyLevel, ModelInfo } from '../types'
import ConversationSearch from './ConversationSearch'

const ACCURACY_LEVELS = [
  { value: 'fast' as AccuracyLevel,     label: 'Fast',     desc: '1 model, fastest',             cost: '1×',      time: '+1-2%' },
  { value: 'balanced' as AccuracyLevel, label: 'Balanced', desc: '2 models, cross-checked',      cost: '~1.05×',  time: '+12% avg' },
  { value: 'high' as AccuracyLevel,     label: 'High',     desc: 'All models, VCG selects best', cost: 'N×',      time: '+5-15%' },
  { value: 'maximum' as AccuracyLevel,  label: 'Max',      desc: 'All models + peer review',     cost: '~N+0.1×', time: '+50-70%' },
]

interface Props {
  conversations: Conversation[]
  activeConvId: string | null
  models: Record<string, ModelInfo>
  enabledModels: string[]
  accuracy: AccuracyLevel
  sessionCost: number
  projects: { project_id: string; name: string }[]
  activeProject?: string
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onToggleModel: (modelId: string) => void
  onAccuracyChange: (level: AccuracyLevel) => void
  onSelectProject: (name: string) => void
  onNewProject: (name: string) => void
  onOpenSettings: () => void
}

export default function Sidebar({
  conversations, activeConvId, models, enabledModels,
  accuracy, sessionCost, projects, activeProject,
  onSelectConversation, onNewConversation, onToggleModel, onAccuracyChange,
  onSelectProject, onNewProject, onOpenSettings,
}: Props) {
  const [addingProject, setAddingProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const enabledCount = enabledModels.length
  const currentLevel = ACCURACY_LEVELS.find(a => a.value === accuracy) || ACCURACY_LEVELS[1]

  const filteredConversations = searchQuery
    ? conversations.filter(c =>
        (c.title || 'New Chat').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : conversations

  const handleAddProject = async () => {
    if (!newProjectName.trim()) return
    await onNewProject(newProjectName.trim())
    setNewProjectName('')
    setAddingProject(false)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      background: '#f5f5f2', borderRight: '1px solid #e5e7eb', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '16px 14px 12px', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: '#111827', letterSpacing: '-0.02em' }}>
            AUA-Veritas
          </div>
          <button onClick={onOpenSettings} title="Settings" style={{
            width: 26, height: 26, borderRadius: 6, border: '1px solid #e5e7eb',
            background: 'transparent', cursor: 'pointer', fontSize: 14, color: '#9ca3af',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>⚙</button>
        </div>
        <button onClick={onNewConversation} title="New chat (⌘K)" style={{
          width: '100%', padding: '7px 10px', borderRadius: 7, fontSize: 13, fontWeight: 600,
          background: '#4338ca', color: '#fff', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center',
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> New chat
        </button>
      </div>

      {/* Project switcher */}
      <div style={{ padding: '8px 14px 4px', flexShrink: 0, borderBottom: '1px solid #f0f0ec' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>
          Project
        </div>
        {addingProject ? (
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              autoFocus value={newProjectName}
              onChange={e => setNewProjectName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleAddProject(); if (e.key === 'Escape') setAddingProject(false) }}
              placeholder="Project name"
              style={{
                flex: 1, padding: '4px 6px', borderRadius: 5, fontSize: 12,
                border: '1px solid #4338ca', outline: 'none', background: '#fff',
              }}
            />
            <button onClick={handleAddProject} style={{
              padding: '4px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
              background: '#4338ca', color: '#fff', border: 'none', cursor: 'pointer',
            }}>✓</button>
            <button onClick={() => setAddingProject(false)} style={{
              padding: '4px 6px', borderRadius: 5, fontSize: 11,
              background: '#f3f4f6', color: '#374151', border: 'none', cursor: 'pointer',
            }}>×</button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {projects.length > 0 ? (
              <select
                value={activeProject || ''}
                onChange={e => onSelectProject(e.target.value)}
                style={{
                  flex: 1, padding: '4px 6px', borderRadius: 6, fontSize: 12,
                  border: '1px solid #e5e7eb', background: '#fff', color: '#374151',
                  outline: 'none', cursor: 'pointer',
                }}
              >
                {projects.map(p => <option key={p.project_id} value={p.name}>{p.name}</option>)}
              </select>
            ) : (
              <span style={{ flex: 1, fontSize: 12, color: '#9ca3af' }}>No projects</span>
            )}
            <button onClick={() => setAddingProject(true)} title="New project" style={{
              width: 22, height: 22, borderRadius: 5, border: '1px solid #e5e7eb',
              background: '#fff', cursor: 'pointer', fontSize: 14, color: '#9ca3af',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>+</button>
          </div>
        )}
      </div>

      {/* Conversations list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
        <ConversationSearch onSearch={setSearchQuery} />
        {filteredConversations.length === 0 ? (
          <div style={{ padding: '8px 14px', fontSize: 12, color: '#9ca3af' }}>
            {searchQuery ? 'No matches' : 'No conversations yet'}
          </div>
        ) : filteredConversations.map(conv => (
          <button
            key={conv.conversation_id}
            onClick={() => onSelectConversation(conv.conversation_id)}
            style={{
              width: '100%', textAlign: 'left', padding: '7px 14px',
              background: activeConvId === conv.conversation_id ? '#e8e8f0' : 'transparent',
              border: 'none', cursor: 'pointer', fontSize: 13, color: '#374151',
              borderRadius: 6, margin: '1px 4px', display: 'block',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              maxWidth: 'calc(100% - 8px)', transition: 'background 0.1s',
            }}
          >
            {conv.title || 'New Chat'}
          </button>
        ))}
      </div>

      <div style={{ borderTop: '1px solid #e5e7eb', flexShrink: 0 }} />

      {/* Models */}
      <div style={{ padding: '10px 14px 8px', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 7 }}>
          Models
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {Object.values(models).filter(m => m.connected && !m.is_cheap_judge).map(model => (
            <label key={model.model_id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '3px 0', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={enabledModels.includes(model.model_id)}
                onChange={() => onToggleModel(model.model_id)}
                style={{ accentColor: '#4338ca', width: 13, height: 13 }}
              />
              <span style={{ color: '#374151', flex: 1 }}>{model.display_name}</span>
            </label>
          ))}
          {Object.values(models).filter(m => m.connected).length === 0 && (
            <button onClick={onOpenSettings} style={{
              fontSize: 12, color: '#4338ca', background: 'none',
              border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0,
            }}>+ Connect a model</button>
          )}
        </div>
      </div>

      <div style={{ borderTop: '1px solid #e5e7eb', flexShrink: 0 }} />

      {/* Accuracy */}
      <div style={{ padding: '10px 14px', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 7 }}>
          Accuracy
        </div>
        <div style={{ display: 'flex', gap: 2, marginBottom: 5 }}>
          {ACCURACY_LEVELS.map(level => {
            const locked = (level.value === 'high' || level.value === 'maximum') && enabledCount < 2
            return (
              <button
                key={level.value}
                onClick={() => !locked && onAccuracyChange(level.value)}
                disabled={locked}
                title={locked ? 'Add a second provider to unlock' : level.desc}
                style={{
                  flex: 1, padding: '4px 2px', border: 'none', cursor: locked ? 'default' : 'pointer',
                  borderRadius: 4, fontSize: 11, fontWeight: accuracy === level.value ? 700 : 400,
                  background: accuracy === level.value ? '#4338ca' : 'transparent',
                  color: accuracy === level.value ? '#fff' : locked ? '#d1d5db' : '#6b7280',
                  transition: 'all 0.15s',
                }}
              >
                {level.label}
              </button>
            )
          })}
        </div>
        <div style={{ fontSize: 11, color: '#9ca3af' }}>
          {currentLevel.cost} · {currentLevel.time}
          {(currentLevel.value === 'high' || currentLevel.value === 'maximum') && enabledCount < 2 && (
            <span style={{ color: '#f59e0b' }}> · 2+ providers needed</span>
          )}
        </div>
      </div>

      {/* Session cost */}
      <div style={{
        padding: '8px 14px', borderTop: '1px solid #e5e7eb',
        fontSize: 12, color: '#9ca3af', display: 'flex', justifyContent: 'space-between', flexShrink: 0,
      }}>
        <span>Session cost</span>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>~${sessionCost.toFixed(3)}</span>
      </div>
    </div>
  )
}
