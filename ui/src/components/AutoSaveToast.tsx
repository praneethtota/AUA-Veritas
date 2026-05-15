// ui/src/components/AutoSaveToast.tsx
// Non-blocking bottom-of-screen toast for automatic memory saves (store_utility ≥ 0.85).
// Shows for 5 seconds with Undo and Edit options.

import { useState, useEffect, useRef } from 'react'

export interface ToastMemory {
  id: string
  corrective_instruction: string
  type: string
  scope: string
}

interface Props {
  memory: ToastMemory | null
  onUndo: (id: string) => void
  onEdit: (memory: ToastMemory) => void
  onDismiss: () => void
}

const DURATION = 5000

export default function AutoSaveToast({ memory, onUndo, onEdit, onDismiss }: Props) {
  const [progress, setProgress] = useState(100)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startRef = useRef<number>(0)

  useEffect(() => {
    if (!memory) return
    setProgress(100)
    startRef.current = Date.now()

    intervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startRef.current
      const remaining = Math.max(0, 100 - (elapsed / DURATION) * 100)
      setProgress(remaining)
      if (remaining <= 0) {
        clearInterval(intervalRef.current!)
        onDismiss()
      }
    }, 50)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [memory?.id])

  if (!memory) return null

  const scopeLabel = memory.scope === 'global' ? 'Global' : 'Project'

  return (
    <div style={{
      position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
      background: '#1f2937', color: '#fff', borderRadius: 10,
      padding: '10px 16px', minWidth: 320, maxWidth: 480,
      boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
      zIndex: 9999, overflow: 'hidden',
      animation: 'slideUp 0.25s ease',
    }}>
      {/* Content */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 16 }}>✓</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 1 }}>
            {scopeLabel} memory saved
          </div>
          <div style={{
            fontSize: 13, fontWeight: 500,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {memory.corrective_instruction}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => onUndo(memory.id)}
            style={{
              padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: 'rgba(255,255,255,0.15)', color: '#fff',
              border: '1px solid rgba(255,255,255,0.2)', cursor: 'pointer',
            }}
          >
            Undo
          </button>
          <button
            onClick={() => onEdit(memory)}
            style={{
              padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 400,
              background: 'transparent', color: '#9ca3af',
              border: '1px solid rgba(255,255,255,0.1)', cursor: 'pointer',
            }}
          >
            Edit
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0,
        height: 3, background: '#4338ca', borderRadius: '0 0 10px 10px',
        width: `${progress}%`, transition: 'width 0.05s linear',
      }} />

      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateX(-50%) translateY(10px); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  )
}
