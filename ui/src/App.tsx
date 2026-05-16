// ui/src/App.tsx — Root application component

import { useState, useEffect } from 'react'
import { getKeyStatus, health } from './api'
import SetupScreen from './components/SetupScreen'
import ChatLayout from './components/ChatLayout'
import OnboardingWalkthrough from './components/OnboardingWalkthrough'

type AppView = 'loading' | 'setup' | 'onboarding' | 'chat'

const ONBOARDING_KEY  = 'veritas_onboarding_done'
const DARK_MODE_KEY   = 'veritas_dark_mode'

// ── Dark mode ──────────────────────────────────────────────────────────────────
// Reads from localStorage. Applied to <html data-theme="dark"> so CSS vars
// propagate everywhere without prop-drilling. Called before first render.

export function getInitialDarkMode(): boolean {
  try { return localStorage.getItem(DARK_MODE_KEY) === '1' } catch { return false }
}

export function applyDarkMode(dark: boolean) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  try { localStorage.setItem(DARK_MODE_KEY, dark ? '1' : '0') } catch {}
}

// Apply immediately on module load (before React renders) to avoid flash
applyDarkMode(getInitialDarkMode())

// ── Loading screen ─────────────────────────────────────────────────────────────

const STAGES = [
  { label: 'Loading interface',      progress: 15 },
  { label: 'Starting AI engine',     progress: 35 },
  { label: 'Loading model plugins',  progress: 60 },
  { label: 'Restoring your memory',  progress: 80 },
  { label: 'Ready',                  progress: 100 },
]

function LoadingScreen({ apiReady }: { apiReady: boolean }) {
  const [stageIdx, setStageIdx] = useState(0)

  useEffect(() => {
    if (apiReady) {
      setStageIdx(STAGES.length - 1)
      return
    }
    // Cycle through stages every ~800ms to show progress
    const iv = setInterval(() => {
      setStageIdx(i => {
        // Stop one before the last (Ready) — that needs real apiReady
        if (i < STAGES.length - 2) return i + 1
        return i
      })
    }, 800)
    return () => clearInterval(iv)
  }, [apiReady])

  const stage = STAGES[stageIdx]

  return (
    <div style={{
      height: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)', gap: 20,
    }}>
      {/* Logo mark */}
      <div style={{
        width: 56, height: 56, borderRadius: 16,
        background: 'linear-gradient(135deg, #4338ca, #7c3aed)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 26, marginBottom: 4,
        boxShadow: '0 8px 24px rgba(67,56,202,0.3)',
      }}>
        ✓
      </div>

      <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        AUA-Veritas
      </div>

      {/* Stage label */}
      <div style={{
        fontSize: 13, color: 'var(--text-secondary)',
        minHeight: 20, transition: 'opacity 0.3s',
      }}>
        {stage.label}...
      </div>

      {/* Progress bar */}
      <div style={{ width: 220, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', background: '#4338ca', borderRadius: 2,
          width: `${stage.progress}%`,
          transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
        }} />
      </div>

      {/* Dots */}
      <div style={{ display: 'flex', gap: 6 }}>
        {STAGES.slice(0, -1).map((_, i) => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: 3,
            background: i <= stageIdx ? '#4338ca' : 'var(--border)',
            transition: 'background 0.3s',
          }} />
        ))}
      </div>
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────────────────────

export default function App() {
  const [view, setView]       = useState<AppView>('loading')
  const [apiReady, setApiReady] = useState(false)
  const [darkMode, setDarkMode] = useState(getInitialDarkMode)

  // Expose dark mode toggle globally so Settings can call it
  useEffect(() => {
    (window as any).veritasSetDarkMode = (dark: boolean) => {
      setDarkMode(dark)
      applyDarkMode(dark)
    }
  }, [])

  useEffect(() => {
    const isElectron = !!(window as any).veritas
    if (isElectron) {
      const cleanup = (window as any).veritas.onApiReady(() => setApiReady(true))
      ;(window as any).veritas.apiStatus().then((s: any) => { if (s.ready) setApiReady(true) })
      return cleanup
    } else {
      const poll = setInterval(async () => {
        try { await health(); setApiReady(true); clearInterval(poll) } catch (_) {}
      }, 500)
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

  if (view === 'loading') return <LoadingScreen apiReady={apiReady} />

  return (
    <>
      {view === 'setup'      && <SetupScreen          onComplete={handleSetupComplete} />}
      {view === 'onboarding' && <OnboardingWalkthrough onComplete={handleOnboardingComplete} />}
      {view === 'chat'       && <ChatLayout darkMode={darkMode} onToggleDarkMode={dark => {
        setDarkMode(dark)
        applyDarkMode(dark)
      }} />}
    </>
  )
}
