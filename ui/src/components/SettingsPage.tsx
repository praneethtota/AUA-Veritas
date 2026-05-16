// ui/src/components/SettingsPage.tsx — Settings modal
// Phase 5.6: Per-provider [?] help modal with numbered steps, open-in-browser, key format, free tier note.

import { useState, useEffect } from 'react'
import { getKeyStatus, saveApiKey, deleteApiKey, testModel, listModels } from '../api'

const PROVIDERS = [
  { id: 'openai',    name: 'OpenAI (ChatGPT)',   helpUrl: 'https://platform.openai.com/api-keys',        keyPrefix: 'sk-proj-', freeNote: null as string|null,
    steps: ['Go to platform.openai.com/api-keys','Sign in or create a free account','Click + Create new secret key','Give it a name (e.g. "AUA-Veritas") and click Create','Copy the key — it starts with sk-proj-','Paste it into the field above and click Connect'] },
  { id: 'anthropic', name: 'Anthropic (Claude)', helpUrl: 'https://console.anthropic.com/settings/keys', keyPrefix: 'sk-ant-',  freeNote: null as string|null,
    steps: ['Go to console.anthropic.com/settings/keys','Sign in or create an account','Click Create Key','Copy the key — it starts with sk-ant-','Paste it into the field above and click Connect'] },
  { id: 'google',    name: 'Google (Gemini)',     helpUrl: 'https://aistudio.google.com/app/apikey',      keyPrefix: 'AIza',     freeNote: 'Gemini has a free tier — no payment needed to get started.',
    steps: ['Go to aistudio.google.com/app/apikey','Sign in with your Google account','Click Create API key','Copy the key — it starts with AIza','Paste it into the field above and click Connect'] },
  { id: 'xai',       name: 'xAI (Grok)',          helpUrl: 'https://console.x.ai/api-keys',               keyPrefix: 'xai-',     freeNote: 'xAI offers a limited free tier.',
    steps: ['Go to console.x.ai/api-keys','Sign in with your X (Twitter) account','Create a new API key','Copy the key — it starts with xai-','Paste it into the field above and click Connect'] },
  { id: 'mistral',   name: 'Mistral',             helpUrl: 'https://console.mistral.ai/api-keys',         keyPrefix: '',         freeNote: 'Mistral offers a limited free tier.',
    steps: ['Go to console.mistral.ai/api-keys','Sign in or create a free account','Click Create new key','Copy your API key','Paste it into the field above and click Connect'] },
  { id: 'groq',      name: 'Groq (Llama)',        helpUrl: 'https://console.groq.com/keys',               keyPrefix: 'gsk_',     freeNote: 'Groq has a generous free tier — no payment needed to get started.',
    steps: ['Go to console.groq.com/keys','Sign in or create a free account','Click Create API Key','Copy the key — it starts with gsk_','Paste it into the field above and click Connect'] },
  { id: 'deepseek',  name: 'DeepSeek',            helpUrl: 'https://platform.deepseek.com/api_keys',      keyPrefix: 'sk-',      freeNote: 'DeepSeek is pay-as-you-go with very low pricing.',
    steps: ['Go to platform.deepseek.com/api_keys','Sign in or create an account','Click Create new API key','Copy the key — it starts with sk-','Paste it into the field above and click Connect'] },
]

interface Props {
  darkMode: boolean
  onToggleDarkMode: (dark: boolean) => void
  onClose: () => void
}

