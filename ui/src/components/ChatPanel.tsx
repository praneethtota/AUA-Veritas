// ui/src/components/ChatPanel.tsx — Centre panel
// 3-color message system: user box (dark) | AI response (light) | callout (amber)
// Fast mode: tokens stream live word by word
// Balanced/High/Max: typing indicator then full response

import { useRef, useEffect, useState } from 'react'
import type { Message, CalloutType } from '../types'
import PassiveSaveCard, { type PendingMemory } from './PassiveSaveCard'

const CALLOUT_COLORS: Record<CalloutType, { bg: string; border: string; icon: string }> = {
  correction:    { bg: '#fffbeb', border: '#f59e0b', icon: '✓' },
  crosscheck:    { bg: '#f0fdf4', border: '#22c55e', icon: '✓' },
  disagreement:  { bg: '#fff7ed', border: '#f97316', icon: '⚠' },
  highstakes:    { bg: '#fff1f2', border: '#f43f5e', icon: '⚠' },
  conflict:      { bg: '#fef2f2', border: '#ef4444', icon: '!' },
  context_reset: { bg: '#f0f9ff', border: '#0ea5e9', icon: 'ℹ' },
}

interface Props {
  messages: Message[]
  loading: boolean
  streamingContent: string          // live token buffer for Fast mode
  pendingMemories: PendingMemory[]
  onSend: (text: string) => void
  onSaveMemory: (memory: PendingMemory) => void
  onSkipMemory: (id: string) => void
}

function UserMessage({ content }: { content: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
      <div style={{
        maxWidth: '72%', padding: '10px 14px', borderRadius: '16px 16px 4px 16px',
        background: '#1f2937', color: '#fff', fontSize: 14, lineHeight: 1.6,
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {content}
      </div>
    </div>
  )
}

function AssistantMessage({ msg }: { msg: Message }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 4 }}>
      <div style={{ maxWidth: '80%' }}>
        {msg.models_used && msg.models_used.length > 0 && (
          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4, paddingLeft: 2 }}>
            {msg.models_used.join(' · ')}
            {msg.confidence && (
              <span style={{
                marginLeft: 8, padding: '1px 6px', borderRadius: 3,
                background: msg.confidence === 'High' ? '#ecfdf5' : msg.confidence === 'Medium' ? '#fff7ed' : '#fef2f2',
                color: msg.confidence === 'High' ? '#059669' : msg.confidence === 'Medium' ? '#d97706' : '#dc2626',
                fontSize: 10, fontWeight: 600,
              }}>
                {msg.confidence}
              </span>
            )}
          </div>
        )}
        <div style={{
          padding: '10px 14px', borderRadius: '4px 16px 16px 16px',
          background: '#fff', border: '1px solid #e5e7eb',
          fontSize: 14, lineHeight: 1.7, color: '#111827',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}>
          {msg.content}
        </div>
        {msg.latency_ms && (
          <div style={{ fontSize: 10, color: '#d1d5db', marginTop: 3, paddingLeft: 2 }}>
            {msg.latency_ms.toFixed(0)}ms
          </div>
        )}
      </div>
    </div>
  )
}

const CALLOUT_EXPLANATIONS: Record<string, string> = {
  correction:    'I detected a correction signal in your message and saved it as a project memory. Future answers on this topic will automatically apply this correction.',
  crosscheck:    'I sent this question to multiple models simultaneously. They gave consistent answers, so the response has been cross-verified.',
  disagreement:  'The models gave different answers. I selected the most reliable response based on their track records, but you may want to verify this independently.',
  highstakes:    'This topic (medical, legal, or financial) carries real-world consequences. AI models can make mistakes on nuanced professional questions — always verify with a qualified expert.',
  conflict:      'A new correction conflicts with an existing project memory. The scope resolver is asking how to handle it.',
  context_reset: 'The conversation exceeded the model\'s context window. I automatically resent your project memory to maintain continuity.',
}

