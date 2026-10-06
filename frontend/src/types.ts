// Backend şemalarının (backend/app/schemas.py, backend/app/api/schemas.py) TypeScript karşılıkları

export type Maturity = 'fikir' | 'prototip' | 'mvp' | 'ilk_gelir' | 'buyume'

export interface Brief {
  title: string
  problem: string | null
  scope: string | null
  required_capabilities: string[]
  sector: string | null
  success_criteria: string | null
  timeline: string | null
  budget: string | null
  location_preference: string | null
  min_maturity: Maturity | null
  missing_fields: string[]
}

export interface FollowUpQuestion {
  field: string
  question: string
  examples?: string[] // tek dokunuşla seçilebilen hazır cevaplar
}

export interface BriefOut {
  brief_id: number
  need_id: number
  status: 'needs_input' | 'final'
  brief: Brief
  questions: FollowUpQuestion[]
}

export interface StartupProfile {
  id: string
  name: string
  sector: string
  maturity: Maturity
  location: string
  capabilities: string[]
  description: string
  past_pilots: string[]
}

export interface EvidenceLink {
  brief_phrase: string
  startup_capability: string
  explanation: string
}

export interface MatchRationale {
  startup_id: string
  fit_summary: string
  evidence: EvidenceLink[]
}

export interface RejectionRationale {
  startup_id: string
  near_miss_reason: string
  missing_capability: string | null
}

export type MatchStatus = 'suggested' | 'accepted' | 'declined'

export interface MatchItem {
  rank: number
  startup: StartupProfile
  score: number
  vector_score: number
  rationale: MatchRationale | null
  rejection: RejectionRationale | null
  filter_notes: string[]
  match_id: number
  status: MatchStatus
  declined_reason?: string | null
}

export interface MatchView {
  brief_id: number
  run_id: number
  shortlist: MatchItem[]
  rejected: MatchItem[]
  retrieval_trace: string[]
}

// POST /briefs/{id}/match cevabı: durumlar ayrı bir sözlükte gelir
export interface MatchOut extends Omit<MatchView, 'shortlist' | 'rejected'> {
  shortlist: Omit<MatchItem, 'match_id' | 'status'>[]
  rejected: Omit<MatchItem, 'match_id' | 'status'>[]
  match_ids: Record<string, number>
}

export interface NeedSummary {
  brief_id: number
  need_id: number
  title: string
  status: 'needs_input' | 'final'
  raw_text: string
  organization: string | null
  created_at: string
  shortlist_count: number
  accepted_count: number
}

export interface Milestone {
  id: number
  title: string
  due_date: string | null
  completed_at: string | null
}

export type PilotStatus = 'active' | 'paused' | 'done' | 'cancelled'

export interface Pilot {
  id: number
  status: PilotStatus
  match_id: number
  brief_id: number
  brief_title: string
  startup: StartupProfile
  started_at: string
  last_activity_at: string
  days_inactive: number
  stale: boolean
  outcome: string | null
  outcome_score: number | null
  milestones: Milestone[]
}

export interface Health {
  status: string
  llm_model: string
  demo_mode: string
  rerank_backend: string
}
