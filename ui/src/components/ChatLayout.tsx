// ui/src/components/ChatLayout.tsx — Main 3-panel layout

import { useState, useEffect, useCallback } from 'react'
import Sidebar from './Sidebar'
import ChatPanel from './ChatPanel'
import QualityPanel from './QualityPanel'
import SettingsPage from './SettingsPage'
import AutoSaveToast, { type ToastMemory } from './AutoSaveToast'
import LookUnderTheHood from './LookUnderTheHood'
import UsagePage from './UsagePage'
import type { PendingMemory } from './PassiveSaveCard'
import {
  listConversations, createConversation, listModels,
  sendQuery, streamQuery, getMessages, listProjects, createProject,
} from '../api'
import type { Conversation, Message, AccuracyLevel, ModelInfo, QueryResponse } from '../types'

interface Props {
  darkMode: boolean
  onToggleDarkMode: (dark: boolean) => void
}

export default function ChatLayout({ darkMode, onToggleDarkMode }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [models, setModels] = useState<Record<string, ModelInfo>>({})
  const [enabledModels, setEnabledModels] = useState<string[]>([])
  const [accuracy, setAccuracy] = useState<AccuracyLevel>('balanced')
  const [loading, setLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [sessionCost, setSessionCost] = useState(0)
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null)
  const [projects, setProjects] = useState<{ project_id: string; name: string }[]>([])
  const [activeProject, setActiveProject] = useState<string | undefined>(undefined)
  const [showSettings, setShowSettings] = useState(false)
  const [toastMemory, setToastMemory] = useState<ToastMemory | null>(null)
  const [pendingMemories, setPendingMemories] = useState<PendingMemory[]>([])
  const [showHood, setShowHood] = useState(false)
  const [showUsage, setShowUsage] = useState(false)
  const [rightTab, setRightTab] = useState<'quality' | 'memory'>('quality')

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key === 'k') {
        e.preventDefault()
        handleNewConversation()
      }
      if (meta && e.key === 'm') {
        e.preventDefault()
        setRightTab('memory')
      }
      if (e.key === 'Escape') {
        setShowSettings(false)
        setShowHood(false)
        setShowUsage(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    loadConversations()
    loadModels()
    loadProjects()
  }, [])

  useEffect(() => {
    if (activeConvId) loadMessages(activeConvId)
    else setMessages([])
  }, [activeConvId])

  const loadConversations = async () => {
    try {
      const convs = await listConversations()
      setConversations(convs)
      if (convs.length > 0 && !activeConvId) setActiveConvId(convs[0].conversation_id)
    } catch {}
  }

  const loadModels = async () => {
    try {
      const modelMap = await listModels()
      setModels(modelMap)
      // Only auto-enable on first load (when enabledModels is still empty)
      // After that, preserve user's manual selections
      setEnabledModels(prev => {
        if (prev.length > 0) return prev  // user already made selections — don't override
        const connected = Object.entries(modelMap)
          .filter(([, m]) => (m as ModelInfo).connected && !(m as ModelInfo).is_cheap_judge)
          .map(([id]) => id)
        return connected.slice(0, 1)  // auto-enable only the first connected model
      })
    } catch {}
  }

  const loadProjects = async () => {
    try {
      const projs = await listProjects()
      setProjects(projs)
      if (projs.length > 0 && !activeProject) setActiveProject(projs[0].name)
    } catch {}
  }

  const loadMessages = async (convId: string) => {
    try {
      const msgs = await getMessages(convId)
      setMessages(msgs.map((m: any) => ({ ...m, timestamp: (m.created_at || Date.now() / 1000) * 1000 })))
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

  const handleNewProject = async (name: string) => {
    try {
      const proj = await createProject(name)
      setProjects(prev => [...prev, proj])
      setActiveProject(proj.name)
    } catch {}
  }

  const handleSaveMemory = useCallback((memory: PendingMemory) => {
    setPendingMemories(prev => prev.filter(m => m.id !== memory.id))
    setToastMemory({
      id: memory.id,
      corrective_instruction: memory.corrective_instruction,
      type: memory.type,
      scope: memory.scope,
    })
  }, [])

  const handleSkipMemory = useCallback((id: string) => {
    setPendingMemories(prev => prev.filter(m => m.id !== id))
  }, [])

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

    const userMsg: Message = {
      id: `user-${Date.now()}`, role: 'user', content: text, timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    setStreamingContent('')

    const history = messages.map(m => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    }))

    try {
      // ── Fast mode: stream tokens live ──────────────────────────────────────
      if (accuracy === 'fast') {
        let fullText = ''
        let finalResponse: QueryResponse | null = null

        const stream = streamQuery({
          query: text,
          conversation_id: convId!,
          enabled_models: enabledModels,
          conversation_history: history,
        })

        for await (const event of stream) {
          if (event.type === 'token') {
            fullText += event.text
            setStreamingContent(fullText)
          } else if (event.type === 'done') {
            finalResponse = event.response as QueryResponse
          }
        }

        setStreamingContent('')

        const response = finalResponse || {
          response: fullText,
          primary_model: enabledModels[0] || '',
          all_models_used: enabledModels.slice(0, 1),
          confidence_label: 'Medium' as const,
          callout_type: null,
          callout_text: null,
          welfare_scores: null,
          peer_review_used: false,
          corrections_applied: [],
          latency_ms: 0,
        }

        setLastResponse(response)
        setSessionCost(prev => prev + 0.01)

        setMessages(prev => [...prev, {
          id: `ai-${Date.now()}`, role: 'assistant' as const,
          content: response.response,
          models_used: response.all_models_used,
          accuracy_level: accuracy,
          confidence: response.confidence_label,
          latency_ms: response.latency_ms,
          timestamp: Date.now(),
        }])

        if (response.callout_type && response.callout_text) {
          setMessages(prev => [...prev, {
            id: `callout-${Date.now()}`, role: 'callout' as const,
            content: response.callout_text!, callout_type: response.callout_type!,
            timestamp: Date.now(),
          }])
        }

      } else {
        // ── Balanced / High / Maximum: wait for full response ───────────────
        const response = await sendQuery({
          query: text,
          conversation_id: convId!,
          accuracy_level: accuracy,
          enabled_models: enabledModels,
          conversation_history: history,
        })

        setLastResponse(response)
        const callCount = Math.max(1, response.all_models_used?.length || 1)
        const judgeCallCost = accuracy === 'maximum' ? (callCount - 1) * 0.001 : 0
        setSessionCost(prev => prev + callCount * 0.01 + judgeCallCost)

        setMessages(prev => [...prev, {
          id: `ai-${Date.now()}`, role: 'assistant' as const,
          content: response.response,
          models_used: response.all_models_used,
          accuracy_level: accuracy,
          confidence: response.confidence_label,
          welfare_scores: response.welfare_scores || undefined,
          peer_review_used: response.peer_review_used,
          corrections_applied: response.corrections_applied,
          latency_ms: response.latency_ms,
          timestamp: Date.now(),
        }])

        if (response.callout_type === 'correction' && response.corrections_applied?.length > 0) {
          setToastMemory({
            id: response.corrections_applied[0],
            corrective_instruction: response.response,
            type: 'factual_correction', scope: 'project',
          })
        } else if (response.callout_type && response.callout_text) {
          setMessages(prev => [...prev, {
            id: `callout-${Date.now()}`, role: 'callout' as const,
            content: response.callout_text!, callout_type: response.callout_type!,
            timestamp: Date.now(),
          }])
        }
      }

      await loadConversations()
    } catch (err: any) {
      setStreamingContent('')
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`, role: 'callout' as const,
        content: `Something went wrong: ${err.message || 'Please try again.'}`,
        callout_type: 'conflict' as const, timestamp: Date.now(),
      }])
    } finally {
      setLoading(false)
      setStreamingContent('')
    }
  }, [activeConvId, accuracy, enabledModels, loading, messages])

  return (
    <>
      <div style={{
        height: '100vh',
        display: 'grid',
        gridTemplateColumns: '240px 1fr 260px',
        overflow: 'hidden',
        background: 'var(--bg-primary)',
      }}>
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          models={models}
          enabledModels={enabledModels}
          accuracy={accuracy}
          sessionCost={sessionCost}
          projects={projects}
          activeProject={activeProject}
          onSelectConversation={setActiveConvId}
          onNewConversation={handleNewConversation}
          onToggleModel={modelId => setEnabledModels(prev =>
            prev.includes(modelId) ? prev.filter(m => m !== modelId) : [...prev, modelId]
          )}
          onAccuracyChange={setAccuracy}
          onSelectProject={setActiveProject}
          onNewProject={handleNewProject}
          onOpenSettings={() => setShowSettings(true)}
        />

        <ChatPanel
          messages={messages}
          loading={loading}
          streamingContent={streamingContent}
          pendingMemories={pendingMemories}
          onSend={handleSendMessage}
          onSaveMemory={handleSaveMemory}
          onSkipMemory={handleSkipMemory}
        />

        <QualityPanel
          response={lastResponse}
          models={models}
          activeProject={activeProject}
          activeTab={rightTab}
          onTabChange={setRightTab}
          onOpenHood={() => setShowHood(true)}
          onOpenUsage={() => setShowUsage(true)}
        />
      </div>

      <AutoSaveToast
        memory={toastMemory}
        onUndo={() => setToastMemory(null)}
        onEdit={() => setToastMemory(null)}
        onDismiss={() => setToastMemory(null)}
      />

      {showSettings && <SettingsPage darkMode={darkMode} onToggleDarkMode={onToggleDarkMode} onClose={() => setShowSettings(false)} />}
      {showHood && <LookUnderTheHood onClose={() => setShowHood(false)} />}
      {showUsage && <UsagePage onClose={() => setShowUsage(false)} />}
    </>
  )
}
