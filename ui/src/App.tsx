// ui/src/App.tsx — Root application component

import { useState, useEffect } from 'react'
import { getKeyStatus, health } from './api'
import SetupScreen from './components/SetupScreen'
import ChatLayout from './components/ChatLayout'
import OnboardingWalkthrough from './components/OnboardingWalkthrough'

type AppView = 'loading' | 'setup' | 'onboarding' | 'chat'

const ONBOARDING_KEY = 'veritas_onboarding_done'

export default function App() {
  const [view, setView] = useState<AppView>('loading')
  const [apiReady, setApiReady] = useState(false)

  useEffect(() => {
    const isElectron = !!(window as any).veritas
    if (isElectron) {
      const cleanup = (window as any).veritas.onApiReady(() => setApiReady(true))
      ;(window as any).veritas.apiStatus().then((s: any) => { if (s.ready) setApiReady(true) })
      return cleanup
    } else {
      const poll = setInterval(async () => {
        try { await health(); setApiReady(true); clearInterval(poll) } catch (_) {}
      }, 1000)
      return () => clearInterval(poll)
    }
  }, [])

  useEffect(() => {
    if (!apiReady) return
    getKeyStatus()
      .then((status) => {
        const hasAnyKey = Object.values(status).some(Boolean)
        if (!hasAnyKey) {
          setView('setup')
        } else {
          const onboardingDone = localStorage.getItem(ONBOARDING_KEY)
          setView(onboardingDone ? 'chat' : 'onboarding')
        }
      })
      .catch(() => setView('setup'))
  }, [apiReady])

  const handleSetupComplete = () => {
    const onboardingDone = localStorage.getItem(ONBOARDING_KEY)
    setView(onboardingDone ? 'chat' : 'onboarding')
  }

  const handleOnboardingComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, '1')
    setView('chat')
  }

  if (view === 'loading') {
    return (
      <div style={{
        height: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: '#fafaf8', gap: 16,
      }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: '#1a1a1a' }}>AUA-Veritas</div>
        <div style={{ fontSize: 14, color: '#6b7280' }}>
          {apiReady ? 'Loading...' : 'Starting AI engine...'}
        </div>
        <div style={{ width: 200, height: 3, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: '#4338ca', borderRadius: 2,
            width: apiReady ? '80%' : '40%', transition: 'width 0.5s ease',
          }} />
        </div>
      </div>
    )
  }

  return (
    <>
      {view === 'setup' && <SetupScreen onComplete={handleSetupComplete} />}
      {view === 'onboarding' && <OnboardingWalkthrough onComplete={handleOnboardingComplete} />}
      {view === 'chat' && <ChatLayout />}
    </>
  )
}
