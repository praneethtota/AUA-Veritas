// ui/src/components/ChatLayout.tsx — Main 3-panel layout

import { useState, useEffect, useCallback } from 'react'
import Sidebar from './Sidebar'
import ChatPanel from './ChatPanel'
import QualityPanel from './QualityPanel'
import { listConversations, createConversation, listModels, sendQuery, getMessages } from '../api'
import type { Conversation, Message, AccuracyLevel, ModelInfo, QueryResponse } from '../types'

export default function ChatLayout() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [models, setModels] = useState<Record<string, ModelInfo>>({})
  const [enabledModels, setEnabledModels] = useState<string[]>([])
  const [accuracy, setAccuracy] = useState<AccuracyLevel>('balanced')
  const [loading, setLoading] = useState(false)
  const [sessionCost, setSessionCost] = useState(0)
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null)

  // Load initial data
  useEffect(() => {
    loadConversations()
    loadModels()
  }, [])

  // Load messages when conversation changes
  useEffect(() => {
    if (activeConvId) {
      loadMessages(activeConvId)
    } else {
      setMessages([])
    }
  }, [activeConvId])

  const loadConversations = async () => {
    try {
      const convs = await listConversations()
      setConversations(convs)
      if (convs.length > 0 && !activeConvId) {
        setActiveConvId(convs[0].conversation_id)
      }
    } catch {}
  }

  const loadModels = async () => {
    try {
      const modelMap = await listModels()
      setModels(modelMap)
      // Auto-enable connected models
      const connected = Object.entries(modelMap)
        .filter(([, m]) => (m as ModelInfo).connected)
        .map(([id]) => id)
      setEnabledModels(connected)
    } catch {}
  }

  const loadMessages = async (convId: string) => {
    try {
      const msgs = await getMessages(convId)
      setMessages(msgs.map(m => ({ ...m, timestamp: m.created_at * 1000 })))
    } catch {}
  }

  const handleNewConversation = async () => {
    try {
      const { conversation_id } = await createConversation()
      await loadConversations()
      setActiveConvId(conversation_id)
      setMessages([])
    } catch {}
  }

  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return

    let convId = activeConvId
    if (!convId) {
      try {
        const result = await createConversation(text.slice(0, 40))
        convId = result.conversation_id
        setActiveConvId(convId)
        await loadConversations()
      } catch { return }
    }

    // Add user message immediately
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    // Build conversation history for correction context
    const history = messages.map(m => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    }))

    try {
      const response = await sendQuery({
        query: text,
        conversation_id: convId!,
        accuracy_level: accuracy,
        enabled_models: enabledModels,
        conversation_history: history,
      })

      setLastResponse(response)

      // Estimate cost
      const callCount = response.all_models_used?.length || 1
      const perCall = 0.01 // rough estimate
      setSessionCost(prev => prev + callCount * perCall)

      // Add AI response
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        models_used: response.all_models_used,
        accuracy_level: accuracy,
        confidence: response.confidence_label,
        welfare_scores: response.welfare_scores || undefined,
        peer_review_used: response.peer_review_used,
        corrections_applied: response.corrections_applied,
        latency_ms: response.latency_ms,
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, aiMsg])

      // Add callout if present
      if (response.callout_type && response.callout_text) {
        const calloutMsg: Message = {
          id: `callout-${Date.now()}`,
          role: 'callout',
          content: response.callout_text,
          callout_type: response.callout_type,
          timestamp: Date.now(),
        }
        setMessages(prev => [...prev, calloutMsg])
      }

      // Update conversation title with first message
      if (conversations.find(c => c.conversation_id === convId)?.title === 'New Chat') {
        await loadConversations()
      }
    } catch (err: any) {
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: 'callout',
        content: `Something went wrong: ${err.message || 'Please try again.'}`,
        callout_type: 'conflict',
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }, [activeConvId, accuracy, enabledModels, loading, messages, conversations])

  return (
    <div style={{
      height: '100vh',
      display: 'grid',
      gridTemplateColumns: '240px 1fr 260px',
      gridTemplateRows: '1fr',
      overflow: 'hidden',
      background: '#fafaf8',
    }}>
      {/* Left panel — Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConvId={activeConvId}
        models={models}
        enabledModels={enabledModels}
        accuracy={accuracy}
        sessionCost={sessionCost}
        onSelectConversation={setActiveConvId}
        onNewConversation={handleNewConversation}
        onToggleModel={(modelId) => {
          setEnabledModels(prev =>
            prev.includes(modelId)
              ? prev.filter(m => m !== modelId)
              : [...prev, modelId]
          )
        }}
        onAccuracyChange={setAccuracy}
      />

      {/* Centre panel — Chat */}
      <ChatPanel
        messages={messages}
        loading={loading}
        onSend={handleSendMessage}
      />

      {/* Right panel — Quality */}
      <QualityPanel
        response={lastResponse}
        models={models}
      />
    </div>
  )
}
