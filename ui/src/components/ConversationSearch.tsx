// ui/src/components/ConversationSearch.tsx
// Search bar that filters the conversation list in the sidebar.

import { useState, useCallback } from 'react'

interface Props {
  onSearch: (query: string) => void
  placeholder?: string
}

export default function ConversationSearch({ onSearch, placeholder = 'Search chats…' }: Props) {
  const [value, setValue] = useState('')

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value)
    onSearch(e.target.value)
  }, [onSearch])

  const handleClear = () => {
    setValue('')
    onSearch('')
  }

  return (
    <div style={{
      position: 'relative', margin: '6px 8px',
    }}>
      <span style={{
        position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
        fontSize: 12, color: '#9ca3af', pointerEvents: 'none',
      }}>🔍</span>
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '5px 28px 5px 24px',
          borderRadius: 6, fontSize: 12, border: '1px solid #e5e7eb',
          background: '#fff', outline: 'none', color: '#374151',
          boxSizing: 'border-box',
        }}
      />
      {value && (
        <button
          onClick={handleClear}
          style={{
            position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, color: '#9ca3af', padding: 0, lineHeight: 1,
          }}
        >×</button>
      )}
    </div>
  )
}