function CalloutMessage({ msg }: { msg: Message }) {
  const [expanded, setExpanded] = useState(false)
  const type = msg.callout_type || 'correction'
  const style = CALLOUT_COLORS[type] || CALLOUT_COLORS.correction
  const explanation = CALLOUT_EXPLANATIONS[type]

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
      <div style={{
        maxWidth: '80%', padding: '8px 12px',
        borderRadius: 8, borderLeft: `3px solid ${style.border}`,
        background: style.bg, fontSize: 13, color: '#374151', lineHeight: 1.5,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <span style={{ color: style.border, fontWeight: 700, flexShrink: 0, fontSize: 14 }}>
            {style.icon}
          </span>
          <span style={{ flex: 1 }}>{msg.content}</span>
          {explanation && (
            <button
              onClick={() => setExpanded(e => !e)}
              title="Why did I get this?"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 11, color: '#9ca3af', flexShrink: 0, padding: 0,
                fontWeight: 500,
              }}
            >
              {expanded ? '▲' : '?'}
            </button>
          )}
        </div>
        {expanded && explanation && (
          <div style={{
            marginTop: 6, paddingTop: 6, borderTop: `1px solid ${style.border}22`,
            fontSize: 12, color: '#6b7280', lineHeight: 1.6,
          }}>
            {explanation}
          </div>
        )}
      </div>
    </div>
  )
}

function StreamingBubble({ content }: { content: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 4 }}>
      <div style={{
        maxWidth: '80%',
        padding: '10px 14px', borderRadius: '4px 16px 16px 16px',
        background: '#fff', border: '1px solid #e5e7eb',
        fontSize: 14, lineHeight: 1.7, color: '#111827',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      }}>
        {content}
        <span style={{
          display: 'inline-block', width: 2, height: 14,
          background: '#4338ca', marginLeft: 2, verticalAlign: 'text-bottom',
          animation: 'blink 1s step-end infinite',
        }} />
        <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
      <div style={{
        padding: '10px 16px', borderRadius: '4px 16px 16px 16px',
        background: '#fff', border: '1px solid #e5e7eb',
        display: 'flex', gap: 4, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7, borderRadius: '50%', background: '#9ca3af',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
        <style>{`
          @keyframes bounce {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-6px); }
          }
        `}</style>
      </div>
    </div>
  )
}

export default function ChatPanel({ messages, loading, streamingContent, pendingMemories, onSend, onSaveMemory, onSkipMemory }: Props) {
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    onSend(text)
    // Reset textarea height
    if (inputRef.current) inputRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    // Auto-resize
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      borderRight: '1px solid #e5e7eb',
    }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px 8px' }}>
        {messages.length === 0 && (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12,
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#9ca3af' }}>
              AUA-Veritas
            </div>
            <div style={{ fontSize: 14, color: '#d1d5db', maxWidth: 320, textAlign: 'center', lineHeight: 1.6 }}>
              Ask anything. I'll cross-check the answer and let you know how confident I am.
            </div>
          </div>
        )}

        {messages.map(msg => {
          if (msg.role === 'user')     return <UserMessage    key={msg.id} content={msg.content} />
          if (msg.role === 'callout')  return <CalloutMessage key={msg.id} msg={msg} />
          if (msg.role === 'assistant') return <AssistantMessage key={msg.id} msg={msg} />
          return null
        })}

        {loading && !streamingContent && <TypingIndicator />}
        {streamingContent && <StreamingBubble content={streamingContent} />}

        {/* Passive save cards for medium-confidence memories */}
        {pendingMemories.map(memory => (
          <PassiveSaveCard
            key={memory.id}
            memory={memory}
            onSave={onSaveMemory}
            onSkip={onSkipMemory}
          />
        ))}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 16px 16px', borderTop: '1px solid #e5e7eb',
        background: '#fff', flexShrink: 0,
      }}>
        <div style={{
          display: 'flex', gap: 10, alignItems: 'flex-end',
          background: '#f9fafb', borderRadius: 12, border: '1px solid #e5e7eb',
          padding: '10px 14px',
          transition: 'border-color 0.2s',
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything…  (Shift+Enter for new line)"
            rows={1}
            style={{
              flex: 1, border: 'none', outline: 'none', resize: 'none',
              background: 'transparent', fontSize: 14, lineHeight: 1.6,
              color: '#111827', fontFamily: 'inherit', maxHeight: 160,
              minHeight: 22,
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            style={{
              width: 34, height: 34, borderRadius: 8, border: 'none',
              background: input.trim() && !loading ? '#4338ca' : '#e5e7eb',
              color: input.trim() && !loading ? '#fff' : '#9ca3af',
              cursor: input.trim() && !loading ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, transition: 'all 0.15s', fontSize: 16,
            }}
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  )
}