export default function SettingsPage({ darkMode, onToggleDarkMode, onClose }: Props) {
  const [keyStatus, setKeyStatus] = useState<Record<string, boolean>>({})
  const [newKeys, setNewKeys]     = useState<Record<string, string>>({})
  const [testing, setTesting]     = useState<Record<string, 'idle'|'loading'|'ok'|'error'>>({})
  const [removing, setRemoving]   = useState<string | null>(null)
  const [models, setModels]       = useState<Record<string, any>>({})
  const [helpProvider, setHelpProvider] = useState<typeof PROVIDERS[0] | null>(null)

  useEffect(() => {
    getKeyStatus().then(setKeyStatus).catch(() => {})
    listModels().then(setModels).catch(() => {})
  }, [])

  const handleTestNew = async (provider: typeof PROVIDERS[0]) => {
    const key = newKeys[provider.id]?.trim()
    if (!key) return
    setTesting(t => ({ ...t, [provider.id]: 'loading' }))
    try {
      await saveApiKey(provider.id, key)
      const pm = Object.values(models).filter((m: any) => m.provider === provider.id)
      const testModelId = (pm[0] as any)?.model_id || provider.id
      const result = await testModel(testModelId)
      const ok = result.status === 'ok'
      setTesting(t => ({ ...t, [provider.id]: ok ? 'ok' : 'error' }))
      if (ok) {
        setKeyStatus(s => ({ ...s, [provider.id]: true }))
        setNewKeys(k => ({ ...k, [provider.id]: '' }))
        await listModels().then(setModels)
      }
    } catch {
      setTesting(t => ({ ...t, [provider.id]: 'error' }))
    }
  }

  const handleRemove = async (id: string) => {
    setRemoving(id)
    try {
      await deleteApiKey(id)
      setKeyStatus(s => ({ ...s, [id]: false }))
      await listModels().then(setModels)
    } catch {}
    setRemoving(null)
  }

  const openExternal = (url: string) => {
    if ((window as any).veritas?.openExternal) (window as any).veritas.openExternal(url)
    else window.open(url)
  }

  return (
    <div style={{ position:'fixed',inset:0,background:'var(--overlay)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9998,padding:24 }}>
      <div style={{ borderRadius:14,width:'100%',maxWidth:520,maxHeight:'85vh',overflow:'hidden',display:'flex',flexDirection:'column',boxShadow:'0 20px 60px rgba(0,0,0,0.15)',background:'var(--bg-surface)' }}>

        {/* Header */}
        <div style={{ padding:'18px 20px 14px',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0 }}>
          <div style={{ fontSize:15,fontWeight:700,color:'var(--text-primary)' }}>Settings</div>
          <button onClick={onClose} style={{ width:28,height:28,borderRadius:7,border:'1px solid var(--border)',background:'var(--bg-secondary)',cursor:'pointer',fontSize:16,color:'var(--text-secondary)',display:'flex',alignItems:'center',justifyContent:'center' }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex:1,overflowY:'auto',padding:'16px 20px' }}>

          {/* Appearance */}
          <div style={{ marginBottom:20 }}>
            <div style={{ fontSize:13,fontWeight:700,color:'var(--text-primary)',marginBottom:12 }}>Appearance</div>
            <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'12px 14px',borderRadius:8,border:'1px solid var(--border)',background:'var(--bg-surface)' }}>
              <div>
                <div style={{ fontSize:13,fontWeight:600,color:'var(--text-primary)' }}>Dark mode</div>
                <div style={{ fontSize:11,color:'var(--text-muted)',marginTop:2 }}>Switch between light and dark theme</div>
              </div>
              <button onClick={() => onToggleDarkMode(!darkMode)} style={{ width:44,height:24,borderRadius:12,border:'none',cursor:'pointer',background:darkMode?'var(--accent)':'var(--border)',position:'relative',transition:'background 0.2s',flexShrink:0 }}>
                <div style={{ position:'absolute',top:3,left:darkMode?23:3,width:18,height:18,borderRadius:9,background:'#fff',transition:'left 0.2s',boxShadow:'0 1px 3px rgba(0,0,0,0.2)' }} />
              </button>
            </div>
          </div>

          {/* API Keys */}
          <div style={{ fontSize:13,fontWeight:700,color:'var(--text-primary)',marginBottom:12 }}>API Keys</div>

          {PROVIDERS.map(provider => {
            const connected = keyStatus[provider.id]
            const status    = testing[provider.id] || 'idle'
            return (
              <div key={provider.id} style={{ padding:'12px 14px',borderRadius:8,border:`1px solid ${connected?'#a7f3d0':'var(--border)'}`,background:connected?'#f0fdf4':'var(--bg-secondary)',marginBottom:8 }}>
                <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:connected?0:8 }}>
                  <span style={{ fontSize:13,fontWeight:600,color:'var(--text-primary)',flex:1 }}>{provider.name}</span>
                  {provider.freeNote && <span style={{ fontSize:10,background:'#ecfdf5',color:'#059669',padding:'2px 6px',borderRadius:4,fontWeight:500 }}>Free</span>}
                  {/* [?] button — Phase 5.6 */}
                  <button onClick={() => setHelpProvider(provider)} title={`How to get your ${provider.name} key`} style={{ width:18,height:18,borderRadius:4,border:'1px solid var(--border)',background:'var(--bg-surface)',cursor:'pointer',fontSize:10,color:'var(--text-muted)',fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0 }}>?</button>
                  {connected && (
                    <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                      <span style={{ fontSize:12,color:'#059669',fontWeight:600 }}>✓ Connected</span>
                      <button onClick={() => handleRemove(provider.id)} disabled={removing===provider.id} style={{ padding:'3px 8px',borderRadius:5,fontSize:11,background:'#fee2e2',color:'#dc2626',border:'none',cursor:'pointer',fontWeight:500 }}>
                        {removing===provider.id?'...':'Remove'}
                      </button>
                    </div>
                  )}
                </div>
                {!connected && (
                  <div style={{ display:'flex',gap:6 }}>
                    <input type="password" placeholder={`${provider.keyPrefix||'API key'}...`} value={newKeys[provider.id]||''} onChange={e=>setNewKeys(k=>({...k,[provider.id]:e.target.value}))} onKeyDown={e=>e.key==='Enter'&&handleTestNew(provider)}
                      style={{ flex:1,padding:'6px 8px',borderRadius:6,fontSize:12,border:`1px solid ${status==='error'?'#fca5a5':'var(--border)'}`,outline:'none',background:'var(--input-bg)',fontFamily:'monospace',color:'var(--text-primary)' }} />
                    <button onClick={()=>handleTestNew(provider)} disabled={!newKeys[provider.id]?.trim()||status==='loading'}
                      style={{ padding:'6px 12px',borderRadius:6,fontSize:12,fontWeight:600,background:'#4338ca',color:'#fff',border:'none',cursor:newKeys[provider.id]?.trim()?'pointer':'default',opacity:newKeys[provider.id]?.trim()?1:0.5 }}>
                      {status==='loading'?'...':status==='error'?'Invalid key':'Connect'}
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          <div style={{ fontSize:11,color:'var(--text-muted)',marginTop:8,lineHeight:1.5 }}>
            🔒 All keys stored in your Mac Keychain — never in the cloud.
          </div>
        </div>
      </div>

      {/* Per-provider help modal */}
      {helpProvider && (
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,0.55)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999,padding:24 }} onClick={()=>setHelpProvider(null)}>
          <div style={{ background:'var(--bg-surface)',borderRadius:12,width:'100%',maxWidth:440,boxShadow:'0 24px 64px rgba(0,0,0,0.25)',overflow:'hidden' }} onClick={e=>e.stopPropagation()}>
            <div style={{ padding:'16px 20px',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',justifyContent:'space-between' }}>
              <div style={{ fontSize:14,fontWeight:700,color:'var(--text-primary)' }}>How to get your {helpProvider.name} key</div>
              <button onClick={()=>setHelpProvider(null)} style={{ background:'none',border:'none',cursor:'pointer',fontSize:20,color:'var(--text-muted)',lineHeight:1 }}>×</button>
            </div>
            <div style={{ padding:'16px 20px' }}>
              {helpProvider.steps.map((step,i) => (
                <div key={i} style={{ display:'flex',gap:12,marginBottom:12,alignItems:'flex-start' }}>
                  <div style={{ width:22,height:22,borderRadius:6,flexShrink:0,background:'#4338ca',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontSize:11,fontWeight:700 }}>{i+1}</div>
                  <div style={{ fontSize:13,color:'var(--text-primary)',lineHeight:1.5,paddingTop:2,flex:1 }}>
                    {step}
                    {i===0 && (
                      <button onClick={()=>openExternal(helpProvider.helpUrl)} style={{ marginLeft:8,padding:'1px 8px',borderRadius:4,fontSize:11,background:'#ede9fe',color:'#4338ca',border:'none',cursor:'pointer',fontWeight:600 }}>Open ↗</button>
                    )}
                  </div>
                </div>
              ))}
              {helpProvider.keyPrefix && (
                <div style={{ marginTop:4,padding:'8px 12px',borderRadius:6,background:'var(--bg-secondary)',fontSize:12,color:'var(--text-secondary)',fontFamily:'monospace' }}>
                  Key format: {helpProvider.keyPrefix}...
                </div>
              )}
              {helpProvider.freeNote && (
                <div style={{ marginTop:8,padding:'8px 12px',borderRadius:6,background:'#f0fdf4',border:'1px solid #a7f3d0',fontSize:12,color:'#065f46' }}>
                  🟢 {helpProvider.freeNote}
                </div>
              )}
              <div style={{ marginTop:8,padding:'8px 12px',borderRadius:6,background:'var(--bg-secondary)',fontSize:11,color:'var(--text-muted)' }}>
                🔒 Your key is stored in your Mac Keychain — never in the cloud.
              </div>
              <button onClick={()=>setHelpProvider(null)} style={{ marginTop:16,width:'100%',padding:'10px',borderRadius:8,background:'#4338ca',color:'#fff',border:'none',cursor:'pointer',fontSize:13,fontWeight:600 }}>
                Got it — close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
