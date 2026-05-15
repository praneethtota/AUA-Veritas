// ui/src/types.ts — Shared types for AUA-Veritas UI

export type AccuracyLevel = 'fast' | 'balanced' | 'high' | 'maximum'

export type MessageRole = 'user' | 'assistant' | 'callout' | 'system'

export type CalloutType =
  | 'correction'
  | 'crosscheck'
  | 'disagreement'
  | 'highstakes'
  | 'conflict'
  | 'context_reset'

export type ConfidenceLabel = 'High' | 'Medium' | 'Uncertain'

export interface Message {
  id: string
  role: MessageRole
  content: string
  callout_type?: CalloutType
  models_used?: string[]
  accuracy_level?: AccuracyLevel
  confidence?: ConfidenceLabel
  welfare_scores?: Record<string, number>
  peer_review_used?: boolean
  corrections_applied?: string[]
  latency_ms?: number
  timestamp: number
}

export interface Conversation {
  conversation_id: string
  title: string
  updated_at: number
  messages?: Message[]
}

export interface ModelInfo {
  model_id: string
  provider: string
  display_name: string
  connected: boolean
  is_cheap_judge: boolean
  context_window: number
}

export interface KeyStatus {
  [provider: string]: boolean
}

export interface CostEstimate {
  calls: number
  estimated_usd: number
  label: string
}

export interface QueryResponse {
  response: string
  primary_model: string
  all_models_used: string[]
  confidence_label: ConfidenceLabel
  callout_type: CalloutType | null
  callout_text: string | null
  welfare_scores: Record<string, number> | null
  peer_review_used: boolean
  corrections_applied: string[]
  latency_ms: number
}

export interface Memory {
  correction_id: string
  type: string
  scope: string
  corrective_instruction: string
  canonical_query: string
  domain: string
  confidence: number
  decay_class: string
  pinned?: boolean
  created_at: number
}

export interface ScoreEvent {
  audit_id: string
  model_id: string
  score_before: number
  score_after: number
  verdict: string
  correction_stored: boolean
  query_preview: string
  created_at: number
}
