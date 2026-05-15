// ui/src/App.tsx — Root application component
// Routes between: SetupScreen (first launch) → ChatLayout (main app)

import { useState, useEffect } from 'react'
import { getKeyStatus, listModels, health } from './api'
import SetupScreen from './components/SetupScreen'
import ChatLayout from './components/ChatLayout'

type AppView = 'loading' | 'setup' | 'chat'

export default function App() {
  const [view, setView] = useState<AppView>('loading')
  const [apiReady, setApiReady] = useState(false)

  useEffect(() => {
    // Listen for API ready signal from Electron main process
    const isElectron = !!(window as any).veritas
    if (isElectron) {
      const cleanup = (window as any).veritas.onApiReady(() => {
        setApiReady(true)
      })
      // Also check current status immediately
      ;(window as any).veritas.apiStatus().then((s: any) => {
        if (s.ready) setApiReady(true)
      })
      return cleanup
    } else {
      // In browser dev mode, poll the API
      const poll = setInterval(async () => {
        try {
          await health()
          setApiReady(true)
          clearInterval(poll)
        } catch (_) {}
      }, 1000)
      return () => clearInterval(poll)
    }
  }, [])

  useEffect(() => {
    if (!apiReady) return
    // Check if user has any API keys configured
    getKeyStatus()
      .then((status) => {
        const hasAnyKey = Object.values(status).some(Boolean)
        setView(hasAnyKey ? 'chat' : 'setup')
      })
      .catch(() => setView('setup'))
  }, [apiReady])

  if (view === 'loading') {
    return (
      <div style={{
        height: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: '#fafaf8', gap: 16,
      }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: '#1a1a1a' }}>
          AUA-Veritas
        </div>
        <div style={{ fontSize: 14, color: '#6b7280' }}>
          {apiReady ? 'Loading...' : 'Starting AI engine...'}
        </div>
        <div style={{
          width: 200, height: 3, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', background: '#4338ca', borderRadius: 2,
            animation: 'pulse 1.5s ease-in-out infinite',
            width: apiReady ? '80%' : '40%',
            transition: 'width 0.5s ease',
          }} />
        </div>
        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}</style>
      </div>
    )
  }

  if (view === 'setup') {
    return <SetupScreen onComplete={() => setView('chat')} />
  }

  return <ChatLayout />
}
