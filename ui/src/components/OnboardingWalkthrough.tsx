// ui/src/components/OnboardingWalkthrough.tsx
// First-launch overlay that explains AUA-Veritas in plain language.
// 5 steps. Shown once, persisted to localStorage.

interface Props {
  onComplete: () => void
}

const STEPS = [
  {
    icon: '🤖',
    title: 'Ask anything — across multiple AI models',
    body: 'AUA-Veritas sends your questions to the AI models you connect, then picks the most accurate answer. You get better results than going to any single AI directly.',
  },
  {
    icon: '🎚️',
    title: 'Choose how thorough you want to be',
    body: 'The accuracy slider lets you decide:\n\n• Fast — one model, same cost as direct\n• Balanced — cross-checks with a second model (~1.05× cost)\n• High — all your models compete, best wins\n• Maximum — all models, then they review each other',
  },
  {
    icon: '✓',
    title: 'See confidence in plain language',
    body: 'The right panel tells you how confident the answer is (High / Medium / Uncertain) and exactly what happened — which models answered, whether they agreed, and if any past correction was applied.',
  },
  {
    icon: '🧠',
    title: 'The app learns from your corrections',
    body: 'When you tell the AI it got something wrong, Veritas saves that as a project memory. Every future answer on the same topic gets that correction injected automatically — you never have to repeat yourself.',
  },
  {
    icon: '↗',
    title: 'Restart any project in one click',
    body: 'The Memory tab stores all your project decisions and corrections. Click "Generate restart prompt" to get a compact block you can paste into Claude Code, Cursor, or any other AI tool to instantly restore your project context.',
  },
]

export default function OnboardingWalkthrough({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 10000, padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: '32px 28px',
        maxWidth: 460, width: '100%',
        boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
      }}>
        {/* Step indicator */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 24, justifyContent: 'center' }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 20 : 8, height: 8, borderRadius: 4,
              background: i === step ? '#4338ca' : i < step ? '#a5b4fc' : '#e5e7eb',
              transition: 'all 0.3s ease',
            }} />
          ))}
        </div>

        {/* Content */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>{current.icon}</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#111827', marginBottom: 12, lineHeight: 1.3 }}>
            {current.title}
          </div>
          <div style={{
            fontSize: 14, color: '#6b7280', lineHeight: 1.7,
            whiteSpace: 'pre-line', textAlign: 'left',
          }}>
            {current.body}
          </div>
        </div>

        {/* Navigation */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={onComplete}
            style={{
              padding: '8px 14px', borderRadius: 8, fontSize: 13,
              background: 'transparent', color: '#9ca3af',
              border: 'none', cursor: 'pointer',
            }}
          >
            Skip
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            {step > 0 && (
              <button
                onClick={() => setStep(s => s - 1)}
                style={{
                  padding: '10px 20px', borderRadius: 9, fontSize: 14, fontWeight: 600,
                  background: '#f3f4f6', color: '#374151',
                  border: 'none', cursor: 'pointer',
                }}
              >
                Back
              </button>
            )}
            <button
              onClick={() => isLast ? onComplete() : setStep(s => s + 1)}
              style={{
                padding: '10px 24px', borderRadius: 9, fontSize: 14, fontWeight: 700,
                background: '#4338ca', color: '#fff',
                border: 'none', cursor: 'pointer',
              }}
            >
              {isLast ? "Let's go →" : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Missing import — add at top
import { useState } from 'react'
